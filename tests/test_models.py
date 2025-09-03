# tests/test_models.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from datetime import UTC
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text


def test_user_password_hashing_and_check(db):
    from tipple.models import User
    u = User(email="t@example.com", username="tester", bio=None)
    u.set_password("secret")
    db.session.add(u); db.session.commit()

    assert u.password_hash and u.check_password("secret") is True
    assert u.check_password("nope") is False


def test_user_unique_constraints(db):
    from tipple.models import User
    u1 = User(email="dup@example.com", username="dupuser")
    u1.set_password("x")
    db.session.add(u1); db.session.commit()

    # duplicate email
    u2 = User(email="dup@example.com", username="other")
    u2.set_password("y")
    db.session.add(u2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # duplicate username
    u3 = User(email="other@example.com", username="dupuser")
    u3.set_password("z")
    db.session.add(u3)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_channel_parent_child_relationship(db):
    from tipple.models import Channel
    parent = Channel(name="General")
    child = Channel(name="Announcements")
    child.parent = parent

    db.session.add_all([parent, child]); db.session.commit()

    assert child.parent_id == parent.id
    assert parent in (child.parent,)
    assert any(c.id == child.id for c in parent.children)


def test_post_belongs_to_user_and_channel(db):
    from tipple.models import User, Channel, Post
    u = User(email="x@y.z", username="xy")
    u.set_password("pw")
    ch = Channel(name="dev")

    p = Post(body="hello", tags="intro")
    p.author = u
    p.channel = ch

    db.session.add_all([u, ch, p]); db.session.commit()

    assert p.id is not None
    assert p.user_id == u.id
    assert p.channel_id == ch.id
    assert any(pp.id == p.id for pp in u.posts)
    assert any(pp.id == p.id for pp in ch.posts)


def test_post_created_at_default_is_recent(db):
    from tipple.models import User, Channel, Post
    u = User(email="recent@example.com", username="recent")
    u.set_password("pw")
    ch = Channel(name="random")
    p = Post(body="timestamp check", tags=None)
    p.author = u
    p.channel = ch

    db.session.add_all([u, ch, p]); db.session.commit()
    p_ts = p.created_at.replace(tzinfo=timezone.utc)

    assert isinstance(p.created_at, datetime)
    assert datetime.now(UTC) - p_ts < timedelta(seconds=5)


def test_post_not_null_constraints(db):
    from tipple.models import User, Channel, Post
    u = User(email="nn@example.com", username="nn")
    u.set_password("pw")
    ch = Channel(name="nn-chan")
    db.session.add_all([u, ch]); db.session.commit()

    # missing body
    bad1 = Post(body=None, tags=None)  # type: ignore[arg-type]
    bad1.author = u
    bad1.channel = ch
    db.session.add(bad1)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # missing author (user)
    bad2 = Post(body="no user", tags=None)
    bad2.channel = ch
    db.session.add(bad2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # missing channel
    bad3 = Post(body="no channel", tags=None)
    bad3.author = u
    db.session.add(bad3)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_delete_user_cascades_posts(db):
    """DB-level FK cascade on users.id -> posts.user_id."""
    from tipple.models import User, Channel, Post
    # Ensure SQLite enforces FKs in tests
    db.session.execute(text("PRAGMA foreign_keys=ON"))

    u = User(email="cas@example.com", username="cas")
    u.set_password("pw")
    ch = Channel(name="cascade")
    db.session.add_all([u, ch]); db.session.commit()

    p1 = Post(body="one", tags=None); p1.author = u; p1.channel = ch
    p2 = Post(body="two", tags="x");  p2.author = u; p2.channel = ch
    db.session.add_all([p1, p2]); db.session.commit()

    from tipple.models import Post as PostModel
    assert PostModel.query.count() == 2

    db.session.delete(u); db.session.commit()
    assert PostModel.query.count() == 0


def test_delete_channel_cascades_posts(db):
    """DB-level FK cascade on channels.id -> posts.channel_id."""
    from tipple.models import User, Channel, Post
    db.session.execute(text("PRAGMA foreign_keys=ON"))

    u = User(email="cc@example.com", username="cc")
    u.set_password("pw")
    ch = Channel(name="to-delete")
    db.session.add_all([u, ch]); db.session.commit()

    p = Post(body="will vanish", tags=None); p.author = u; p.channel = ch
    db.session.add(p); db.session.commit()

    from tipple.models import Post as PostModel
    assert PostModel.query.count() == 1

    db.session.delete(ch); db.session.commit()
    assert PostModel.query.count() == 0


@pytest.mark.parametrize("use_collection", [True, False])
def test_channel_children_delete_orphan_semantics(db, use_collection):
    """
    Self-referential: removing child from parent's children should delete-orphan
    only if relationship is configured with delete-orphan+single_parent.
    We assert the association semantics (child loses parent), and if the ORM
    is configured to delete orphans, it should disappear; otherwise it remains.
    """
    from tipple.models import Channel
    parent = Channel(name="parent")
    child = Channel(name="child")
    if use_collection:
        parent.children.append(child)
    else:
        child.parent = parent
    db.session.add(parent); db.session.commit()

    # Remove link
    parent.children.remove(child) if use_collection else setattr(child, "parent", None)
    db.session.commit()

    # Child either deleted (delete-orphan) or still exists without parent.
    exists = db.session.get(Channel, child.id) is not None
    # In both cases, parent no longer lists child:
    assert all(c.id != child.id for c in parent.children)
    # We don't assert exact deletion to avoid coupling to a specific cascade policy.


def test_user_following_m2m_if_present(db):
    """
    If the m2m 'following' exists, verify basic add/idempotency.
    If not present in this build, skip gracefully.
    """
    from tipple.models import User, Channel
    u = User(email="m2m@example.com", username="m2m"); u.set_password("pw")
    ch = Channel(name="news")
    db.session.add_all([u, ch]); db.session.commit()

    if not hasattr(u, "following") or not hasattr(ch, "followers"):
        pytest.skip("following/followers m2m not configured in this build")

    # follow once
    u.following.append(ch); db.session.commit()
    assert ch in u.following
    assert u in ch.followers

    # idempotent add (composite PK prevents duplicates)
    u.following.append(ch)
    db.session.commit()
    assert [c.id for c in u.following].count(ch.id) == 1
