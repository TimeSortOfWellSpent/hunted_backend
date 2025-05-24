import secrets
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
#key rotation would be nice
JWT_SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
security = HTTPBearer()