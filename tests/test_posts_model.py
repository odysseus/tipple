# tests/test_posts_model.py
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_create_post_via_author_relationship(db, make_user):
    from tipple.models import Post

    u = make_user()
    p = Post(body="hello world", tags="intro,example")
    p.author = u  # set via relationship
    db.session.add(p)
    db.session.commit()

    assert p.id is not None
    assert p.user_id == u.id
    assert p.author is u
    # User side populated
    assert any(pp.id == p.id for pp in u.posts)


def test_create_post_via_parent_collection(db, make_user):
    from tipple.models import Post

    u = make_user()
    u.posts.append(Post(body="via collection", tags=None))
    db.session.commit()

    assert len(u.posts) == 1
    created = u.posts[0]
    assert created.user_id == u.id
    assert created.tags is None


def test_delete_orphan_on_remove_from_collection(db, make_user):
    from tipple.models import Post

    u = make_user()
    p = Post(body="to be removed", tags=None)
    u.posts.append(p)
    db.session.commit()
    assert len(u.posts) == 1

    # Remove child from collection -> delete-orphan should delete it on commit
    u.posts.remove(p)
    db.session.commit()

    # Confirm it's gone
    assert len(u.posts) == 0
    assert Post.query.count() == 0


def test_not_null_constraints(db, make_user):
    from tipple.models import Post

    u = make_user()

    # Missing body -> NOT NULL should fail on commit
    p = Post(body=None, tags=None) # type: ignore
    p.author = u
    db.session.add(p)  
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # Missing user_id/author -> NOT NULL should fail on commit
    db.session.add(Post(body="no user", tags=None))  # no author set
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_created_at_default_is_recent(db, make_user):
    from tipple.models import Post

    u = make_user()
    p = Post(body="timestamp", tags=None)
    p.author = u

    db.session.add(p)
    db.session.commit()

    assert isinstance(p.created_at, datetime)
    assert datetime.utcnow() - p.created_at < timedelta(seconds=5)


def test_repr_contains_identifiers(db, make_user):
    from tipple.models import Post

    u = make_user()
    p = Post(body="repr check", tags=None)
    p.author = u

    db.session.add(p)
    db.session.commit()

    r = repr(p)
    assert "Post" in r or "post" in r
    assert str(p.id) in r
    assert str(p.user_id) in r


def test_delete_user_cascades_posts_when_fk_enabled(db, make_user):
    """
    If your model uses passive_deletes=True + FK ondelete=CASCADE, enable SQLite FKs
    so DB-level cascade works in tests. This is optional but nice to verify.
    """
    from tipple.models import Post, User

    # Enable SQLite FK enforcement on THIS connection/session
    db.session.execute(text("PRAGMA foreign_keys=ON"))

    u = make_user()
    u.posts.append(Post(body="p1", tags=None))
    u.posts.append(Post(body="p2", tags="x"))
    db.session.commit()

    assert Post.query.count() == 2

    db.session.delete(u)
    db.session.commit()

    # With FK cascade active, children are removed by the DB
    assert Post.query.count() == 0
    assert User.query.count() == 0
