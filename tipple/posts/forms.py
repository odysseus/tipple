# tipple/posts/forms.py
from __future__ import annotations
from flask_wtf import FlaskForm
from wtforms import TextAreaField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class PostForm(FlaskForm):
    body = TextAreaField("What's on your mind?",
                         validators=[DataRequired(), Length(max=255)])
    tags = StringField("Add tags (comma-separated)",
                       validators=[Optional(), Length(max=255)])
    submit = SubmitField("Post")
