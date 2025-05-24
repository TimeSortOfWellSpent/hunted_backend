import datetime

from pydantic import EmailStr, BaseModel, Field
from sqlmodel import Field, Relationship, SQLModel
from typing import Optional
from uuid import UUID

class User(SQLModel, table=True):
    id: UUID | None = Field(default=None, primary_key=True)
    username: str
    photo_path: str | None = ""
    sessions: list["Session"] = Relationship(back_populates="owner")

class Session(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str
    owner_id: int | None = Field(default=None, foreign_key="user.id")
    owner: User | None = Relationship(back_populates="sessions")
    eliminations: list["Elimination"] = Relationship(back_populates="session")
    participants: list["Participant"] = Relationship(back_populates="session")
    created_at: datetime.datetime
    started_at: datetime.datetime | None
    ended_at: datetime.datetime | None

class Participant(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_id: int | None = Field(default=None, foreign_key="session.id")
    session: Session | None = Relationship(back_populates="participants")
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
    id: int | None = Field(default=None, primary_key=True)
    session_id: int | None = Field(default=None, foreign_key="session.id")
    session: Session | None = Relationship(back_populates="eliminations")
    eliminator_id: int | None = Field(default=None, foreign_key="participant.id")
    eliminator: Participant | None = Relationship(
        back_populates="eliminations_made",
        sa_relationship_kwargs={"foreign_keys": "[Elimination.eliminator_id]"}
    )

    eliminated_id:int| None = Field(default=None, foreign_key="participant.id")
    eliminated: Optional["Participant"] = Relationship(
        sa_relationship_kwargs={
            "uselist": False,
            "foreign_keys": "[Elimination.eliminated_id]",
        },
        back_populates="elimination_received"
    )
    happened_at: datetime.datetime | None