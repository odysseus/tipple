# tipple/models.py
from __future__ import annotations
from datetime import datetime, UTC
from typing import Optional, List, Any, TYPE_CHECKING
import uuid

import sqlalchemy as sa
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy import event
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import (
    DeclarativeBase, MappedAsDataclass, Mapped, mapped_column, relationship,
    Session, attributes
)
from sqlalchemy.exc import IntegrityError

from flask.signals import appcontext_pushed
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(UTC),
                                                nullable=False, init=False)

    # IMPORTANT: list-based relationship + matching back_populates on Post.author
    posts: Mapped[List["Post"]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
        init=False,
    )

    following: Mapped[List["Channel"]] = relationship(
        secondary="user_channel_follows",
        back_populates="followers",
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
    
    # NEW: required channel FK (init=False so constructor doesn’t demand it)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        init=False,
    )
    channel: Mapped["Channel"] = relationship(back_populates="posts", init=False)

    
    body: Mapped[str] = mapped_column(String(255), nullable=False)
    tags: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(UTC),
                                                nullable=False, init=False)

    author: Mapped["User"] = relationship(back_populates="posts", init=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Post {self.id} user_id={self.user_id} channel_id={self.channel_id}>"

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

# tipple/models.py (add alongside your other models)
class Channel(db.Model):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        init=False
    )

    # Required channel name (max 255 chars)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Self-referential parent (nullable)
    parent_id: Mapped[Optional[int | None]] = mapped_column(
        ForeignKey("channels.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        init=False,          # ORM fills from relationship
    )

    parent: Mapped[Optional["Channel"]] = relationship(
        back_populates="children",
        remote_side="Channel.id",   # tells SQLA which side is the parent
        init=False,
    )

    # Children collection
    children: Mapped[List["Channel"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        single_parent=True,         # required for delete-orphan on self-ref
        passive_deletes=True,
        init=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now(UTC),
        nullable=False,
        init=False,
    )

    followers: Mapped[List["User"]] = relationship(
        secondary="user_channel_follows",
        back_populates="following",
        init=False,
    )

    posts: Mapped[List["Post"]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
        passive_deletes=True,
        init=False,
    )

    # NEW: Path of ancestor channel IDs (root -> parent), excludes self.
    # Uses JSON type which SQLite stores as TEXT. 
    path: Mapped[List[int]] = mapped_column(
        "path",
        MutableList.as_mutable(JSON),
        insert_default=list,
        nullable=False,
        init=False,
    )

    if TYPE_CHECKING:
        def __init__(
            self,
            *,
            name: str,
            id: Optional[int] = ...,
            parent_if: Optional[int] = ...,
            parent: Optional[Channel] = ...,
            children: Optional[List[Channel]] = ...,
            created_at: Optional[datetime] = ...,
            followers: Optional[List[User]] = ...,
            **kw: Any,
        ) -> None: ...

    
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Channel {self.id} name={self.name!r} parent_id={self.parent_id!r}>"


def _compute_path_ids(ch: "Channel") -> list[int]:
    """
    Build ancestor id list from root -> parent (excludes self).
    Guards against accidental cycles and limits depth.
    """
    ids: list[int] = []
    seen: set[int] = set()
    current = ch.parent
    for _ in range(50):            # reasonable safety cap
        if current is None:
            break
        if current.id is None:
            # parent not flushed yet; fall back to current DB value via parent_id
            # (will correct on the same flush once IDs exist)
            break
        if current.id in seen:
            break                  # cycle guard
        ids.append(current.id)
        seen.add(current.id)
        current = current.parent
    return list(reversed(ids))


@event.listens_for(Session, "before_flush")
def _update_channel_paths(session: Session, flush_context, instances):
    """
    For new channels, or channels whose parent changed, recompute .path.
    Also update descendants if a node was reparented.
    """
    # Gather affected channels
    targets: list[Channel] = []
    for obj in session.new.union(session.dirty):
        if isinstance(obj, Channel):
            if obj in session.new:
                targets.append(obj)
            else:
                hist = attributes.get_history(obj, "parent_id", passive=True)
                if hist.has_changes():
                    targets.append(obj)

    if not targets:
        return

    # Recompute for each target and all its descendants
    for ch in targets:
        ch.path = _compute_path_ids(ch)

        # Propagate to descendants (their ancestor chain changed too)
        stack = list(getattr(ch, "children", []) or [])
        # Limit breadth/depth to avoid surprises on pathological graphs
        visited: set[int] = set()
        while stack:
            child = stack.pop()
            if child.id and child.id in visited:
                continue
            child.path = _compute_path_ids(child)
            visited.add(child.id or id(child))
            stack.extend(child.children or [])

        
user_channel_follows = sa.Table(
    "user_channel_follows",
    db.metadata,
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    # Optional: helpful index for reverse lookups
    sa.Index("ix_ucf_channel_id", "channel_id"),
    sa.Index("ix_ucf_user_id", "user_id"),
)
