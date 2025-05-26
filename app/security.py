import secrets
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
#key rotation would be nice
JWT_SECRET_KEY = "this is a placeholder jwt secret key"
ALGORITHM = "HS256"
security = HTTPBearer()