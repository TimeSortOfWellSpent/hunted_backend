from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel
from typing import Optional
from uuid import UUID

class UserBase(SQLModel):
    username: str
    photo_path: str = ""

class User(UserBase, table=True):
    __tablename__ = "user"

    id: UUID | None = Field(default=None, primary_key=True)
    participations: list["Participant"] = Relationship(back_populates="user")
    owned_game_sessions: list["GameSession"] = Relationship(back_populates="owner")

class UserCreate(UserBase):
    pass

class UserPublic(UserBase):
    pass

class GameSessionBase(SQLModel):
    pass

class GameSession(GameSessionBase, table=True):
    __tablename__ = "game_session"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    owner_id: UUID | None = Field(default=None, foreign_key="user.id")
    owner: User | None = Relationship(back_populates="owned_game_sessions")
    eliminations: list["Elimination"] = Relationship(back_populates="game_session")
    participants: list["Participant"] = Relationship(back_populates="game_session")
    created_at: datetime = datetime.now()
    started_at: datetime | None
    ended_at: datetime | None

class GameSessionCreate(GameSessionBase):
    owner_id: UUID

class GameSessionPublic(GameSessionBase):
    code: str


class Participant(SQLModel, table=True):
    __tablename__ = "participant"

    id: int | None = Field(default=None, primary_key=True)
    user_id: UUID | None = Field(default=None, foreign_key="user.id")
    user: User | None = Relationship(back_populates="participations")
    game_session_id: int | None = Field(default=None, foreign_key="game_session.id")
    game_session: Optional["GameSession"] = Relationship(back_populates="participants")
    eliminations_made: list["Elimination"] = Relationship(
        back_populates="eliminator",
        sa_relationship_kwargs={"foreign_keys": "[Elimination.eliminator_id]"}
    )
    elimination_received: Optional["Elimination"] = Relationship(
        back_populates="eliminated",
        sa_relationship_kwargs={
            "foreign_keys": "[Elimination.eliminated_id]",
            "uselist": False
        }
    )
    target_id: int | None = Field(default=None, foreign_key="participant.id")
    target: Optional["Participant"] = Relationship(
        sa_relationship_kwargs={
            'uselist': False,
            'remote_side': "[Participant.id]"
        },
        back_populates="targeted_by"
    )
    targeted_by: Optional["Participant"] = Relationship(
        sa_relationship_kwargs={'uselist': False},
        back_populates="target"
    )

class Elimination(SQLModel, table=True):
    __tablename__ = "elimination"

    id: int | None = Field(default=None, primary_key=True)
    game_session_id: int | None = Field(default=None, foreign_key="game_session.id")
    game_session: GameSession | None = Relationship(back_populates="eliminations")
    eliminator_id: int | None = Field(default=None, foreign_key="participant.id")
    eliminator: Participant | None = Relationship(
        back_populates="eliminations_made",
        sa_relationship_kwargs={"foreign_keys": "[Elimination.eliminator_id]"}
    )

    eliminated_id: int | None = Field(default=None, foreign_key="participant.id")
    eliminated: Optional["Participant"] = Relationship(
        sa_relationship_kwargs={
            "uselist": False,
            "foreign_keys": "[Elimination.eliminated_id]",
        },
        back_populates="elimination_received"
    )
    happened_at: datetime = datetime.now()