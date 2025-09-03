# tests/test_posts_model.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text


def test_create_post_via_relationships(db, make_user, make_channel):
    from tipple.models import Post
    u = make_user(email="p1@example.com", username="p1")
    ch = make_channel("dev")

    p = Post(body="hello world", tags="intro,example")
    p.author = u
    p.channel = ch

    db.session.add(p)
    db.session.commit()

    assert p.id is not None
    assert p.user_id == u.id
    assert p.channel_id == ch.id
    # backrefs
    assert any(pp.id == p.id for pp in u.posts)
    assert any(pp.id == p.id for pp in ch.posts)


def test_create_post_via_parent_collections(db, make_user, make_channel):
    from tipple.models import Post
    u = make_user(email="p2@example.com", username="p2")
    ch = make_channel("random")

    with db.session.no_autoflush:
        p = Post(body="via collections", tags=None)
        u.posts.append(p)   # sets user_id (no flush yet)
        ch.posts.append(p)  # sets channel_id (still no flush)

        db.session.commit()

    assert p.user_id == u.id
    assert p.channel_id == ch.id
    assert p.tags is None



def test_created_at_default_is_recent(db, make_user, make_channel):
    from tipple.models import Post
    u = make_user(email="time@example.com", username="time")
    ch = make_channel("clock")

    p = Post(body="timestamp check", tags=None)
    p.author = u
    p.channel = ch
    db.session.add(p); db.session.commit()
    p_ts = p.created_at.replace(tzinfo=timezone.utc)

    assert isinstance(p.created_at, datetime)
    assert datetime.now(UTC) - p_ts < timedelta(seconds=5)


def test_not_null_constraints(db, make_user, make_channel):
    from tipple.models import Post
    u = make_user(email="nn@example.com", username="nn")
    ch = make_channel("nn-chan")

    # Missing body -> NOT NULL should fail
    bad1 = Post(body=None, tags=None)  # type: ignore[arg-type]
    bad1.author = u; bad1.channel = ch
    db.session.add(bad1)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # Missing author/user -> NOT NULL should fail
    bad2 = Post(body="no user", tags=None)
    bad2.channel = ch
    db.session.add(bad2)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # Missing channel -> NOT NULL should fail
    bad3 = Post(body="no channel", tags=None)
    bad3.author = u
    db.session.add(bad3)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_repr_contains_identifiers(db, make_user, make_channel):
    from tipple.models import Post
    u = make_user(email="repr@example.com", username="repr")
    ch = make_channel("repr-chan")
    p = Post(body="repr check", tags=None)
    p.author = u; p.channel = ch
    db.session.add(p); db.session.commit()

    r = repr(p)
    assert "Post" in r or "post" in r
    assert str(p.id) in r
    assert str(p.user_id) in r
    assert str(p.channel_id) in r


def test_delete_user_cascades_posts(db, make_user, make_channel):
    """FK on posts.user_id should cascade when the user is deleted."""
    from tipple.models import Post, User
    db.session.execute(text("PRAGMA foreign_keys=ON"))  # for SQLite

    u = make_user(email="casu@example.com", username="casu")
    ch = make_channel("cascade-u")
    p1 = Post(body="one", tags=None); p1.author = u; p1.channel = ch
    p2 = Post(body="two", tags="x");  p2.author = u; p2.channel = ch
    db.session.add_all([p1, p2]); db.session.commit()

    assert Post.query.count() == 2
    db.session.delete(u); db.session.commit()
    assert Post.query.count() == 0
    assert User.query.count() == 0


def test_delete_channel_cascades_posts(db, make_user, make_channel):
    """FK on posts.channel_id should cascade when the channel is deleted."""
    from tipple.models import Post, Channel
    db.session.execute(text("PRAGMA foreign_keys=ON"))  # for SQLite

    u = make_user(email="casc@example.com", username="casc")
    ch = make_channel("to-delete")
    p = Post(body="will vanish", tags=None); p.author = u; p.channel = ch
    db.session.add(p); db.session.commit()

    assert Post.query.count() == 1
    db.session.delete(ch); db.session.commit()
    assert Post.query.count() == 0
    assert Channel.query.filter_by(name="to-delete").count() == 0


def test_query_by_user_and_channel_filters(db, make_user, make_channel):
    """Sanity check simple filtering by FKs."""
    from tipple.models import Post
    u1 = make_user(email="a@example.com", username="a")
    u2 = make_user(email="b@example.com", username="b")
    ch1 = make_channel("alpha")
    ch2 = make_channel("beta")

    p1 = Post(body="A in alpha", tags=None); p1.author = u1; p1.channel = ch1
    p2 = Post(body="A in beta", tags=None);  p2.author = u1; p2.channel = ch2
    p3 = Post(body="B in beta", tags=None);  p3.author = u2; p3.channel = ch2
    db.session.add_all([p1, p2, p3]); db.session.commit()

    # by user
    a_posts = Post.query.filter_by(user_id=u1.id).all()
    assert {p.body for p in a_posts} == {"A in alpha", "A in beta"}

    # by channel
    beta_posts = Post.query.filter_by(channel_id=ch2.id).all()
    assert {p.body for p in beta_posts} == {"A in beta", "B in beta"}
