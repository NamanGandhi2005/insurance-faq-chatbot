# app/utils/limiter.py
from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize the limiter using the client's IP address as the key
limiter = Limiter(key_func=get_remote_address)