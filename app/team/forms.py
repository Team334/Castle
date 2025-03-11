import logging

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileSize
from wtforms import IntegerField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange

logger = logging.getLogger(__name__)


class CreateTeamForm(FlaskForm):
    class Meta:
        csrf = True

    team_number = IntegerField(
        "Team Number",
        validators=[
            DataRequired(message="Team number is required"),
            NumberRange(
                min=1, max=19999, message="Team number must be between 1 and 19999"
            ),
        ],
    )

    team_name = StringField(
        "Team Name",
        validators=[
            DataRequired(message="Team name is required"),
            Length(
                min=1, max=100, message="Team name must be between 1 and 100 characters"
            ),
        ],
    )

    description = TextAreaField(
        "Description",
        validators=[
            Length(max=500, message="Description must be less than 500 characters")
        ],
    )

    logo = FileField(
        "Team Logo",
        validators=[
            FileAllowed(["jpg", "png"], "Only JPG and PNG images are allowed!"),
            FileSize(
                max_size=2 * 1024 * 1024, message="File size must be less than 2MB"
            ),
        ],
    )

    def validate(self, extra_validators=None):
        """Override validate method to add custom validation and logging"""
        initial_validation = super().validate(extra_validators=extra_validators)
        logger.debug(f"Form initial validation: {initial_validation}")

        if not initial_validation:
            logger.debug(f"Form errors: {self.errors}")
            return False

        # Add any custom validation here if needed
        return True
