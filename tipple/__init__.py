# tipple/__init__.py
from __future__ import annotations

import os
from pathlib import Path
from flask import Flask, render_template
from flask_login import LoginManager
from flask_migrate import Migrate

from .config_classes import DevelopmentConfig, TestingConfig, ProductionConfig
from .models import db

from flask_wtf import CSRFProtect
csrf = CSRFProtect()

migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login_page"  # pyright: ignore[reportAttributeAccessIssue]


def create_app(config_object: type | str | None = None) -> Flask:
    """Application factory for the tipple Flask app."""
    app = Flask(__name__, instance_relative_config=True)

    # Config selection
    config_obj = config_object or _pick_config_from_env()
    app.config.from_object(config_obj)
    app.config.from_pyfile("config.py", silent=True)

    # Ensure instance folder exists
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Default DB URI if none provided: sqlite file in instance/
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{Path(app.instance_path) / 'tipple.sqlite'}" # pragma: no cover

    # Init extensions
    db.init_app(app)
    
    # Import models AFTER db.init_app to avoid metaclass errors
    with app.app_context():
      from . import models
    
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Form for logout button
    @app.context_processor
    def inject_forms():
        from .auth.forms import EmptyForm
        return {"logout_form": EmptyForm()}

    # Blueprints
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from .posts import bp as posts_bp
    app.register_blueprint(posts_bp)

    from .channels import bp as channels_bp
    app.register_blueprint(channels_bp)

    from .channels.api import bp as channels_api_bp
    app.register_blueprint(channels_api_bp)
    
    # Main page route
    @app.get("/")
    def index():
        return render_template("index.html")

    return app


def _pick_config_from_env(): # pragma: no cover
    env = os.environ.get("TIPPLE_ENV", "development").lower()
    return {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
        "prod": ProductionConfig,
        "dev": DevelopmentConfig,
        "test": TestingConfig,
    }.get(env, DevelopmentConfig)


@login_manager.user_loader
def load_user(user_id: str): # pragma: no cover
    from .models import User

    # Flask-Login needs this to load the session’s user
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
