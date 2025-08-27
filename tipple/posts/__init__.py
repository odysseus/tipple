from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..models import db, Post

bp = Blueprint("posts", __name__, url_prefix="/posts")

@bp.post("/")
@login_required
def create_post():
    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    tags = (data.get("tags") or "").strip() or None
    if not body:
        return jsonify(error="body is required"), 400
    if len(body) > 255 or (tags and len(tags) > 255):
        return jsonify(error="body/tags too long"), 400
    p = Post(user_id=current_user.id, body=body, tags=tags) # pyright: ignore[reportCallIssue]
    db.session.add(p); db.session.commit()
    return jsonify(id=p.id, body=p.body, tags=p.tags, user_id=p.user_id), 201

@bp.get("/")
@login_required
def list_my_posts():
    posts = (
        Post.query.filter_by(user_id=current_user.id)
        .order_by(Post.id.desc())
        .limit(50)
        .all()
    )
    return jsonify([
        {"id": p.id, "body": p.body, "tags": p.tags, "created_at": p.created_at.isoformat()}
        for p in posts
    ])
