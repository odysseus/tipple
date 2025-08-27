# tipple/auth/__init__.py
from __future__ import annotations
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from .forms import RegisterForm, LoginForm, ProfileForm
from ..models import db, User, Post         # import Post
from ..posts.forms import PostForm           # import PostForm

bp = Blueprint("auth", __name__, url_prefix="/auth", template_folder="../templates")

# ---------- HTML PAGE VIEWS ----------

@bp.route("/register", methods=["GET", "POST"])
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower().strip(), # type: ignore
            username=form.username.data.strip(), # type: ignore
        )
        user.set_password(form.password.data) # type: ignore
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome to tipple!", "success")
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("index"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()
    if form.validate_on_submit():
        ident = form.identifier.data.strip().lower() # type: ignore
        user = User.query.filter_by(email=ident).first() or User.query.filter_by(username=ident).first()
        if not user or not user.check_password(form.password.data):
            flash("Invalid credentials.", "danger")
            return render_template("auth/login.html", form=form), 401

        login_user(user, remember=form.remember.data)
        flash("Signed in.", "success")
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("index"))

    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout_page():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("auth.login_page"))


# tipple/auth/__init__.py

@bp.route("/me", methods=["GET", "POST"])
@login_required
def me_page():
    post_form = PostForm()

    if post_form.validate_on_submit():
        body = (post_form.body.data or "").strip()
        tags = (post_form.tags.data or "").strip() or None
        p = Post(user_id=current_user.id, body=body, tags=tags) 
        db.session.add(p)
        db.session.commit()
        flash("Posted!", "success")
        return redirect(url_for("auth.me_page"))

    # NEW: POST happened but form invalid (e.g., >255 chars) – flash and redirect
    if post_form.is_submitted() and not post_form.validate():
        # Optional: you can inspect post_form.body.errors / post_form.tags.errors
        flash("Post or tags too long.", "danger")
        return redirect(url_for("auth.me_page"))

    my_posts = (
        Post.query.filter_by(user_id=current_user.id)
        .order_by(Post.id.desc())
        .limit(20)
        .all()
    )
    return render_template("auth/me.html", user=current_user, post_form=post_form, posts=my_posts)


# ---------- JSON API (unchanged behavior, just moved under /api) ----------

@bp.post("/api/register")
def register_api():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    username = (data.get("username") or "").strip()
    password = data.get("password")
    bio = data.get("bio")

    if not email or not username or not password:
        return jsonify(error="email, username, and password are required"), 400

    if User.query.filter((User.email == email) | (User.username == username)).first():
        return jsonify(error="email or username already in use"), 409

    user = User(email=email, username=username, bio=bio)  
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(message="registered"), 201


@bp.post("/api/login")
def login_api():
    data = request.get_json(silent=True) or request.form
    ident = (data.get("email") or data.get("username") or "").strip().lower()
    password = data.get("password")

    if not ident or not password:
        return jsonify(error="credentials required"), 400

    user = User.query.filter_by(email=ident).first() or User.query.filter_by(username=ident).first()
    if not user or not user.check_password(password):
        return jsonify(error="invalid credentials"), 401

    login_user(user)
    return jsonify(message="logged in")


@bp.post("/api/logout")
@login_required
def logout_api():
    logout_user()
    return jsonify(message="logged out")


@bp.get("/api/me")
@login_required
def me_api():
    u = current_user
    return jsonify(id=u.id, email=u.email, username=u.username, bio=u.bio)


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile_page():
    form = ProfileForm(obj=current_user)  # prefill from user
    if form.validate_on_submit():
        current_user.bio = (form.bio.data or "").strip() or None
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("auth.me_page"))
    return render_template("auth/profile.html", form=form)
