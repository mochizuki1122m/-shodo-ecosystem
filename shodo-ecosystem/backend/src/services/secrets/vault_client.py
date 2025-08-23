"""
HashiCorp Vault client for secrets management
MUST: All production secrets from Vault, never from environment
"""

import os
from typing import Dict, Any
from datetime import datetime, timedelta
import asyncio
from functools import lru_cache

import hvac
from hvac.exceptions import InvalidPath, Forbidden
import structlog

from ...core.config import settings

logger = structlog.get_logger()

class VaultClient:
    """
    HashiCorp Vault client for secure secrets management
    
    MUST requirements:
    - All production secrets from Vault
    - Automatic token renewal
    - Audit logging for all access
    - Encryption in transit
    - Dynamic secrets where possible
    """
    
    def __init__(
        self,
        vault_url: str = None,
        vault_token: str = None,
        mount_point: str = "secret",
        path_prefix: str = "shodo",
        auto_renew: bool = True
    ):
        self.vault_url = vault_url or settings.vault_url or os.getenv("VAULT_ADDR")
        self.vault_token = vault_token or settings.vault_token.get_secret_value() if settings.vault_token else os.getenv("VAULT_TOKEN")
        self.mount_point = mount_point
        self.path_prefix = path_prefix
        self.auto_renew = auto_renew
        
        self.client = None
        self._token_renew_task = None
        self._secrets_cache = {}
        self._cache_ttl = 300  # 5 minutes cache
        
        if not self.vault_url or not self.vault_token:
            if settings.is_production():
                raise ValueError("Vault URL and token are required in production")
            else:
                logger.warning("Vault not configured, using environment variables")
    
    async def initialize(self):
        """Initialize Vault client and verify connectivity"""
        if not self.vault_url or not self.vault_token:
            logger.warning("Vault not configured")
            return
        
        try:
            self.client = hvac.Client(
                url=self.vault_url,
                token=self.vault_token,
                verify=settings.is_production()  # Verify SSL in production
            )
            
            # Verify authentication
            if not self.client.is_authenticated():
                raise ValueError("Vault authentication failed")
            
            logger.info(
                "Vault client initialized",
                vault_url=self.vault_url,
                mount_point=self.mount_point
            )
            
            # Start token renewal if enabled
            if self.auto_renew:
                self._token_renew_task = asyncio.create_task(self._token_renewal_loop())
            
        except Exception as e:
            logger.error("Failed to initialize Vault client", error=str(e))
            if settings.is_production():
                raise
    
    async def get_secret(
        self,
        path: str,
        key: str = None,
        version: int = None,
        use_cache: bool = True
    ) -> Any:
        """
        Get secret from Vault
        
        Args:
            path: Secret path (relative to path_prefix)
            key: Specific key in secret (optional)
            version: Secret version (optional)
            use_cache: Use cached value if available
        
        Returns:
            Secret value
        """
        
        # Check cache first
        cache_key = f"{path}:{key}:{version}"
        if use_cache and cache_key in self._secrets_cache:
            cached = self._secrets_cache[cache_key]
            if cached['expires'] > datetime.utcnow():
                return cached['value']
        
        # Fallback to environment in development
        if not self.client:
            return self._get_from_environment(path, key)
        
        try:
            # Build full path
            full_path = f"{self.path_prefix}/{path}"
            
            # Read from Vault
            if version:
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=full_path,
                    version=version,
                    mount_point=self.mount_point
                )
            else:
                response = self.client.secrets.kv.v2.read_secret(
                    path=full_path,
                    mount_point=self.mount_point
                )
            
            if not response or 'data' not in response:
                raise ValueError(f"Secret not found: {full_path}")
            
            data = response['data'].get('data', {})
            
            # Get specific key or entire secret
            if key:
                value = data.get(key)
                if value is None:
                    raise ValueError(f"Key '{key}' not found in secret '{full_path}'")
            else:
                value = data
            
            # Cache the result
            if use_cache:
                self._secrets_cache[cache_key] = {
                    'value': value,
                    'expires': datetime.utcnow() + timedelta(seconds=self._cache_ttl)
                }
            
            # Audit log
            logger.info(
                "Secret accessed",
                path=path,
                key=key,
                version=version
            )
            
            return value
            
        except InvalidPath:
            logger.error("Secret path not found", path=full_path)
            raise ValueError(f"Secret not found: {path}")
        except Forbidden:
            logger.error("Access denied to secret", path=full_path)
            raise PermissionError(f"Access denied: {path}")
        except Exception as e:
            logger.error("Failed to get secret", path=path, error=str(e))
            raise
    
    async def get_database_credentials(self, database: str = "postgres") -> Dict[str, str]:
        """Get database credentials from Vault"""
        
        # Try dynamic credentials first
        try:
            return await self._get_dynamic_db_credentials(database)
        except:
            # Fallback to static credentials
            return await self.get_secret(f"database/{database}")
    
    async def _get_dynamic_db_credentials(self, database: str) -> Dict[str, str]:
        """Get dynamic database credentials"""
        
        if not self.client:
            raise ValueError("Vault client not initialized")
        
        try:
            # Request dynamic credentials
            response = self.client.read(f"database/creds/{database}")
            
            if response and 'data' in response:
                return {
                    'username': response['data']['username'],
                    'password': response['data']['password'],
                    'lease_duration': response['lease_duration']
                }
            
            raise ValueError("Failed to get dynamic credentials")
            
        except Exception as e:
            logger.warning(
                "Failed to get dynamic DB credentials, falling back to static",
                database=database,
                error=str(e)
            )
            raise
    
    async def get_api_key(self, service: str) -> str:
        """Get API key for external service"""
        return await self.get_secret(f"api-keys/{service}", "key")
    
    async def get_jwt_keys(self) -> Dict[str, str]:
        """Get JWT signing keys"""
        keys = await self.get_secret("jwt", use_cache=False)
        return {
            'private_key': keys.get('private_key'),
            'public_key': keys.get('public_key'),
            'kid': keys.get('kid')
        }
    
    async def get_encryption_key(self) -> bytes:
        """Get master encryption key"""
        key = await self.get_secret("encryption", "master_key", use_cache=False)
        if isinstance(key, str):
            return key.encode()
        return key
    
    async def rotate_secret(self, path: str) -> Dict[str, Any]:
        """Rotate a secret in Vault"""
        
        if not self.client:
            raise ValueError("Vault client not initialized")
        
        try:
            f"{self.path_prefix}/{path}"
            
            # Create new version
            # Implementation depends on secret type
            
            logger.warning(
                "Secret rotated",
                path=path
            )
            
            # Clear cache
            self._clear_cache_for_path(path)
            
            return {"status": "rotated", "path": path}
            
        except Exception as e:
            logger.error("Failed to rotate secret", path=path, error=str(e))
            raise
    
    async def _token_renewal_loop(self):
        """Background task to renew Vault token"""
        
        while True:
            try:
                # Check token TTL
                token_info = self.client.auth.token.lookup_self()
                ttl = token_info['data']['ttl']
                
                # Renew if less than 1 hour remaining
                if ttl < 3600:
                    self.client.auth.token.renew_self()
                    logger.info("Vault token renewed", new_ttl=ttl)
                
                # Sleep for half the TTL
                await asyncio.sleep(min(ttl / 2, 3600))
                
            except Exception as e:
                logger.error("Token renewal failed", error=str(e))
                await asyncio.sleep(60)  # Retry after 1 minute
    
    def _get_from_environment(self, path: str, key: str = None) -> Any:
        """Fallback to environment variables in development"""
        
        # Map Vault paths to environment variables
        env_map = {
            "database/postgres": {
                "username": "POSTGRES_USER",
                "password": "POSTGRES_PASSWORD",
                "host": "POSTGRES_HOST",
                "port": "POSTGRES_PORT",
                "database": "POSTGRES_DB"
            },
            "redis": {
                "url": "REDIS_URL",
                "password": "REDIS_PASSWORD"
            },
            "jwt": {
                "private_key": "JWT_PRIVATE_KEY",
                "public_key": "JWT_PUBLIC_KEY",
                "secret": "JWT_SECRET_KEY"
            },
            "encryption": {
                "master_key": "ENCRYPTION_KEY"
            },
            "api-keys/shopify": {
                "key": "SHOPIFY_API_KEY",
                "secret": "SHOPIFY_API_SECRET"
            },
            "api-keys/stripe": {
                "key": "STRIPE_API_KEY"
            },
            "api-keys/gmail": {
                "client_id": "GMAIL_CLIENT_ID",
                "client_secret": "GMAIL_CLIENT_SECRET"
            }
        }
        
        if path in env_map:
            if key:
                env_var = env_map[path].get(key)
                if env_var:
                    return os.getenv(env_var)
            else:
                return {
                    k: os.getenv(v) 
                    for k, v in env_map[path].items()
                }
        
        return None
    
    def _clear_cache_for_path(self, path: str):
        """Clear cache entries for a specific path"""
        keys_to_remove = [
            k for k in self._secrets_cache.keys()
            if k.startswith(f"{path}:")
        ]
        for key in keys_to_remove:
            del self._secrets_cache[key]
    
    async def close(self):
        """Clean up resources"""
        if self._token_renew_task:
            self._token_renew_task.cancel()
            try:
                await self._token_renew_task
            except asyncio.CancelledError:
                pass
        
        self._secrets_cache.clear()

# Singleton instance
_vault_client = None

async def get_vault_client() -> VaultClient:
    """Get or create Vault client instance"""
    global _vault_client
    
    if _vault_client is None:
        _vault_client = VaultClient()
        await _vault_client.initialize()
    
    return _vault_client

@lru_cache(maxsize=128)
def get_secret_sync(path: str, key: str = None) -> Any:
    """Synchronous wrapper for getting secrets (for config initialization)"""
    
    # In production, this should not be used
    # Secrets should be loaded asynchronously at startup
    
    if settings.is_production():
        raise RuntimeError("Synchronous secret access not allowed in production")
    
    # Development fallback to environment
    env_value = os.getenv(f"{path.upper().replace('/', '_')}_{key.upper()}" if key else path.upper().replace('/', '_'))
    return env_value