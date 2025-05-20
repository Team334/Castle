from __future__ import annotations

import logging
from datetime import datetime, timezone

from bson import ObjectId

from app.models import TeamData
from app.utils import DatabaseManager, with_mongodb_retry

logger = logging.getLogger(__name__)


class ScoutingManager(DatabaseManager):
    def __init__(self, mongo_uri=None):
        # Use the singleton connection
        super().__init__(mongo_uri)
        self._ensure_collections()

    def _ensure_collections(self):
        """Ensure required collections exist"""
        collections = self.db.list_collection_names()
        if "team_data" not in collections:
            self._create_team_data_collection()
        if "pit_scouting" not in collections:
            self.db.create_collection("pit_scouting")
            self.db.pit_scouting.create_index([("team_number", 1)])
            self.db.pit_scouting.create_index([("scouter_id", 1)])
            logger.info("Created pit_scouting collection and indexes")

    
    def _create_team_data_collection(self):
        self.db.create_collection("team_data")
        self.db.team_data.create_index([("team_number", 1)])
        self.db.team_data.create_index([("scouter_id", 1)])
        logger.info("Created team_data collection and indexes")

    @with_mongodb_retry(retries=3, delay=2)
    def add_scouting_data(self, data, scouter_id):
        """Add new scouting data with retry mechanism"""
        # Ensure we have a valid connection
        # TODO: 2026

    @with_mongodb_retry(retries=3, delay=2)
    def get_all_scouting_data(self, user_team_number=None, user_id=None):
        """Get all scouting data with user information, filtered by team access"""
        # TODO: 2026

    @with_mongodb_retry(retries=3, delay=2)
    def get_team_data(self, team_id, scouter_id=None):
        """Get specific team data with optional scouter verification"""
        # TODO: 2026

    @with_mongodb_retry(retries=3, delay=2)
    def update_team_data(self, team_id, data, scouter_id):
        """Update existing team data if user is the owner"""
        # TODO: 2026

    @with_mongodb_retry(retries=3, delay=2)
    def delete_team_data(self, team_id, user_id, admin_override=False):
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

    @with_mongodb_retry(retries=3, delay=2)
    def has_team_data(self, team_number):
        """Check if there is any scouting data for a given team number"""
        try:
            count = self.db.team_data.count_documents({"team_number": int(team_number)})
            return count > 0
        except Exception as e:
            logger.error(f"Error checking team data: {str(e)}")
            return False

    @with_mongodb_retry(retries=3, delay=2)
    def get_team_stats(self, team_number):
        """Get comprehensive stats for a team"""
        # TODO: 2026

    @with_mongodb_retry(retries=3, delay=2)
    def get_team_matches(self, team_number):
        """Get all match data for a specific team"""
        # TODO: 2026

    @with_mongodb_retry(retries=3, delay=2)
    def get_auto_paths(self, team_number):
        """Get all auto paths for a specific team"""
        try:
            paths = list(self.db.team_data.find(
                {
                    "team_number": int(team_number),
                    "auto_path": {"$exists": True, "$ne": ""}
                },
                {
                    "match_number": 1,
                    "event_code": 1,
                    "auto_path": 1
                }
            ).sort("match_number", 1))

            return [
                {
                    "match_number": path.get("match_number", "Unknown"),
                    "event_code": path.get("event_code", "Unknown"),
                    "image_data": path["auto_path"],
                }
                for path in paths
                if path.get("auto_path")
            ]
        except Exception as e:
            logger.error(f"Error fetching auto paths for team {team_number}: {str(e)}")
            return []

    @with_mongodb_retry(retries=3, delay=2)
    def add_pit_scouting(self, data):
        """Add new pit scouting data with team validation"""
        try:
            team_number = int(data["team_number"])
            scouter_id = ObjectId(data["scouter_id"])  # Convert to ObjectId

            # Check if this team is already scouted by someone from the same team
            pipeline = [
                {
                    "$match": {
                        "team_number": team_number
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "scouter_id",
                        "foreignField": "_id",
                        "as": "scouter"
                    }
                },
                {"$unwind": "$scouter"}
            ]
            
            existing_entries = list(self.db.pit_scouting.aggregate(pipeline))
            current_user = self.db.users.find_one({"_id": scouter_id})
            
            for entry in existing_entries:
                if entry.get("scouter", {}).get("teamNumber") == current_user.get("teamNumber"):
                    logger.warning(f"Team {team_number} has already been pit scouted by team {current_user.get('teamNumber')}")
                    return False

            # Ensure scouter_id is ObjectId in the data
            data["scouter_id"] = scouter_id
            
            result = self.db.pit_scouting.insert_one(data)
            return bool(result.inserted_id)

        except Exception as e:
            logger.error(f"Error adding pit scouting data: {str(e)}")
            return False

    @with_mongodb_retry(retries=3, delay=2)
    def get_pit_scouting(self, team_number):
        """Get pit scouting data with scouter information"""
        try:
            pipeline = [
                {
                    "$match": {
                        "team_number": int(team_number)
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "scouter_id",
                        "foreignField": "_id",
                        "as": "scouter"
                    }
                },
                {
                    "$unwind": {
                        "path": "$scouter",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "team_number": 1,
                        "drive_type": 1,
                        "swerve_modules": 1,
                        "motor_details": 1,
                        "motor_count": 1,
                        "dimensions": 1,
                        "mechanisms": 1,
                        "programming_language": 1,
                        "autonomous_capabilities": 1,
                        "driver_experience": 1,
                        "notes": 1,
                        "scouter_id": "$scouter._id",
                        "scouter_name": "$scouter.username",
                        "scouter_team": "$scouter.teamNumber"
                    }
                }
            ]
            
            result = list(self.db.pit_scouting.aggregate(pipeline))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error fetching pit scouting data: {str(e)}")
            return None

    @with_mongodb_retry(retries=3, delay=2)
    def get_all_pit_scouting(self, user_team_number=None, user_id=None):
        """Get all pit scouting data with team-based access control"""
        try:
            logger.info(f"Fetching pit scouting data for user_id: {user_id}, team_number: {user_team_number}")

            # First check if we have any data at all in the collection
            total_count = self.db.pit_scouting.count_documents({})
            logger.info(f"Total documents in pit_scouting collection: {total_count}")

            # Log the raw documents for debugging
            # raw_docs = list(self.db.pit_scouting.find())
            # for doc in raw_docs:
                # logger.info(f"Raw pit scouting document: {doc}")
                # if 'scouter_id' in doc:
                    # scouter = self.db.users.find_one({"_id": doc['scouter_id']})
                    # logger.info(f"Associated scouter: {scouter}")

            # Log the user's info
            # user_info = self.db.users.find_one({"_id": ObjectId(user_id)})
            # logger.info(f"User info: {user_info}")

            # Add match stage for filtering based on team number or user ID
            if user_team_number:
                # If user has a team number, show data from their team and their own data
                match_stage = {
                    "$match": {
                        "$or": [
                            {"scouter.teamNumber": user_team_number},
                            {"scouter._id": ObjectId(user_id)}
                        ]
                    }
                }
                logger.info(f"Using team filter with team number: {user_team_number}")
            else:
                # If user has no team, only show their own data
                match_stage = {
                    "$match": {
                        "scouter._id": ObjectId(user_id)
                    }
                }
                logger.info("Using individual user filter")

            pipeline = [
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "scouter_id",
                        "foreignField": "_id",
                        "as": "scouter",
                    }
                },
                {"$unwind": "$scouter"},
                *(
                    match_stage,
                    {
                        "$project": {
                            "_id": 1,
                            "team_number": 1,
                            "drive_type": 1,
                            "swerve_modules": 1,
                            "motor_details": 1,
                            "motor_count": 1,
                            "dimensions": 1,
                            "mechanisms": 1,
                            "programming_language": 1,
                            "autonomous_capabilities": 1,
                            "driver_experience": 1,
                            "notes": 1,
                            "created_at": 1,
                            "updated_at": 1,
                            "scouter_id": "$scouter._id",
                            "scouter_name": "$scouter.username",
                            "scouter_team": "$scouter.teamNumber",
                        }
                    },
                ),
            ]
            # Log the full pipeline for debugging
            # logger.info(f"MongoDB pipeline: {pipeline}")

            # Execute the pipeline on the pit_scouting collection
            pit_data = list(self.db.pit_scouting.aggregate(pipeline))
            logger.info(f"Retrieved {len(pit_data)} pit scouting records")

            # Log the first record if any exist (excluding sensitive info)
            # if pit_data:
            #     sample_record = pit_data[0].copy()
            #     if "scouter_id" in sample_record:
            #         del sample_record["scouter_id"]
            #     logger.info(f"Sample record: {sample_record}")

            return pit_data

        except Exception as e:
            logger.error(f"Error fetching pit scouting data: {str(e)}", exc_info=True)
            return []

    @with_mongodb_retry(retries=3, delay=2)
    def update_pit_scouting(self, team_number, data, scouter_id):
        """Update pit scouting data with team validation"""
        try:
            # First verify ownership and get current data
            existing_data = self.db.pit_scouting.find_one(
                {"team_number": team_number}
            )

            if not existing_data:
                logger.warning(f"Pit data not found for team: {team_number}")
                return False

            # Check if this team is already scouted by someone else from the same team
            pipeline = [
                {
                    "$match": {
                        "team_number": team_number,
                        "_id": {"$ne": existing_data["_id"]}  # Exclude current entry
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "scouter_id",
                        "foreignField": "_id",
                        "as": "scouter"
                    }
                },
                {"$unwind": "$scouter"}
            ]
            
            existing_entries = list(self.db.pit_scouting.aggregate(pipeline))
            current_user = self.db.users.find_one({"_id": ObjectId(scouter_id)})
            
            for entry in existing_entries:
                if entry.get("scouter", {}).get("teamNumber") == current_user.get("teamNumber"):
                    logger.warning(
                        f"Update attempted for team {team_number} which is already pit scouted by team {current_user.get('teamNumber')}"
                    )
                    return False

            result = self.db.pit_scouting.update_one(
                {"team_number": team_number},
                {"$set": data}
            )
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error updating pit scouting data: {str(e)}")
            return False

    @with_mongodb_retry(retries=3, delay=2)
    def delete_pit_scouting(self, team_number, scouter_id):
        """Delete pit scouting data"""
        try:
            result = self.db.pit_scouting.delete_one({
                "team_number": int(team_number),
                "scouter_id": ObjectId(scouter_id)
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting pit scouting data: {str(e)}")
            return False
