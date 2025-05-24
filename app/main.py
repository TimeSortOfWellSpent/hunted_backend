import secrets
import string
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.exc import IntegrityError
import jwt
from fastapi.encoders import jsonable_encoder
from app.database import SessionDep, create_db_and_tables
from app.models import GameSession, GameSessionPublic, User, UserPublic, UserCreate, Participant
from typing import Annotated
from app.security import security, JWT_SECRET_KEY, ALGORITHM
from app.dependencies import UserDep, UUIDDep
from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import select
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield
app = FastAPI(lifespan=lifespan)

@app.post("/sessions/", response_model=GameSessionPublic)
def create_lobby(
        session: SessionDep,
        user: UserDep
    ):
    for _ in range(5):
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        game_session_db = GameSession(owner=user, code=code)
        session.add(game_session_db)
        try:
            session.commit()
            session.refresh(game_session_db)
            return game_session_db
        except IntegrityError:
            session.rollback()

    raise HTTPException(status_code=500, detail="Could not generate a unique lobby code")

@app.get("/sessions/")
def get_lobbies(
        session: SessionDep
    ):
    return session.exec(select(GameSession)).all()
@app.post("/users/")
def create_user(
        session: SessionDep,
        user: UserCreate,
        uuid: UUIDDep,
    ):

    user_db = User.model_validate(user, update={"id": uuid})
    session.add(user_db)
    try:
        session.commit()
        session.refresh(user_db)
    except IntegrityError:
        raise HTTPException(status_code=403, detail="User with this id already exists")
    to_encode = {"uuid": jsonable_encoder(uuid)}
    token = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

@app.post("/sessions/{code}/participants")
def join_session(
        session: SessionDep,
        code: str,
        user: UserDep
    ):
    game_session = session.exec(select(GameSession).where(GameSession.code == code)).first()
    if game_session is None:
        raise HTTPException(status_code=404, detail="Game session not found")
    if user.id == game_session.owner_id:
        raise HTTPException(status_code=403, detail="You can not join a session you created")
    participant_db = Participant(user=user, game_session=game_session)
    session.add(participant_db)
    session.commit()
    session.refresh(participant_db)
    return participant_db