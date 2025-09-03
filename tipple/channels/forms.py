from __future__ import annotations
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class ChannelCreateForm(FlaskForm):
    name = StringField("Channel name", validators=[DataRequired(), Length(max=255)])
    # We'll populate choices in the view; 0 means “None”
    parent_id = SelectField("Parent channel", coerce=int, validators=[Optional()], choices=[])
    submit = SubmitField("Create channel")
