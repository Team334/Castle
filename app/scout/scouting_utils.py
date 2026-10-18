from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from bson import ObjectId

from app.models import Team, TeamData
from app.utils import DatabaseManager, with_mongodb_retry

logger = logging.getLogger(__name__)

SCOUTER_LOOKUP = {"$lookup": {
    "from": "users",
    "localField": "scouter_id",
    "foreignField": "_id",
    "as": "scouter"
}}
UNWIND_SCOUTER = {"$unwind": "$scouter"}

PIT_PROJECTION = {
    "_id": 1,
    "team_number": 1,
    "drive_type": 1,
    "swerve_modules": 1,
    "fuel_count_bps": 1,
    "shooter_type": 1,
    "shooter_notes": 1,
    "intake_notes": 1,
    "hopper_notes": 1,
    "autonomous_capabilities": 1,
    "driver_experience": 1,
    "notes": 1,
    "scouter_id": "$scouter._id",
    "scouter_name": "$scouter.username",
    "scouter_team": "$scouter.teamNumber"
}

LEADERBOARD_SORT_FIELDS = {
    'fuel': 'total_fuel',
    'auto_fuel': 'auto_fuel',
    'ferried_fuel': 'ferried_fuel',
    'auto_climb': 'auto_climb_pct',
    'climb': 'climb_success_rate',
    'climb_l1': 'climb_l1_pct',
    'climb_l2': 'climb_l2_pct',
    'climb_l3': 'climb_l3_pct',
    'defense': 'defense_rating',
    'herd_rating': 'herd_rating',
    'ferrying_rating': 'ferrying_rating'
}
SCOUTER_SORT_FIELDS = {
    'match_count': 'match_count',
    'unique_teams': 'unique_teams_count',
}


def access_match(user_id, team_number=None) -> dict:
    """$match stage (after SCOUTER_LOOKUP + unwind) limiting records to the user's own or their team's."""
    access = {"scouter._id": ObjectId(user_id)}
    if team_number:
        access = {"$or": [access, {"scouter.teamNumber": team_number}]}
    return {"$match": access}


def _percent(count_field: str, total_field: str = "$matches_played") -> dict:
    return {"$multiply": [{"$divide": [count_field, total_field]}, 100]}


def _is_checked(value) -> bool:
    return value == "true" or value is True


def _record_fields(data: dict) -> dict:
    """Scored fields shared by new and edited match records."""
    herd = _is_checked(data.get("herd_balls"))
    ferrying = _is_checked(data.get("ferrying_did"))
    return {
        # Fuel
        "auto_fuel": int(data.get("auto_fuel", 0)),
        "transition_fuel": int(data.get("transition_fuel", 0)),
        "teleop_shift_1_fuel": int(data.get("teleop_shift_1_fuel", 0)),
        "teleop_shift_2_fuel": int(data.get("teleop_shift_2_fuel", 0)),
        "teleop_shift_3_fuel": int(data.get("teleop_shift_3_fuel", 0)),
        "teleop_shift_4_fuel": int(data.get("teleop_shift_4_fuel", 0)),
        "endgame_fuel": int(data.get("endgame_fuel", 0)),
        "ferried_fuel": int(data.get("ferried_fuel", 0)),

        # Climb
        "climb_level": int(data.get("climb_level", 0)),
        "climb_type": data.get("climb_type", ""),
        "climb_success": bool(data.get("climb_success", False)),

        # Defense
        "defense_rating": int(data.get("defense_rating", 1)),
        "defense_notes": data.get("defense_notes", ""),
        "defense_response_notes": data.get("defense_response_notes", ""),

        # Herd and Ferrying
        "herd_balls": herd,
        "herd_rating": int(data.get("herd_rating", 5)) if herd else 0,
        "ferrying_did": ferrying,
        "ferrying_rating": int(data.get("ferrying_rating", 5)) if ferrying else 0,
        # Robot Disabled Status
        "robot_disabled": data.get("robot_disabled", "None"),

        # Auto
        "auto_path": data.get("auto_path", ""),
        "auto_notes": data.get("auto_notes", ""),

        # Notes
        "notes": data.get("notes", ""),
    }


class ScoutingManager(DatabaseManager):
    def __init__(self, mongo_uri=None):
        # Use the singleton connection
        super().__init__(mongo_uri)
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        """Ensure required collections exist"""
        collections = self.db.list_collection_names()
        if "team_data" not in collections:
            self.db.create_collection("team_data")
            self.db.team_data.create_index([("team_number", 1)])
            self.db.team_data.create_index([("scouter_id", 1)])
            logger.info("Created team_data collection and indexes")
        if "pit_scouting" not in collections:
            self.db.create_collection("pit_scouting")
            self.db.pit_scouting.create_index([("team_number", 1)])
            self.db.pit_scouting.create_index([("scouter_id", 1)])
            logger.info("Created pit_scouting collection and indexes")

    def _visible_records(self, user_id, team_number) -> list[dict]:
        """Pipeline prefix: every match record joined with its scouter, limited to what the user may see."""
        return [SCOUTER_LOOKUP, UNWIND_SCOUTER, access_match(user_id, team_number)]

    def get_team(self, team_number) -> Team | None:
        if team_number and (team_doc := self.db.teams.find_one({"team_number": team_number})):
            return Team.create_from_db(team_doc)
        return None

    # ============ Match records ============

    @with_mongodb_retry(retries=3, delay=2)
    def add_scouting_data(self, data: dict, scouter_id: str) -> tuple[bool, str]:
        """Add new scouting data with retry mechanism"""
        try:
            # Validate team number
            team_number = int(data["team_number"])
            if team_number <= 0:
                return False, "Invalid team number"

            team_data = {
                "team_number": team_number,
                "event_code": data["event_code"],
                "match_number": data["match_number"],
                "alliance": data.get("alliance", "red"),
                "auto_climb": bool(data.get("auto_climb", False)),
                **_record_fields(data),

                # Metadata
                "scouter_id": ObjectId(scouter_id),
                "created_at": datetime.now(timezone.utc),
            }

            result = self.db.team_data.insert_one(team_data)
            return True, str(result.inserted_id)

        except Exception as e:
            logger.error(f"Error adding team data: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    def get_all_scouting_data(self, user_team_number=None, user_id=None, *,
                              page=None, page_size=20, search="", filter_type="team") -> list[dict] | dict:
        """Read authorized scouting data, optionally returning a page and total."""
        try:
            pipeline = self._visible_records(user_id, user_team_number)
            pipeline.append({
                "$project": {
                    "_id": 1,
                    "team_number": 1,
                    "match_number": 1,
                    "event_code": 1,

                    # Fuel Stats
                    "auto_fuel": 1,
                    "transition_fuel": 1,
                    "teleop_shift_1_fuel": 1,
                    "teleop_shift_2_fuel": 1,
                    "teleop_shift_3_fuel": 1,
                    "teleop_shift_4_fuel": 1,
                    "endgame_fuel": 1,
                    "ferried_fuel": 1,

                    # Climb Stats
                    "auto_climb": 1,
                    "climb_level": 1,
                    "climb_type": 1,
                    "climb_success": 1,
                    "defense_rating": 1,
                    "defense_notes": 1,
                    "defense_response_notes": 1,
                    "herd_balls": 1,
                    "herd_rating": 1,
                    "ferrying_did": 1,
                    "ferrying_rating": 1,
                    "robot_disabled": 1,
                    "auto_path": 1,
                    "auto_notes": 1,
                    "notes": 1,
                    "alliance": 1,
                    "scouter_id": 1,
                    "scouter_name": "$scouter.username",
                    "scouter_team": "$scouter.teamNumber",
                    "device_type": 1
                }
            })

            if page is not None:
                # Keep the existing visibility rules and storage format. Search
                # precedes pagination so older records remain discoverable.
                fields = {"team": "team_number", "match": "match_number",
                          "scouter": "scouter_name", "notes": "notes"}
                term = search.strip()[:200]
                if term:
                    field = fields.get(filter_type, "team_number")
                    pipeline.append({"$match": {"$expr": {"$regexMatch": {
                        "input": {"$convert": {"input": "$" + field, "to": "string",
                                               "onError": "", "onNull": ""}},
                        "regex": re.escape(term), "options": "i"}}}})
                pipeline.append({"$facet": {
                    "records": [{"$sort": {"_id": -1}},
                                {"$skip": (max(1, page) - 1) * page_size},
                                {"$limit": page_size}],
                    "count": [{"$count": "total"}],
                }})
                result = next(iter(self.db.team_data.aggregate(pipeline)), {})
                return {"records": result.get("records", []),
                        "total": (result.get("count") or [{"total": 0}])[0]["total"]}
            return list(self.db.team_data.aggregate(pipeline))
        except Exception as e:
            logger.error(f"Error fetching team data: {str(e)}")
            if page is not None:
                raise
            return []

    def get_visible_fuel(self, record_ids, user_id, team_number, fields) -> list[dict]:
        """Fuel fields of the given records the user may see."""
        return list(self.db.team_data.aggregate([
            {"$match": {"_id": {"$in": [ObjectId(id) for id in record_ids]}}},
            *self._visible_records(user_id, team_number),
            {"$project": {"_id": 1, **dict.fromkeys(fields, 1)}},
        ]))

    @with_mongodb_retry(retries=3, delay=2)
    def get_team_data(self, team_id, scouter_id=None) -> TeamData | None:
        """Get specific team data with optional scouter verification"""
        try:
            # Just get the data by ID first
            data = self.db.team_data.find_one({"_id": ObjectId(team_id)})
            if not data:
                return None

            if scouter := self.db.users.find_one(
                {"_id": ObjectId(data["scouter_id"])}
            ):
                data["scouter_team"] = scouter.get("teamNumber")
            else:
                data["scouter_team"] = None

            # Then check ownership if scouter_id is provided
            if scouter_id:
                data["is_owner"] = str(data["scouter_id"]) == str(scouter_id)
            else:
                data["is_owner"] = False

            return TeamData.create_from_db(data)
        except Exception as e:
            logger.error(f"Error fetching team data: {str(e)}")
            return None

    @with_mongodb_retry(retries=3, delay=2)
    def update_team_data(self, team_id, data, scouter_id) -> bool:
        """Update existing team data if user is the owner"""
        try:
            try:
                team_number = int(data["team_number"])
                event_code = data["event_code"]
                match_number = data["match_number"]
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning(f"Invalid update payload for team data: {exc}")
                return False

            # First verify ownership and get current data
            existing_data = self.db.team_data.find_one(
                {"_id": ObjectId(team_id)}
            )

            if not existing_data:
                logger.warning(f"Data not found for team_id: {team_id}")
                return False

            existing_team_number = existing_data.get("team_number")
            try:
                existing_team_number = int(existing_team_number) if existing_team_number is not None else None
            except (TypeError, ValueError):
                logger.warning(f"Invalid existing team_number in record {team_id}: {existing_team_number}")
                existing_team_number = None

            identity_changed = (
                existing_data.get("event_code") != event_code
                or existing_data.get("match_number") != match_number
                or existing_team_number != team_number
            )

            # Check for duplicate scouting records only when identity fields change.
            # This allows editing existing duplicate records without being blocked.
            if identity_changed:
                existing_entries = list(self.db.team_data.aggregate([
                    {
                        "$match": {
                            "event_code": event_code,
                            "match_number": match_number,
                            "team_number": team_number,
                            "_id": {"$ne": ObjectId(team_id)}  # Exclude current entry
                        }
                    },
                    SCOUTER_LOOKUP,
                    UNWIND_SCOUTER
                ]))
                current_user = self.db.users.find_one({"_id": ObjectId(scouter_id)})

                for entry in existing_entries:
                    if entry.get("scouter", {}).get("teamNumber") == current_user.get("teamNumber"):
                        logger.warning(
                            f"Update attempted for team {team_number} in match {match_number} "
                            f"which is already scouted by team {current_user.get('teamNumber')}"
                        )
                        return False

            # Get match data to validate alliance sizes
            match_data = list(self.db.team_data.find({
                "event_code": event_code,
                "match_number": match_number,
                "_id": {"$ne": ObjectId(team_id)}  # Exclude current entry
            }))

            # Count teams per alliance
            alliance = data.get("alliance", "red")
            alliance_size = sum(1 for m in match_data if m["alliance"] == alliance)
            if alliance in ("red", "blue") and alliance_size >= 3 and existing_data.get("alliance") != alliance:
                return False

            updated_data = {
                "team_number": team_number,
                "event_code": event_code,
                "match_number": match_number,
                "alliance": alliance,
                **_record_fields(data),
            }

            result = self.db.team_data.update_one(
                {"_id": ObjectId(team_id)},
                {"$set": updated_data},
            )
            return result.matched_count > 0
        except Exception as e:
            logger.error(f"Error updating team data: {str(e)}")
            return False

    @with_mongodb_retry(retries=3, delay=2)
    def delete_team_data(self, team_id: str, user_id: str, admin_override=False) -> bool:
        """Delete team data if scouter has permission (original scouter or team admin)"""
        try:
            # First get the team data to check permissions
            team_data = self.db.team_data.find_one({"_id": ObjectId(team_id)})
            if not team_data:
                logger.warning(f"Team data with ID {team_id} not found")
                return False

            # Check if user is the original scouter
            is_original_scouter = str(team_data.get("scouter_id")) == str(user_id)

            # If admin_override is True, skip additional permission checks
            if admin_override:
                logger.info(f"Admin override: Deleting team data {team_id} by user {user_id}")
                result = self.db.team_data.delete_one({"_id": ObjectId(team_id)})
                return result.deleted_count > 0

            # Check if user is a team admin
            is_team_admin = False

            # Get the scouter's team number
            scouter = self.db.users.find_one({"_id": ObjectId(team_data["scouter_id"])})
            scouter_team_number = scouter.get("teamNumber") if scouter else None

            # Get the current user's team number
            current_user = self.db.users.find_one({"_id": ObjectId(user_id)})
            user_team_number = current_user.get("teamNumber") if current_user else None

            # Check if both users are on the same team
            if scouter_team_number and user_team_number and scouter_team_number == user_team_number:
                if team := self.db.teams.find_one(
                    {"team_number": user_team_number}
                ):
                    # Check if user is in the admins list or is the owner
                    is_team_admin = str(user_id) in team.get("admins", []) or str(user_id) == str(team.get("owner_id"))
                    logger.info(f"User {user_id} is admin of team {user_team_number}: {is_team_admin}")

            # Allow deletion if user is original scouter or a team admin
            if is_original_scouter or is_team_admin:
                logger.info(f"Deleting team data {team_id} by user {user_id} (original: {is_original_scouter}, admin: {is_team_admin})")
                result = self.db.team_data.delete_one({"_id": ObjectId(team_id)})
                return result.deleted_count > 0

            logger.warning(f"Permission denied: User {user_id} attempted to delete team data {team_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting team data: {str(e)}", exc_info=True)
            return False

    # ============ Analysis over visible match records ============

    def get_match_alliances(self, user_id, team_number) -> list[dict]:
        """Visible records grouped by (event, match), each team's fuel and climb defaulted."""
        return list(self.db.team_data.aggregate([
            *self._visible_records(user_id, team_number),
            {"$group": {
                "_id": {
                    "event": "$event_code",
                    "match": "$match_number"
                },
                "teams": {
                    "$push": {
                        "id": "$_id",
                        "number": "$team_number",
                        "alliance": "$alliance",

                        # Fuel stats
                        "auto_fuel": {"$ifNull": ["$auto_fuel", 0]},
                        "auto_climb": {"$ifNull": ["$auto_climb", False]},
                        "transition_fuel": {"$ifNull": ["$transition_fuel", 0]},
                        "ferried_fuel": {"$ifNull": ["$ferried_fuel", 0]},
                        "teleop_shift_1_fuel": {"$ifNull": ["$teleop_shift_1_fuel", 0]},
                        "teleop_shift_2_fuel": {"$ifNull": ["$teleop_shift_2_fuel", 0]},
                        "teleop_shift_3_fuel": {"$ifNull": ["$teleop_shift_3_fuel", 0]},
                        "teleop_shift_4_fuel": {"$ifNull": ["$teleop_shift_4_fuel", 0]},
                        "endgame_fuel": {"$ifNull": ["$endgame_fuel", 0]},

                        "climb_level": {"$ifNull": ["$climb_level", 0]},
                        "climb_type": "$climb_type",
                        "climb_success": "$climb_success"
                    }
                },
            }}
        ]))

    def get_compare_stats(self, team: int, user_id, team_number) -> dict | None:
        """Averages for one team over the user's visible records, or None without data."""
        stats = list(self.db.team_data.aggregate([
            {"$match": {"team_number": team}},
            *self._visible_records(user_id, team_number),
            {"$group": {
                "_id": "$team_number",
                "matches_played": {"$sum": 1},

                # Fuel Stats
                "avg_auto_fuel": {"$avg": {"$ifNull": ["$auto_fuel", 0]}},
                "avg_auto_climb": {"$avg": {"$cond": ["$auto_climb", 1, 0]}},
                "avg_transition_fuel": {"$avg": {"$ifNull": ["$transition_fuel", 0]}},
                "avg_ferried_fuel": {"$avg": {"$ifNull": ["$ferried_fuel", 0]}},
                "avg_teleop_shift_1_fuel": {"$avg": {"$ifNull": ["$teleop_shift_1_fuel", 0]}},
                "avg_teleop_shift_2_fuel": {"$avg": {"$ifNull": ["$teleop_shift_2_fuel", 0]}},
                "avg_teleop_shift_3_fuel": {"$avg": {"$ifNull": ["$teleop_shift_3_fuel", 0]}},
                "avg_teleop_shift_4_fuel": {"$avg": {"$ifNull": ["$teleop_shift_4_fuel", 0]}},
                "avg_endgame_fuel": {"$avg": {"$ifNull": ["$endgame_fuel", 0]}},

                # Climb Stats
                "climb_success_rate": {"$avg": {"$cond": ["$climb_success", 1, 0]}},
                "climb_level_1_count": {"$sum": {"$cond": [{"$eq": ["$climb_level", 1]}, 1, 0]}},
                "climb_level_2_count": {"$sum": {"$cond": [{"$eq": ["$climb_level", 2]}, 1, 0]}},
                "climb_level_3_count": {"$sum": {"$cond": [{"$eq": ["$climb_level", 3]}, 1, 0]}},
                "avg_climb_level": {"$avg": {"$ifNull": ["$climb_level", 0]}},

                "defense_notes": {"$push": "$defense_notes"},
                "auto_paths": {"$push": {
                    "path": "$auto_path",
                    "notes": "$auto_notes",
                    "match_number": "$match_number"
                }},
                "defense_rating": {"$avg": {"$cond": [{"$gt": ["$defense_rating", 0]}, "$defense_rating", None]}},
                "robot_disabled_list": {"$push": "$robot_disabled"},
                "preferred_climb_type": {"$last": "$climb_type"},
                "matches": {"$push": "$$ROOT"}
            }},
            {"$match": {"matches_played": {"$gt": 0}}}
        ]))
        return stats[0] if stats else None

    def get_team_records(self, team: int, user_id, team_number) -> list[dict]:
        """A team's visible records for search results, oldest match first."""
        return list(self.db.team_data.aggregate([
            {"$match": {"team_number": team}},
            SCOUTER_LOOKUP,
            {"$unwind": {"path": "$scouter"}},
            access_match(user_id, team_number),
            {"$sort": {"event_code": 1, "match_number": 1}},
            {
                "$project": {
                    "_id": {"$toString": "$_id"},  # Convert ObjectId to string
                    "event_code": 1,
                    "match_number": 1,
                    # Fuel Stats
                    "transition_fuel": {"$ifNull": ["$transition_fuel", 0]},
                    "ferried_fuel": {"$ifNull": ["$ferried_fuel", 0]},
                    "auto_fuel": {"$ifNull": ["$auto_fuel", 0]},
                    "teleop_shift_1_fuel": {"$ifNull": ["$teleop_shift_1_fuel", 0]},
                    "teleop_shift_2_fuel": {"$ifNull": ["$teleop_shift_2_fuel", 0]},
                    "teleop_shift_3_fuel": {"$ifNull": ["$teleop_shift_3_fuel", 0]},
                    "teleop_shift_4_fuel": {"$ifNull": ["$teleop_shift_4_fuel", 0]},
                    "endgame_fuel": {"$ifNull": ["$endgame_fuel", 0]},

                    # Climb Stats
                    "auto_climb": 1,
                    "climb_level": {"$ifNull": ["$climb_level", 0]},
                    "climb_type": 1,
                    "climb_success": 1,

                    "auto_path": 1,
                    "auto_notes": 1,
                    "defense_rating": {"$ifNull": ["$defense_rating", 0]},
                    "notes": 1,
                    "scouter_name": "$scouter.username",
                    "scouter_id": {"$toString": "$scouter._id"}
                }
            }
        ]))

    def get_auto_paths(self, team: int, user_id, team_number) -> list[dict]:
        """A team's visible records that drew an auto path, newest match first."""
        return list(self.db.team_data.aggregate([
            {"$match": {"team_number": team}},
            SCOUTER_LOOKUP,
            {"$unwind": {"path": "$scouter", "preserveNullAndEmptyArrays": True}},
            access_match(user_id, team_number),
            # Only get matches with auto path data
            {"$match": {"auto_path": {"$exists": True, "$ne": []}}},
            {"$sort": {"match_number": -1}},
            {"$project": {
                "_id": {"$toString": "$_id"},
                "team_number": 1,
                "match_number": 1,
                "event_code": 1,
                "event_name": 1,
                "alliance": 1,
                "auto_path": 1,
                "auto_notes": 1,
                "scouter_name": "$scouter.username",
                "scouter_id": {"$toString": "$scouter._id"}
            }}
        ]))

    def get_leaderboard_events(self, user_id, team_number) -> list[dict]:
        """Events in the user's visible records, with record counts."""
        return list(self.db.team_data.aggregate([
            *self._visible_records(user_id, team_number),
            {"$group": {
                "_id": "$event_code",
                "event_name": {"$first": "$event_name"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]))

    def get_team_leaderboard(self, user_id, team_number, event="all", sort_field=None,
                             min_matches=1) -> list[dict]:
        """Per-team averages over visible records; sorted descending by sort_field when given."""
        pipeline = self._visible_records(user_id, team_number)
        if event != 'all':
            pipeline.append({"$match": {"event_code": event}})
        pipeline.extend([
            {"$group": {
                "_id": "$team_number",
                "matches_played": {"$sum": 1},

                # Auto Fuel
                "auto_fuel": {"$avg": {"$ifNull": ["$auto_fuel", 0]}},
                "transition_fuel": {"$avg": {"$ifNull": ["$transition_fuel", 0]}},
                "ferried_fuel": {"$avg": {"$ifNull": ["$ferried_fuel", 0]}},

                # Teleop Fuel
                "teleop_shift_1_fuel": {"$avg": {"$ifNull": ["$teleop_shift_1_fuel", 0]}},
                "teleop_shift_2_fuel": {"$avg": {"$ifNull": ["$teleop_shift_2_fuel", 0]}},
                "teleop_shift_3_fuel": {"$avg": {"$ifNull": ["$teleop_shift_3_fuel", 0]}},
                "teleop_shift_4_fuel": {"$avg": {"$ifNull": ["$teleop_shift_4_fuel", 0]}},

                # Endgame Fuel
                "endgame_fuel": {"$avg": {"$ifNull": ["$endgame_fuel", 0]}},

                # Climb Level
                "auto_climb_sum": {"$sum": {"$cond": [{"$eq": ["$auto_climb", True]}, 1, 0]}},
                "climb_level": {"$avg": {"$ifNull": ["$climb_level", 0]}},

                # Defense Rating
                "defense_rating": {"$avg": {"$ifNull": ["$defense_rating", 0]}},
                # Robot Disabled
                "robot_disabled_list": {"$push": "$robot_disabled"},

                "herd_rating": {
                    "$avg": {
                        "$cond": [{"$eq": ["$herd_balls", True]}, {"$ifNull": ["$herd_rating", 0]}, None]
                    }
                },
                "herd_count": {"$sum": {"$cond": [{"$eq": ["$herd_balls", True]}, 1, 0]}},

                "ferrying_rating": {
                    "$avg": {
                        "$cond": [{"$eq": ["$ferrying_did", True]}, {"$ifNull": ["$ferrying_rating", 0]}, None]
                    }
                },
                "ferrying_count": {"$sum": {"$cond": [{"$eq": ["$ferrying_did", True]}, 1, 0]}},

                # Climb stats
                "climb_level_1_success": {"$sum": {"$cond": [{"$and": [{"$eq": ["$climb_level", 1]}, {"$eq": ["$climb_success", True]}]}, 1, 0]}},
                "climb_level_2_success": {"$sum": {"$cond": [{"$and": [{"$eq": ["$climb_level", 2]}, {"$eq": ["$climb_success", True]}]}, 1, 0]}},
                "climb_level_3_success": {"$sum": {"$cond": [{"$and": [{"$eq": ["$climb_level", 3]}, {"$eq": ["$climb_success", True]}]}, 1, 0]}},
                "climb_attempts": {"$sum": 1},
                "climb_successes": {
                    "$sum": {"$cond": [{"$eq": ["$climb_success", True]}, 1, 0]}
                },
            }},
            {"$match": {"matches_played": {"$gte": min_matches}}},
            {"$project": {
                "team_number": "$_id",
                "matches_played": 1,

                "auto_fuel": {"$round": ["$auto_fuel", 1]},
                "transition_fuel": {"$round": ["$transition_fuel", 1]},
                "ferried_fuel": {"$round": ["$ferried_fuel", 1]},
                "teleop_fuel_total": {
                    "$add": [
                        "$transition_fuel",
                        "$teleop_shift_1_fuel",
                        "$teleop_shift_2_fuel",
                        "$teleop_shift_3_fuel",
                        "$teleop_shift_4_fuel"
                    ]
                },
                "endgame_fuel": {"$round": ["$endgame_fuel", 1]},

                # Calculate totals for each category
                "total_fuel": {
                    "$add": [
                        "$auto_fuel",
                        "$transition_fuel",
                        "$teleop_shift_1_fuel",
                        "$teleop_shift_2_fuel",
                        "$teleop_shift_3_fuel",
                        "$teleop_shift_4_fuel",
                        "$endgame_fuel"
                    ]
                },

                "climb_level_avg": {"$round": ["$climb_level", 1]},

                "auto_climb_pct": _percent("$auto_climb_sum"),
                "climb_l1_pct": _percent("$climb_level_1_success"),
                "climb_l2_pct": _percent("$climb_level_2_success"),
                "climb_l3_pct": _percent("$climb_level_3_success"),
                "climb_success_rate": {
                    "$multiply": [
                        {"$cond": [
                            {"$gt": ["$climb_attempts", 0]},
                            {"$divide": ["$climb_successes", "$climb_attempts"]},
                            0
                        ]},
                        100
                    ]
                },
                "defense_rating": {"$round": ["$defense_rating", 1]},
                "robot_disabled_list": "$robot_disabled_list",
                "herd_rating": {"$round": [{"$ifNull": ["$herd_rating", 0]}, 1]},
                "herd_count": 1,
                "ferrying_rating": {"$round": [{"$ifNull": ["$ferrying_rating", 0]}, 1]},
                "ferrying_count": 1
            }}
        ])
        if sort_field:
            pipeline.append({"$sort": {sort_field: -1}})
        return list(self.db.team_data.aggregate(pipeline))

    def get_scouter_leaderboard(self, event="all", scouter_team="all", sort_field="match_count") -> list[dict]:
        """Records per scouter across all teams, optionally filtered by event and scouter's team."""
        pipeline = [SCOUTER_LOOKUP, UNWIND_SCOUTER]
        if event != 'all':
            pipeline.append({"$match": {"event_code": event}})
        if scouter_team != 'all' and scouter_team.isdigit():
            pipeline.append({"$match": {"scouter.teamNumber": int(scouter_team)}})
        pipeline.extend([
            {
                "$group": {
                    "_id": "$scouter._id",
                    "username": {"$first": "$scouter.username"},
                    "teamNumber": {"$first": "$scouter.teamNumber"},
                    "match_count": {"$sum": 1},
                    "unique_teams": {"$addToSet": "$team_number"},
                }
            },
            {
                "$project": {
                    "username": 1,
                    "teamNumber": 1,
                    "match_count": 1,
                    "unique_teams_count": {"$size": "$unique_teams"},
                }
            },
            {"$sort": {sort_field: -1}}
        ])
        return list(self.db.team_data.aggregate(pipeline))

    def get_event_codes(self) -> list:
        """Every event code with match records, sorted."""
        return [evt["_id"] for evt in self.db.team_data.aggregate([
            {"$group": {"_id": "$event_code"}},
            {"$sort": {"_id": 1}}
        ])]

    def get_scouter_teams(self) -> list:
        """Team numbers of every scouter with match records, sorted."""
        return [team["_id"] for team in self.db.team_data.aggregate([
            SCOUTER_LOOKUP,
            UNWIND_SCOUTER,
            {"$match": {"scouter.teamNumber": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$scouter.teamNumber"}},
            {"$sort": {"_id": 1}}
        ])]

    # ============ Pit scouting ============

    @with_mongodb_retry(retries=3, delay=2)
    def add_pit_scouting(self, data: dict) -> bool:
        """Add new pit scouting data"""
        try:
            int(data["team_number"])
            data["scouter_id"] = ObjectId(data["scouter_id"])
            result = self.db.pit_scouting.insert_one(data)
            return bool(result.inserted_id)

        except Exception as e:
            logger.error(f"Error adding pit scouting data: {str(e)}")
            return False

    @with_mongodb_retry(retries=3, delay=2)
    def get_pit_scouting_by_id(self, entry_id: str) -> dict | None:
        """Get a single pit scouting record by its MongoDB _id"""
        try:
            result = list(self.db.pit_scouting.aggregate([
                {"$match": {"_id": ObjectId(entry_id)}},
                SCOUTER_LOOKUP,
                {"$unwind": {"path": "$scouter", "preserveNullAndEmptyArrays": True}},
                {"$project": PIT_PROJECTION}
            ]))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error fetching pit scouting data by id: {str(e)}")
            return None

    @with_mongodb_retry(retries=3, delay=2)
    def get_all_pit_scouting(self, user_team_number=None, user_id=None) -> list[dict]:
        """Get all pit scouting data with team-based access control"""
        try:
            return list(self.db.pit_scouting.aggregate([
                *self._visible_records(user_id, user_team_number),
                {"$project": {**PIT_PROJECTION, "created_at": 1, "updated_at": 1}},
            ]))
        except Exception as e:
            logger.error(f"Error fetching pit scouting data: {str(e)}", exc_info=True)
            return []

    @with_mongodb_retry(retries=3, delay=2)
    def update_pit_scouting(self, entry_id: str, data: dict, scouter_id: str) -> bool:
        """Update pit scouting data with ownership validation"""
        try:
            result = self.db.pit_scouting.update_one(
                {"_id": ObjectId(entry_id), "scouter_id": ObjectId(scouter_id)},
                {"$set": data}
            )
            if result.matched_count == 0:
                logger.warning(f"Pit data not found or permission denied for entry: {entry_id}")
                return False
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error updating pit scouting data: {str(e)}")
            return False

    @with_mongodb_retry(retries=3, delay=2)
    def delete_pit_scouting(self, entry_id: str, scouter_id: str) -> bool:
        """Delete pit scouting data"""
        try:
            result = self.db.pit_scouting.delete_one({
                "_id": ObjectId(entry_id),
                "scouter_id": ObjectId(scouter_id)
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting pit scouting data: {str(e)}")
            return False
