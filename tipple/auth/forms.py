# tipple/auth/forms.py
from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
# NOTE: We import User INSIDE the validators to avoid early-import/circular issues.

class RegisterForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=255)],
    )
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=80)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=128)],
    )
    confirm = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create account")

    def validate_email(self, field: StringField) -> None:
        # normalize
        normalized = (field.data or "").strip().lower()
        field.data = normalized

        from ..models import User  # local import avoids mapper-init timing issues
        if User.query.filter_by(email=normalized).first():
            raise ValidationError("That email is already registered.")

    def validate_username(self, field: StringField) -> None:
        normalized = (field.data or "").strip()
        field.data = normalized

        from ..models import User
        # Case-sensitive check (matches a UNIQUE index on username)
        if User.query.filter_by(username=normalized).first():
            raise ValidationError("That username is taken.")

        # If you want case-insensitive duplicates, use this instead:
        # from sqlalchemy import func
        # if User.query.filter(func.lower(User.username) == normalized.lower()).first():
        #     raise ValidationError("That username is taken.")


class LoginForm(FlaskForm):
    identifier = StringField("Email or Username", validators=[DataRequired(), Length(min=3, max=255)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Sign in")


class ProfileForm(FlaskForm):
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=256)])
    submit = SubmitField("Save changes")


class EmptyForm(FlaskForm):
    pass
