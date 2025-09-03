from __future__ import annotations
from flask import Blueprint, jsonify, request, url_for, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from ..models import db, Channel

bp = Blueprint("channels", __name__, url_prefix="/channels")


@bp.post("/new/<string:name>")
@login_required
def create_channel(name: str):
    """Create a new channel. Supports optional parent via ?parent_id= or JSON/form."""
    nm = (name or "").strip()
    if not nm or len(nm) > 255:
        return jsonify(error="name is required and must be <= 255 chars"), 400

    # Optional parent
    parent_id = request.args.get("parent_id") or (request.get_json(silent=True) or {}).get("parent_id") or request.form.get("parent_id")
    parent = None
    if parent_id:
        parent = db.session.get(Channel, int(parent_id))
        if not parent:
            return jsonify(error="parent channel not found"), 404

    # Prevent duplicate names (soft-uniqueness; DB UNIQUE not required)
    if Channel.query.filter_by(name=nm).first():
        return jsonify(error="channel name already exists"), 409

    ch = Channel(name=nm)
    if parent:
        ch.parent = parent

    db.session.add(ch)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="unable to create channel"), 409

    return (
        jsonify(
            id=ch.id,
            name=ch.name,
            parent_id=ch.parent_id,
            created_at=ch.created_at.isoformat(),
        ),
        201,
        {"Location": url_for("channels.get_channel", channel_id=ch.id)},
    )


@bp.get("/<int:channel_id>")
def get_channel(channel_id: int):
    """Return channel details as JSON."""
    ch = db.session.get(Channel, channel_id)
    if not ch:
        abort(404)

    # follower_count only if the m2m is set up
    follower_count = len(ch.followers) if hasattr(ch, "followers") else None

    payload = {
        "channel_id": ch.id,
        "name": ch.name,
        "parent_id": ch.parent_id,
        "created_at": ch.created_at.isoformat(),
    }
    if follower_count is not None:
        payload["follower_count"] = follower_count
    return jsonify(payload)


@bp.post("/<int:channel_id>")
@login_required
def follow_channel(channel_id: int):
    """Current user follows the channel (idempotent)."""
    ch = db.session.get(Channel, channel_id)
    if not ch:
        abort(404)

    # If already following, do nothing (idempotent success)
    if ch in current_user.following:
        return jsonify(message="already following", id=ch.id), 200

    current_user.following.append(ch)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # If a race caused the join row to exist, treat as already-following
        return jsonify(message="already following", id=ch.id), 200

    return jsonify(message="now following", id=ch.id), 201
