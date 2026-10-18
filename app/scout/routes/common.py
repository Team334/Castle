"""Blueprint, shared manager, and helpers for every scouting view module."""
from __future__ import annotations

import logging
import os

from bson import ObjectId
from flask import Blueprint

from app.scout.scouting_utils import ScoutingManager

from ..match13_fuel import PHASES, FuelEstimateService

scouting_bp = Blueprint("scouting", __name__)
scouting_manager: ScoutingManager | None = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEOP_SHIFT_FIELDS = ("teleop_shift_1_fuel", "teleop_shift_2_fuel",
                       "teleop_shift_3_fuel", "teleop_shift_4_fuel")

SCOUTER_LOOKUP = {"$lookup": {
    "from": "users",
    "localField": "scouter_id",
    "foreignField": "_id",
    "as": "scouter"
}}


@scouting_bp.record
def on_blueprint_init(state):
    global scouting_manager
    app = state.app

    # Create ScoutingManager with the singleton connection
    scouting_manager = ScoutingManager(app.config["MONGO_URI"])

    # Store in app context for proper cleanup
    if not hasattr(app, 'db_managers'):
        app.db_managers = {}
    app.db_managers['scouting'] = scouting_manager
    try:
        service = FuelEstimateService(
            scouting_manager.db, os.getenv("MATCH13_STATE_PATH") or os.path.join(app.instance_path, "match13.sqlite"),
            api_key=os.getenv("MATCH_13_API_KEY") or os.getenv("MATCH13_API_KEY", ""),
            tba_key=os.getenv("TBA_AUTH_KEY", ""))
        app.extensions["match13_fuel"] = service
        service.start()
    except Exception:
        app.logger.exception("Fuel estimates unavailable; normal scouting is unaffected")


def actor_name(user) -> str:
    """Username for log lines."""
    return user.username if user.is_authenticated else 'Anonymous'


def team_access_match(user) -> dict:
    """$match stage (after SCOUTER_LOOKUP + $unwind) limiting records to the user's own or their team's."""
    access = {"scouter._id": ObjectId(user.get_id())}
    if user.teamNumber:
        access = {"$or": [access, {"scouter.teamNumber": user.teamNumber}]}
    return {"$match": access}


def fuel_total(record: dict):
    """Scored fuel across every phase (excludes ferried fuel)."""
    return sum(record[field] for field in PHASES)
