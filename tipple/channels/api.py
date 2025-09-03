# tipple/channels/api.py
from __future__ import annotations
from flask import Blueprint, request, jsonify, url_for, abort
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..models import db, Channel

bp = Blueprint("channels_api", __name__, url_prefix="/channels/api")


@bp.post("/new")
@login_required
def create_channel_api():
    """
    Create a new channel.
    Body may be JSON or form data:
      - name: str (required, <=255)
      - parent_id: int (optional)
    """
    data = request.get_json(silent=True) or request.form or {}
    name = (data.get("name") or "").strip()
    parent_id = data.get("parent_id")  # may be str/int/None

    # Validate name
    if not name or len(name) > 255:
        return jsonify(error="name is required and must be <= 255 chars"), 400

    # Optional parent lookup
    parent = None
    if parent_id not in (None, "", 0, "0"):
        try:
            parent = db.session.get(Channel, int(parent_id))
        except (TypeError, ValueError):
            return jsonify(error="parent_id must be an integer"), 400
        if not parent:
            return jsonify(error="parent channel not found"), 404

    # Soft duplicate guard (keep a DB UNIQUE if you want a hard guarantee)
    if Channel.query.filter_by(name=name).first():
        return jsonify(error="channel name already exists"), 409

    ch = Channel(name=name)
    if parent:
        ch.parent = parent

    db.session.add(ch)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="unable to create channel"), 409

    payload = {
        "id": ch.id,
        "name": ch.name,
        "parent_id": ch.parent_id,
        "created_at": ch.created_at.isoformat(),
    }
    return (
        jsonify(payload),
        201,
        {"Location": url_for("channels.get_channel", channel_id=ch.id)},  # HTML page
    )


@bp.get("/<int:channel_id>")
def get_channel_api(channel_id: int):
    """Return channel details as JSON."""
    ch = db.session.get(Channel, channel_id)
    if not ch:
        abort(404)

    # follower_count only if the m2m is set up
    follower_count = len(ch.followers) if hasattr(ch, "followers") else None

    payload = {
        "id": ch.id,
        "name": ch.name,
        "parent_id": ch.parent_id,
        "created_at": ch.created_at.isoformat(),
    }
    if follower_count is not None:
        payload["follower_count"] = follower_count
    return jsonify(payload)


@bp.post("/<int:channel_id>")
@login_required
def follow_channel_api(channel_id: int):
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
