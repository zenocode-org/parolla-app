import hashlib
import os

def hash_password(password):
    salt=os.getenv('SALT_PASSWORD')
    if salt:
        hashed_password = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    
        return hashed_password.hex()

