from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Participant


def get_player_count(session: Session, game_session_id: int) -> int:
    return session.exec(
        select(func.count(Participant.id))
        .where(Participant.game_session_id == game_session_id)
        .where(Participant.target is not None)
    ).one()
