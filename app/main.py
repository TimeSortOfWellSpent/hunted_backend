import secrets, string, jwt, random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated
from sqlalchemy.exc import IntegrityError
from fastapi.encoders import jsonable_encoder
from app.database import SessionDep, create_db_and_tables
from app.models import GameSession, GameSessionPublic, User, Participant, GameStatus, \
    GameSessionStatusUpdate, Elimination, ParticipantPublic
from app.dependencies import UserDep, UUIDDep, GameSessionDep, ParticipantDep
from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from sqlmodel import select
from app.config import settings
from app.storage import upload_file, compare_faces, generate_presigned_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/sessions/")
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
            return {"code": code}
        except IntegrityError:
            session.rollback()

    raise HTTPException(status_code=500, detail="Could not generate a unique lobby code")


@app.get("/sessions/{code}", response_model=GameSessionPublic)
def get_session(
        session: SessionDep,
        participant: ParticipantDep,
):
    query = (
        select(User.username)
        .join(Participant, Participant.user_id == User.id)
        .where(Participant.game_session_id == participant.game_session_id)
    )
    
    if participant.game_session.status != GameStatus.NOT_STARTED:
        query = query.where(Participant.target_id.isnot(None))
    
    players = session.exec(query).all()
    target = None
    if participant.target is not None:
        url = generate_presigned_url(participant.target.user.photo_path)
        target = ParticipantPublic(
            username=participant.target.user.username,
            photo_url=url,
        )
    return GameSessionPublic(
        players=players,
        status=participant.game_session.status,
        target=target
    )


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
    token = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.algorithm)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/sessions/{code}/participants", status_code=201)
def join_session(
        session: SessionDep,
        user: UserDep,
        game_session: GameSessionDep
):
    # if user.id == game_session.owner_id:
    #     raise HTTPException(status_code=403, detail="You can not join a session you created")
    if game_session.status != GameStatus.NOT_STARTED:
        raise HTTPException(status_code=403, detail="The session is either already started or has already ended")
    participant_db = Participant(user=user, game_session=game_session)
    session.add(participant_db)
    try:
        session.commit()
        session.refresh(participant_db)
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=403, detail="You have already joined this session.")


@app.delete("/sessions/{code}/participants", status_code=204)
def leave_session(
        session: SessionDep,
        user: UserDep,
        game_session: GameSessionDep,
        username: str | None = None
):
    if game_session.status != GameStatus.NOT_STARTED:
        raise HTTPException(status_code=403, detail="Game has already started or ended.")
    if game_session.owner == user:
        if not username:
            raise HTTPException(status_code=400, detail="Username must be provided.")
        stmt = (
            select(Participant)
            .join(Participant.user)
            .where(Participant.game_session_id == game_session.id)
            .where(User.username == username)
        )
    else:
        stmt = (
            select(Participant)
            .where(Participant.game_session_id == game_session.id)
            .where(Participant.user_id == user.id)
        )
    participant = session.exec(stmt).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    session.delete(participant)
    session.commit()


@app.patch("/sessions/{code}", response_model=GameSessionPublic)
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
            game_session.sqlmodel_update({"ended_at": datetime.now()})
    session.add(game_session)
    session.commit()
    session.refresh(game_session)
    players = session.exec(
        select(User.username)
        .join(Participant, Participant.user_id == User.id)
        .where(Participant.game_session_id == game_session.id)
        .where(Participant.target_id.isnot(None))
    ).all()
    return GameSessionPublic(
        players=players,
        status=game_session.status,
    )


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
    response = compare_faces(participant.target.user.photo_path, photo)
    if not response:
        raise HTTPException(status_code=400, detail="Face verification failed.")

    active_players = session.exec(
        select(Participant)
        .where(Participant.game_session_id == participant.game_session_id)
        .where(Participant.target_id.isnot(None))
    ).all()
    
    if len(active_players) <= 2:
        participant.game_session.ended_at = datetime.now()
        session.add(participant.game_session)
        try:
            session.commit()
            return {"status": "winner", "message": "You are the winner"}
        except IntegrityError:
            session.rollback()
            raise HTTPException(status_code=403, detail="Failed to end game")

    elimination_db = Elimination(
        game_session=participant.game_session,
        eliminator=participant,
        eliminated=participant.target
    )
    
    next_target = participant.target.target
    participant.target_id = next_target.id
    
    session.add(elimination_db)
    session.add(participant)
    
    try:
        session.commit()
        session.refresh(participant)
        
        url = generate_presigned_url(next_target.user.photo_path)
        return {
            "status": "continue",
            "message": "Elimination was successful",
            "target": ParticipantPublic(
                username=next_target.user.username,
                photo_url=url,
            )
        }
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=403, detail="This elimination already exists")
