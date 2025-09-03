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
