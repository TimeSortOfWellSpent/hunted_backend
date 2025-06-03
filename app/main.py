import io
import secrets, string, jwt, random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

import boto3
from sqlalchemy.exc import IntegrityError
from fastapi.encoders import jsonable_encoder

from app.config import settings
from app.database import SessionDep, create_db_and_tables
from app.models import GameSession, GameSessionPublic, User, UserPublic, Participant, GameStatus, \
    GameSessionStatusUpdate, Elimination
from app.security import JWT_SECRET_KEY, ALGORITHM
from app.dependencies import UserDep, UUIDDep, GameSessionDep, ParticipantDep
from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from sqlmodel import select
from app.storage import upload_file, get_file
from deepface import DeepFace
import numpy as np
from PIL import Image
import cv2
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield
app = FastAPI(lifespan=lifespan)

@app.post("/sessions/", response_model=GameSessionPublic)
def create_session(
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
def get_sessions(
        session: SessionDep
    ):
    return session.exec(select(GameSession)).all()
@app.post("/users/", status_code=201)
def create_user(
        session: SessionDep,
        username: Annotated[str, Form()],
        photo: Annotated[UploadFile, File()],
        uuid: UUIDDep,
    ):
    filename = upload_file(photo)
    user_db = User(username=username, id=uuid, photo_path=filename)
    session.add(user_db)
    try:
        session.commit()
        session.refresh(user_db)
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=403, detail="User with this id already exists")
    to_encode = {"uuid": jsonable_encoder(uuid)}
    token = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

@app.post("/sessions/{code}/participants", status_code=201)
def join_session(
        session: SessionDep,
        user: UserDep,
        game_session: GameSessionDep
    ):
    if user.id == game_session.owner_id:
        raise HTTPException(status_code=403, detail="You can not join a session you created")
    if game_session.status != GameStatus.NOT_STARTED:
        raise HTTPException(status_code=403, detail="The session is either already started or has already ended")
    participant_db = Participant(user=user, game_session=game_session)
    session.add(participant_db)
    try:
        session.commit()
        session.refresh(participant_db)
        return participant_db
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=403, detail="You have already joined this session")

@app.delete("/sessions/{code}/participants")
def leave_session(
        session: SessionDep,
        user: UserDep,
        game_session: GameSessionDep
    ):
    participant = session.exec(select(Participant).where(Participant.game_session == game_session).where(Participant.user == user)).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    session.delete(participant)
    session.commit()
    return {"ok": True}

@app.patch("/sessions/{code}")
def update_session_status(
        session: SessionDep,
        user: UserDep,
        status: GameSessionStatusUpdate,
        game_session: GameSessionDep
    ):
    if game_session.owner != user:
        raise HTTPException(status_code=403, detail="You are not the owner of the session")
    if game_session.status == GameStatus.FINISHED:
        raise HTTPException(status_code=403, detail="The session has already finished")
    elif game_session.status == GameStatus.NOT_STARTED:
        if status.status == GameStatus.FINISHED:
            raise HTTPException(status_code=403, detail="The session has not been started yet")
        if len(game_session.participants) >= 2:
            assign_targets(game_session.participants)
            game_session.sqlmodel_update({"started_at": datetime.now()})
    elif game_session.status == GameStatus.IN_PROGRESS:
        if status.status == GameStatus.FINISHED:
            game_session.sqlmodel_update({"ended_at":datetime.now()})
    session.add(game_session)
    session.commit()
    session.refresh(game_session)
    return game_session

def assign_targets(participants: list[Participant]):
    shuffled = participants.copy()
    random.shuffle(shuffled)
    for i, participant in enumerate(shuffled):
        next_participant = shuffled[(i + 1) % len(shuffled)]
        participant.target_id = next_participant.id

@app.post("/sessions/{code}/eliminations", status_code=201)
def create_elimination(
        session: SessionDep,
        participant: ParticipantDep,
        photo: Annotated[UploadFile, File()],
    ):
    img = Image.open(photo.file)
    if img.mode != 'RGB':
        img = img.convert('RGB')

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=75, optimize=True)
    photo_bytes = buffer.getvalue()
    client = boto3.client('rekognition', region_name='eu-central-1')
    response = client.compare_faces(
        SourceImage={"S3Object": {"Bucket": settings.bucket_name, "Name": participant.target.user.photo_path}},
        TargetImage={"Bytes": photo_bytes},
        SimilarityThreshold=80
    )
    if len(response['FaceMatches']) == 0:
        return {"response": "This is not the same person!"}

    elimination_db = Elimination(game_session=participant.game_session, eliminator=participant, eliminated=participant.target)
    participant.target = participant.target.target
    session.add(elimination_db)
    session.add(participant)
    try:
        session.commit()
        session.refresh(elimination_db)
        return {"new_target": participant.target_id}
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=403, detail="This elimination already exists")