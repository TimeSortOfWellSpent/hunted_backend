from uuid import UUID
from typing import Annotated

import jwt

from fastapi import Depends, FastAPI, HTTPException, status
from jwt import InvalidTokenError
from sqlmodel import select, SQLModel
from app.models import User
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.database import SessionDep
from app.security import security, JWT_SECRET_KEY, ALGORITHM


def get_current_user(
        credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
        session: SessionDep
    ):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        uuid_s = payload.get("uuid")
        if uuid_s is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    try:
        uuid = UUID(uuid_s)
    except ValueError:
        raise credentials_exception
    user = session.exec(select(User).where(User.id == uuid)).first()
    if user is None:
        raise credentials_exception
    return user

def verify_uuid(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]):
    try:
        return UUID(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

UUIDDep = Annotated[UUID, Depends(verify_uuid)]
UserDep = Annotated[User, Depends(get_current_user)]