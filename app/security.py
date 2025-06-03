import secrets
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
#key rotation would be nice
security = HTTPBearer()