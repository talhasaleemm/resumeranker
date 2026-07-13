import hashlib
import hmac
import os
import json
from cryptography.fernet import Fernet

def get_encryption_key() -> bytes:
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY is not set in environment")
    return key.encode("utf-8")

def get_blind_index_key() -> bytes:
    key = os.environ.get("BLIND_INDEX_KEY")
    if not key:
        raise ValueError("BLIND_INDEX_KEY is not set in environment")
    return key.encode("utf-8")

def encrypt_text(plaintext: str | None) -> str | None:
    if not plaintext:
        return None
    f = Fernet(get_encryption_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")

def decrypt_text(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    f = Fernet(get_encryption_key())
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")

def encrypt_json(data: dict | list | None) -> str | None:
    if not data:
        return None
    return encrypt_text(json.dumps(data))

def decrypt_json(ciphertext: str | None) -> dict | list | None:
    if not ciphertext:
        return None
    decrypted = decrypt_text(ciphertext)
    return json.loads(decrypted) if decrypted else None

def compute_blind_index(value: str | None) -> str | None:
    if not value:
        return None
    key = get_blind_index_key()
    # Normalize to lowercase before hashing for case-insensitive lookup
    normalized_value = value.lower().strip()
    return hmac.new(key, normalized_value.encode("utf-8"), hashlib.sha256).hexdigest()
