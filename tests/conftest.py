# tests/conftest.py
import pytest

from tipple import create_app
from tipple.config_classes import TestingConfig
from tipple.models import db as _db

@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SERVER_NAME="localhost")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    yield _db


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def make_user(db, app):
    from tipple.models import User
    def _make(email="alice@example.com", username="alice", password="secret", bio="Just a friendly tippler"):
        u = User(email=email, username=username, bio=bio)
        u.set_password(password)
        db.session.add(u); db.session.commit()
        return u
    return _make


@pytest.fixture()
def login(client, make_user):
    def _login(identifier="alice@example.com", password="secret"):
        return client.post(
            "/auth/login",
            data={"identifier": identifier, "password": password},
            follow_redirects=False,
        )
    return _login