from __future__ import annotations
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
    )
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..models import db, Channel, Post
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

    is_following = (
        current_user.is_authenticated
        and hasattr(current_user, "following")
        and (channel in current_user.following)
    )
    
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
        return render_template(
            "channels/show.html", 
            channel=channel, 
            posts=posts, 
            post_form=form, 
            is_following=is_following
            ), 400

    # GET
    posts = (
        Post.query.filter_by(channel_id=channel.id)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .all()
    )

    return render_template(
        "channels/show.html", 
        channel=channel, 
        posts=posts, 
        post_form=form, 
        is_following=is_following
        )


@bp.post("/<int:channel_id>/follow")
@login_required
def follow_channel(channel_id: int):
    ch = db.session.get(Channel, channel_id)
    if not ch:
        abort(404)
    # idempotent: do nothing if already following
    if hasattr(current_user, "following") and ch in current_user.following:
        flash(f"Already following #{ch.name}.", "info")
        return redirect(url_for("channels.get_channel", channel_id=ch.id))

    try:
        current_user.following.append(ch)
        db.session.commit()
        flash(f"Now following #{ch.name}.", "success")
    except IntegrityError:
        db.session.rollback()
        # race-safe: treat as already following
        flash(f"Already following #{ch.name}.", "info")
    return redirect(url_for("channels.get_channel", channel_id=ch.id))


@bp.post("/<int:channel_id>/unfollow")
@login_required
def unfollow_channel(channel_id: int):
    ch = db.session.get(Channel, channel_id)
    if not ch:
        abort(404)
    if not hasattr(current_user, "following"):
        flash("Following is not available.", "warning")
        return redirect(url_for("channels.get_channel", channel_id=channel_id))

    # Remove if present; idempotent if not
    if ch in current_user.following:
        current_user.following.remove(ch)
        db.session.commit()
        flash(f"Unfollowed #{ch.name}.", "info")
    else:
        flash(f"You are not following #{ch.name}.", "info")
    return redirect(url_for("channels.get_channel", channel_id=ch.id))
