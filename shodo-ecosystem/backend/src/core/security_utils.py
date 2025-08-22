"""
Lightweight security utilities without heavy framework dependencies.
Includes:
- InputSanitizer (Unicode-safe)
- PIIMasking
- SecureTokenGenerator
"""
from typing import List
import secrets
import hashlib
import unicodedata


class InputSanitizer:
	"""Input sanitization and validation (Unicode-friendly)"""
	@staticmethod
	def sanitize_string(value: str, max_length: int = 1000) -> str:
		if value is None:
			return ""
		if not isinstance(value, str):
			try:
				value = str(value)
			except Exception:
				return ""
		# Pre-truncate
		if len(value) > max_length * 2:
			value = value[: max_length * 2]
		# Remove control chars (Cc/Cf), allow \n and \t
		cleaned_chars = []
		for ch in value:
			cat = unicodedata.category(ch)
			if ch in ('\n', '\t'):
				cleaned_chars.append(ch)
				continue
			if cat in ("Cc", "Cf"):
				continue
			cleaned_chars.append(ch)
		cleaned = "".join(cleaned_chars)
		# Final truncate and trim
		if len(cleaned) > max_length:
			cleaned = cleaned[:max_length]
		return cleaned.strip()

	@staticmethod
	def sanitize_json(data: dict) -> dict:
		if not isinstance(data, dict):
			return {}
		sanitized = {}
		for key, value in data.items():
			if isinstance(value, str):
				sanitized[key] = InputSanitizer.sanitize_string(value)
			elif isinstance(value, dict):
				sanitized[key] = InputSanitizer.sanitize_json(value)
			elif isinstance(value, list):
				sanitized[key] = [
					InputSanitizer.sanitize_json(item) if isinstance(item, dict)
					else InputSanitizer.sanitize_string(item) if isinstance(item, str)
					else item
					for item in value
				]
			else:
				sanitized[key] = value
		return sanitized


class PIIMasking:
	"""PII detection and masking"""
	PATTERNS = {
		'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
		'phone': r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,5}[-\s\.]?[0-9]{1,5}',
		'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
		'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
		'ip_address': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
	}

	@classmethod
	def mask_pii(cls, text: str) -> str:
		import re
		for name, pattern in cls.PATTERNS.items():
			text = re.sub(pattern, f'[REDACTED_{name.upper()}]', text)
		return text

	@classmethod
	def mask_dict(cls, data: dict, fields_to_mask: List[str] = None) -> dict:
		if fields_to_mask is None:
			fields_to_mask = ['password', 'token', 'secret', 'api_key', 'email', 'phone']
		masked = {}
		for key, value in data.items():
			if any(field in key.lower() for field in fields_to_mask):
				masked[key] = '[REDACTED]'
			elif isinstance(value, str):
				masked[key] = cls.mask_pii(value)
			elif isinstance(value, dict):
				masked[key] = cls.mask_dict(value, fields_to_mask)
			else:
				masked[key] = value
		return masked


class SecureTokenGenerator:
	"""Cryptographically secure token generation"""
	@staticmethod
	def generate_token(length: int = 32) -> str:
		return secrets.token_urlsafe(length)

	@staticmethod
	def generate_api_key() -> str:
		prefix = "sk_live_"
		token = secrets.token_hex(32)
		checksum = hashlib.sha256(token.encode()).hexdigest()[:8]
		return f"{prefix}{token}_{checksum}"

	@staticmethod
	def verify_api_key(api_key: str) -> bool:
		try:
			parts = api_key.rsplit('_', 1)
			if len(parts) != 2:
				return False
			key_part = parts[0].split('_', 2)[2]
			checksum = parts[1]
			expected = hashlib.sha256(key_part.encode()).hexdigest()[:8]
			return secrets.compare_digest(checksum, expected)
		except Exception:
			return False