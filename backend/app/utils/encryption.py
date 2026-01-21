# app/utils/encryption.py
from cryptography.fernet import Fernet
from fastapi import HTTPException, status
from ..config import settings

# Initialize Fernet with the encryption key
try:
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
except (ValueError, TypeError) as e:
    # Handle cases where the key is invalid
    # In a real application, you'd want to log this error and prevent the app from starting
    # if the key is essential for operation.
    raise RuntimeError(f"Invalid ENCRYPTION_KEY: {e}")

def encrypt_id(id_to_encrypt: int) -> str:
    """Encrypts an integer ID."""
    if not isinstance(id_to_encrypt, int):
        raise TypeError("ID must be an integer.")
    
    return fernet.encrypt(str(id_to_encrypt).encode()).decode()

def decrypt_id(encrypted_id: str) -> int:
    """Decrypts an encrypted ID string back to an integer."""
    try:
        decrypted_bytes = fernet.decrypt(encrypted_id.encode())
        return int(decrypted_bytes.decode())
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted ID.",
        )
