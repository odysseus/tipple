from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ..models import db, Post

bp = Blueprint("posts", __name__, url_prefix="/posts")
