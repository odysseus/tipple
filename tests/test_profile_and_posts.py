# tests/test_profile_and_posts.py
from tipple.models import Post, User


def test_profile_update_bio(client, make_user, login):
    user = make_user()
    login()

    resp = client.post(
        "/auth/profile",
        data={"bio": "Just a friendly tippler"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Confirm persisted
    me_page = client.get("/auth/me")
    assert b"Just a friendly tippler" in me_page.data


def test_embedded_post_create_success(client, make_user, login):
    user = make_user()
    login()

    # Post is submitted to /auth/me (same page that renders the form)
    resp = client.post(
        "/auth/me",
        data={"body": "Hello, world!", "tags": "intro, first"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Posted!" in resp.data
    assert b"Hello, world!" in resp.data
    assert b"intro, first" in resp.data


def test_embedded_post_rejects_too_long_body(client, make_user, login):
    make_user(); login()
    too_long = "x" * 256

    resp = client.post(
        "/auth/me",
        data={"body": too_long, "tags": ""},
        follow_redirects=True,          # FOLLOW the redirect to see the flashed message
    )
    assert resp.status_code == 200
    assert b"Post or tags too long" in resp.data

    # No post was created
    from tipple.models import Post
    assert Post.query.count() == 0


def test_recent_posts_rendered(client, make_user, login, db):
    user = make_user()
    login()

    # create a couple of posts directly
    p1 = Post(user_id=user.id, body="Post A", tags="alpha") # pyright: ignore[reportCallIssue]
    p2 = Post(user_id=user.id, body="Post B", tags=None) # pyright: ignore[reportCallIssue]
    db.session.add_all([p1, p2]); db.session.commit()

    page = client.get("/auth/me")
    assert page.status_code == 200
    assert b"Post A" in page.data
    assert b"Post B" in page.data
