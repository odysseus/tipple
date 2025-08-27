# tests/test_models.py
from tipple.models import User, Post
from werkzeug.security import check_password_hash


def test_user_password_hashing(db):
    u = User(email="x@y.z", username="xy")
    u.set_password("hunter2")
    db.session.add(u); db.session.commit()
    assert u.password_hash and check_password_hash(u.password_hash, "hunter2")


def test_post_relationship(db):
    u = User(email="p@q.r", username="pq")
    u.set_password("pw")
    db.session.add(u); db.session.commit()

    p = Post(user_id=u.id, body="rel test", tags="x")
    db.session.add(p); db.session.commit()

    # backref via .author
    assert p.author.id == u.id
    # relationship on user
    assert u.posts.count() == 1
