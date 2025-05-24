from uuid import UUID
from typing import Annotated, Final
import secrets, string

from fastapi import HTTPException

from app.database import engine, SessionDep
from app.models import GameSessionCreate, GameSession, User, UserCreate
from sqlmodel import select, SQLModel
from uuid import UUID

