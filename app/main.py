from contextlib import asynccontextmanager
from app.database import engine, SessionDep
from fastapi import Depends, FastAPI
from sqlmodel import SQLModel
from app.models import User, Session, Participant, Elimination
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield
app = FastAPI(lifespan=lifespan)

security = HTTPBearer()

@app.post("/users/")
def create_user(user: User, session: SessionDep, credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]):
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
@app.get("/users/")
def read_users(
        session: SessionDep,
        offset: int = 0,
        limit: Annotated[int, Query(le=100)] = 100
) -> list[User]:
    users = session.exec(select(User).offset(offset).limit(limit)).all()
    return users

@app.get("/uuid")
def read_user_credentials(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]):
    return credentials