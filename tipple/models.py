# tipple/models.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any, TYPE_CHECKING

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import (
    DeclarativeBase, MappedAsDataclass, Mapped, mapped_column, relationship
)
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class Base(MappedAsDataclass, DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, repr=False, init=False)
    bio: Mapped[Optional[str]] = mapped_column(String(256), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                nullable=False, init=False)

    # IMPORTANT: list-based relationship + matching back_populates on Post.author
    posts: Mapped[List["Post"]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
        init=False,
    )

    # --- type-only init: seen by Pyright, ignored at runtime ---
    if TYPE_CHECKING:
        def __init__(
            self,
            *,
            email: str,
            username: str,
            bio: Optional[str] = ...,
            # If you REQUIRE callers to pass a hash, include this:
            # password_hash: str = ...,
            **kw: Any,
        ) -> None: ...

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Post(db.Model):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    # IMPORTANT: correct FK target must match __tablename__ ("users.id")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        index=True, 
        nullable=False, 
        init=False,
    )
    body: Mapped[str] = mapped_column(String(255), nullable=False)
    tags: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                nullable=False, init=False)

    # Mirror side of the relationship
    author: Mapped["User"] = relationship(back_populates="posts", init=False)

    if TYPE_CHECKING:
        def __init__(
            self,
            *,
            body: str,
            tags: Optional[str] = ...,
            # allow either user_id or author at construction time
            user_id: Optional[int] = ...,
            author: Optional[User] = ...,
            **kw: Any,
        ) -> None: ...
