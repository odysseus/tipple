# tipple/config_classes.py
from __future__ import annotations
import os


class BaseConfig:
    SECRET_KEY = os.environ.get("TIPPLE_SECRET_KEY", "dev")
    WTF_CSRF_ENABLED = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("TIPPLE_DATABASE_URI")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(BaseConfig):
    DEBUG = False
