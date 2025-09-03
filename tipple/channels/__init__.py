from __future__ import annotations
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
    )
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..models import db, Channel, Post
# Use the post form you already have. If you created ChannelPostForm, import that instead.
from ..posts.forms import PostForm
from .forms import ChannelCreateForm

bp = Blueprint("channels", __name__, url_prefix="/channels")


@bp.route("/new", methods=["GET", "POST"])
def new_channel():
    """
    GET: render the 'create channel' page.
    POST: create a channel (requires login) and redirect to its page.
    """
    form = ChannelCreateForm()

    # Populate parent choices each time (so the list is fresh)
    channels = Channel.query.order_by(Channel.name.asc()).all()
    form.parent_id.choices = [(0, "— None —")] + [(c.id, f"#{c.name}") for c in channels]

    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Please sign in to create a channel.", "warning")
            return redirect(url_for("auth.login_page", next=request.path))

        if form.validate_on_submit():
            name = (form.name.data or "").strip()

            # Soft duplicate guard (keep a UNIQUE at DB layer if you want hard guarantee)
            if Channel.query.filter_by(name=name).first():
                form.name.errors.append("A channel with that name already exists.")
                return render_template("channels/new.html", form=form), 409

            ch = Channel(name=name)

            pid = form.parent_id.data or 0
            if pid:
                parent = db.session.get(Channel, pid)
                if not parent:
                    form.parent_id.errors.append("Parent channel not found.")
                    return render_template("channels/new.html", form=form), 400
                ch.parent = parent

            db.session.add(ch)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                form.name.errors.append("Could not create channel (possibly duplicate).")
                return render_template("channels/new.html", form=form), 409

            flash(f"Created channel #{ch.name}.", "success")
            return redirect(url_for("channels.get_channel", channel_id=ch.id))

        # Form didn’t validate (length, etc.)
        return render_template("channels/new.html")

    # GET
    return render_template("channels/new.html", form=form)


@bp.route("/<int:channel_id>", methods=["GET", "POST"])
def get_channel(channel_id: int):
    """
    GET: render the channel page with its posts and a post form.
    POST: create a post in this channel for the logged-in user.
    """
    channel = db.session.get(Channel, channel_id)
    if not channel:
        abort(404)

    form = PostForm()

    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Please sign in to post.", "warning")
            return redirect(url_for("auth.login_page", next=request.path))

        if form.validate_on_submit():
            body = (form.body.data or "").strip()
            tags = (form.tags.data or "").strip() or None

            p = Post(body=body, tags=tags)
            p.author = current_user
            p.channel = channel
            db.session.add(p)
            db.session.commit()

            flash("Posted!", "success")
            return redirect(url_for("channels.get_channel", channel_id=channel.id))

        # Validation errors → re-render with 400
        posts = (
            Post.query.filter_by(channel_id=channel.id)
            .order_by(Post.created_at.desc(), Post.id.desc())
            .all()
        )
        return render_template("channels/show.html", channel=channel, posts=posts, post_form=form), 400

    # GET
    posts = (
        Post.query.filter_by(channel_id=channel.id)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .all()
    )
    return render_template("channels/show.html", channel=channel, posts=posts, post_form=form)



### API JSON Methods ###

@bp.get("/api/<int:channel_id>")
def get_channel_api(channel_id: int):
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


@bp.post("/api/<int:channel_id>")
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
