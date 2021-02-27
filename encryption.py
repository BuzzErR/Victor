from cryptography.fernet import Fernet
import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def key_generation(user_id, password):
    password = password.encode()    # Convert to type bytes
    salt = bytes(user_id, 'utf-8') 
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password))   # Can only use kdf once


def encrypt(filename, user_id, password):
    key = key_generation(user_id, password)
    with open(filename, 'rb') as f:
        data = f.read()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data)
    with open(filename, 'wb') as f:
        f.write(encrypted)
    

def decrypt(filename, path, user_id, password):
    key = key_generation(user_id, password)
    with open(path, 'rb') as f:
        data = f.read()
    f.close()
    fernet = Fernet(key)
    encrypted = fernet.decrypt(data)
    with open(filename, 'wb') as f:
        f.write(encrypted)
    f.close()
