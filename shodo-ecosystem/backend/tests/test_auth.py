def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.status_code in (200, 503)
    # 最新推奨ヘッダが付与されていること
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert "Permissions-Policy" in resp.headers
    assert "Content-Security-Policy" in resp.headers
"""
認証関連のテスト
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.core.security import JWTManager, InputSanitizer, DataEncryption
from src.schemas.auth import LoginRequest, RegisterRequest, UserInfo

@pytest.mark.unit
class TestJWTManager:
    """JWTマネージャーのテスト"""
    
    def test_create_access_token(self):
        """アクセストークン生成のテスト"""
        data = {
            "user_id": "test-user",
            "username": "testuser",
            "email": "test@example.com"
        }
        
        token = JWTManager.create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # JWT形式
    
    def test_verify_valid_token(self):
        """有効なトークンの検証"""
        data = {
            "user_id": "test-user",
            "username": "testuser",
            "email": "test@example.com",
            "roles": ["user"]
        }
        
        token = JWTManager.create_access_token(data)
        
        # Mock credentials
        mock_credentials = Mock()
        mock_credentials.credentials = token
        
        token_data = JWTManager.verify_token(mock_credentials)
        
        assert token_data.user_id == "test-user"
        assert token_data.username == "testuser"
        assert token_data.email == "test@example.com"
    
    def test_verify_expired_token(self):
        """期限切れトークンの検証"""
        data = {
            "user_id": "test-user",
            "username": "testuser",
            "email": "test@example.com",
            "exp": (datetime.utcnow() - timedelta(hours=1)).timestamp()
        }
        
        # 期限切れトークンを直接作成
        import jwt
        token = jwt.encode(data, "test-secret-key", algorithm="HS256")
        
        mock_credentials = Mock()
        mock_credentials.credentials = token
        
        with pytest.raises(Exception):  # HTTPException
            JWTManager.verify_token(mock_credentials)

@pytest.mark.unit
class TestInputSanitizer:
    """入力サニタイザーのテスト"""
    
    def test_sanitize_html(self):
        """HTMLサニタイズのテスト"""
        dirty_html = '<script>alert("XSS")</script><p>Safe content</p>'
        clean_html = InputSanitizer.sanitize_html(dirty_html)
        
        assert "<script>" not in clean_html
        assert "alert" not in clean_html
        assert "<p>Safe content</p>" in clean_html
    
    def test_sanitize_json(self):
        """JSONサニタイズのテスト"""
        dirty_json = {
            "text": '<script>alert("XSS")</script>',
            "nested": {
                "value": '<img src=x onerror="alert(1)">'
            }
        }
        
        clean_json = InputSanitizer.sanitize_json(dirty_json)
        
        assert "<script>" not in clean_json["text"]
        assert "onerror" not in clean_json["nested"]["value"]
    
    def test_validate_prompt(self):
        """プロンプト検証のテスト"""
        # 正常なプロンプト
        valid_prompt = "これは正常なプロンプトです。"
        result = InputSanitizer.validate_prompt(valid_prompt)
        assert result == valid_prompt.strip()
        
        # 危険なパターンを含むプロンプト
        dangerous_prompt = "javascript:alert('XSS')"
        result = InputSanitizer.validate_prompt(dangerous_prompt)
        assert "javascript:" not in result

@pytest.mark.unit
class TestDataEncryption:
    """データ暗号化のテスト"""
    
    def test_encrypt_decrypt(self):
        """暗号化と復号化のテスト"""
        encryption = DataEncryption()
        
        original = "This is sensitive data"
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)
        
        assert encrypted != original
        assert decrypted == original
    
    def test_encrypt_different_each_time(self):
        """同じデータでも異なる暗号文になることのテスト"""
        encryption = DataEncryption()
        
        original = "Test data"
        encrypted1 = encryption.encrypt(original)
        encrypted2 = encryption.encrypt(original)
        
        # Fernetは同じデータでも異なる暗号文を生成
        assert encrypted1 != encrypted2
        
        # どちらも正しく復号化できる
        assert encryption.decrypt(encrypted1) == original
        assert encryption.decrypt(encrypted2) == original

@pytest.mark.integration
class TestAuthAPI:
    """認証APIのテスト"""
    
    def test_login_success(self, client):
        """ログイン成功のテスト"""
        # ユーザーを事前に作成（モック）
        with patch('src.api.v1.auth.authenticate_user') as mock_auth:
            mock_auth.return_value = {
                "user_id": "test-user",
                "email": "test@example.com",
                "username": "testuser"
            }
            
            response = client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "password123"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data["data"]
            assert data["data"]["token_type"] == "Bearer"
    
    def test_login_invalid_credentials(self, client):
        """無効な認証情報でのログインテスト"""
        with patch('src.api.v1.auth.authenticate_user') as mock_auth:
            mock_auth.return_value = None
            
            response = client.post("/api/v1/auth/login", json={
                "email": "wrong@example.com",
                "password": "wrongpassword"
            })
            
            assert response.status_code == 401
    
    def test_register_success(self, client):
        """ユーザー登録成功のテスト"""
        with patch('src.api.v1.auth.create_user') as mock_create:
            mock_create.return_value = {
                "user_id": "new-user",
                "email": "new@example.com",
                "username": "newuser"
            }
            
            response = client.post("/api/v1/auth/register", json={
                "email": "new@example.com",
                "password": "SecurePass123!",
                "confirm_password": "SecurePass123!",
                "username": "newuser"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["email"] == "new@example.com"
    
    def test_register_password_mismatch(self, client):
        """パスワード不一致での登録テスト"""
        response = client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "SecurePass123!",
            "confirm_password": "DifferentPass123!",
            "username": "newuser"
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_get_current_user(self, client, auth_headers):
        """現在のユーザー情報取得テスト"""
        with patch('src.api.v1.auth.get_user_by_id') as mock_get:
            mock_get.return_value = {
                "user_id": "test-user-id",
                "email": "test@example.com",
                "username": "testuser"
            }
            
            response = client.get("/api/v1/auth/me", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["user_id"] == "test-user-id"
    
    def test_change_password(self, client, auth_headers):
        """パスワード変更テスト"""
        with patch('src.api.v1.auth.verify_password') as mock_verify:
            mock_verify.return_value = True
            
            with patch('src.api.v1.auth.update_password') as mock_update:
                mock_update.return_value = True
                
                response = client.post("/api/v1/auth/change-password", 
                    headers=auth_headers,
                    json={
                        "current_password": "OldPass123!",
                        "new_password": "NewPass123!",
                        "confirm_password": "NewPass123!"
                    }
                )
                
                assert response.status_code == 200