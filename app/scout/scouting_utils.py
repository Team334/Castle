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
        
        # Fix any string scouter_ids in pit_scouting collection
        self._migrate_pit_scouting_scouter_ids()

    def _migrate_pit_scouting_scouter_ids(self):
        """Migrate string scouter_ids to ObjectId in pit_scouting collection"""
        try:
            # Find documents where scouter_id is a string
            for doc in self.db.pit_scouting.find({"scouter_id": {"$type": "string"}}):
                try:
                    # Convert string to ObjectId
                    self.db.pit_scouting.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"scouter_id": ObjectId(doc["scouter_id"])}}
                    )
                    logger.info(f"Migrated pit scouting document {doc['_id']} scouter_id to ObjectId")
                except Exception as e:
                    logger.error(f"Failed to migrate pit scouting document {doc['_id']}: {str(e)}")
        except Exception as e:
            logger.error(f"Error during pit scouting migration: {str(e)}")

    def _create_team_data_collection(self):
        self.db.create_collection("team_data")
        self.db.team_data.create_index([("team_number", 1)])
        self.db.team_data.create_index([("scouter_id", 1)])
        logger.info("Created team_data collection and indexes")

    @with_mongodb_retry(retries=3, delay=2)
    def add_scouting_data(self, data, scouter_id):
        """Add new scouting data with retry mechanism"""
        # Ensure we have a valid connection
        
        
        try:
            # Validate team number
            team_number = int(data["team_number"])
            if team_number <= 0:
                return False, "Invalid team number"

            # Lookup to check if this team is already scouted in this match by someone from the same team
            pipeline = [
                {
                    "$match": {
                        "event_code": data["event_code"],
                        "match_number": data["match_number"],
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
                {"$unwind": "$scouter"},
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "scouter.teamNumber",
                        "foreignField": "teamNumber",
                        "as": "team_scouters"
                    }
                }
            ]

            if existing_entries := list(self.db.team_data.aggregate(pipeline)):
                current_user = self.db.users.find_one({"_id": ObjectId(scouter_id)})
                for entry in existing_entries:
                    if entry.get("scouter", {}).get("teamNumber") == current_user.get("teamNumber"):
                        return False, f"Team {team_number} has already been scouted by your team in match {data['match_number']}"

            # Get existing match data to validate alliance sizes and calculate scores
            # match_data = list(self.db.team_data.find({
            #     "event_code": data["event_code"],
            #     "match_number": data["match_number"]
            # }))

            # Count teams per alliance
            alliance = data.get("alliance", "red")
            # red_teams = [m for m in match_data if m["alliance"] == "red"]
            # blue_teams = [m for m in match_data if m["alliance"] == "blue"]

            # if (alliance == "red" and len(red_teams) >= 3) or (alliance == "blue" and len(blue_teams) >= 3):
            #     return False, f"Cannot add more teams to {alliance} alliance (maximum 3)"

            # Process form data
            team_data = {
                "team_number": team_number,
                "event_code": data["event_code"],
                "match_number": data["match_number"],
                "alliance": alliance,

                # Auto Coral scoring
                "auto_coral_level1": int(data.get("auto_coral_level1", 0)),
                "auto_coral_level2": int(data.get("auto_coral_level2", 0)),
                "auto_coral_level3": int(data.get("auto_coral_level3", 0)),
                "auto_coral_level4": int(data.get("auto_coral_level4", 0)),

                # Teleop Coral scoring
                "teleop_coral_level1": int(data.get("teleop_coral_level1", 0)),
                "teleop_coral_level2": int(data.get("teleop_coral_level2", 0)),
                "teleop_coral_level3": int(data.get("teleop_coral_level3", 0)),
                "teleop_coral_level4": int(data.get("teleop_coral_level4", 0)),

                # Auto Algae scoring
                "auto_algae_net": int(data.get("auto_algae_net", 0)),
                "auto_algae_processor": int(data.get("auto_algae_processor", 0)),

                # Teleop Algae scoring
                "teleop_algae_net": int(data.get("teleop_algae_net", 0)),
                "teleop_algae_processor": int(data.get("teleop_algae_processor", 0)),

                # Climb
                "climb_type": data.get("climb_type", ""),
                "climb_success": bool(data.get("climb_success", False)),

                # Defense
                "defense_rating": int(data.get("defense_rating", 1)),
                "defense_notes": data.get("defense_notes", ""),

                # Mobility
                "mobility_rating": int(data.get("mobility_rating", 1)),
                "mobility_notes": data.get("mobility_notes", ""),

                # Durability
                "durability_rating": int(data.get("durability_rating", 1)),
                "durability_notes": data.get("durability_notes", ""),

                # Auto
                "auto_path": data.get("auto_path", ""),
                "auto_notes": data.get("auto_notes", ""),

                # Notes
                "notes": data.get("notes", ""),

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
    def get_all_scouting_data(self, user_team_number=None, user_id=None):
        """Get all scouting data with user information, filtered by team access"""
        try:
            # Base pipeline for user lookup
            pipeline = [
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "scouter_id",
                        "foreignField": "_id",
                        "as": "scouter"
                    }
                },
                {"$unwind": "$scouter"},
            ]

            # Add match stage for filtering based on team number or user ID
            if user_team_number:
                # If user has a team number, show data from their team and their own data
                pipeline.append({
                    "$match": {
                        "$or": [
                            {"scouter.teamNumber": user_team_number},
                            {"scouter._id": ObjectId(user_id)}
                        ]
                    }
                })
            else:
                # If user has no team, only show their own data
                pipeline.append({
                    "$match": {
                        "scouter._id": ObjectId(user_id)
                    }
                })

            # Project the needed fields
            pipeline.append({
                "$project": {
                    "_id": 1,
                    "team_number": 1,
                    "match_number": 1,
                    "event_code": 1,
                    "auto_coral_level1": 1,
                    "auto_coral_level2": 1,
                    "auto_coral_level3": 1,
                    "auto_coral_level4": 1,
                    "teleop_coral_level1": 1,
                    "teleop_coral_level2": 1,
                    "teleop_coral_level3": 1,
                    "teleop_coral_level4": 1,
                    "auto_algae_net": 1,
                    "auto_algae_processor": 1,
                    "teleop_algae_net": 1,
                    "teleop_algae_processor": 1,
                    "climb_type": 1,
                    "climb_success": 1,
                    "defense_rating": 1,
                    "defense_notes": 1,
                    "mobility_rating": 1,
                    "mobility_notes": 1,
                    "durability_rating": 1,
                    "durability_notes": 1,
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
            
            team_data = list(self.db.team_data.aggregate(pipeline))
            return team_data
        except Exception as e:
            logger.error(f"Error fetching team data: {str(e)}")
            return []

    @with_mongodb_retry(retries=3, delay=2)
    def get_team_data(self, team_id, scouter_id=None):
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
    def update_team_data(self, team_id, data, scouter_id):
        """Update existing team data if user is the owner"""
        try:
            # First verify ownership and get current data
            existing_data = self.db.team_data.find_one(
                {"_id": ObjectId(team_id)}
            )

            if not existing_data:
                logger.warning(f"Data not found for team_id: {team_id}")
                return False

            # Check if the team is already scouted by someone else from the same team
            pipeline = [
                {
                    "$match": {
                        "event_code": data["event_code"],
                        "match_number": data["match_number"],
                        "team_number": int(data["team_number"]),
                        "_id": {"$ne": ObjectId(team_id)}  # Exclude current entry
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
            
            existing_entries = list(self.db.team_data.aggregate(pipeline))
            current_user = self.db.users.find_one({"_id": ObjectId(scouter_id)})
            
            for entry in existing_entries:
                if entry.get("scouter", {}).get("teamNumber") == current_user.get("teamNumber"):
                    logger.warning(
                        f"Update attempted for team {data['team_number']} in match {data['match_number']} "
                        f"which is already scouted by team {current_user.get('teamNumber')}"
                    )
                    return False

            # Get match data to validate alliance sizes
            match_data = list(self.db.team_data.find({
                "event_code": data["event_code"],
                "match_number": data["match_number"],
                "_id": {"$ne": ObjectId(team_id)}  # Exclude current entry
            }))

            # Count teams per alliance
            alliance = data.get("alliance", "red")
            red_teams = [m for m in match_data if m["alliance"] == "red"]
            blue_teams = [m for m in match_data if m["alliance"] == "blue"]

            if ((alliance == "red" and len(red_teams) >= 3) or (alliance == "blue" and len(blue_teams) >= 3)) and existing_data.get("alliance") != alliance:
                return False

            updated_data = {
                "team_number": int(data["team_number"]),
                "event_code": data["event_code"],
                "match_number": data["match_number"],
                "alliance": alliance,
                
                # Coral scoring
                "coral_level1": int(data.get("coral_level1", 0)),
                "coral_level2": int(data.get("coral_level2", 0)),
                "coral_level3": int(data.get("coral_level3", 0)),
                "coral_level4": int(data.get("coral_level4", 0)),
                
                # Algae scoring
                "algae_net": int(data.get("algae_net", 0)),
                "algae_processor": int(data.get("algae_processor", 0)),

                # Climb
                "climb_type": data.get("climb_type", ""),
                "climb_success": bool(data.get("climb_success", False)),
                
                # Defense
                "defense_rating": int(data.get("defense_rating", 1)),
                "defense_notes": data.get("defense_notes", ""),

                # Mobility
                "mobility_rating": int(data.get("mobility_rating", 1)),
                "mobility_notes": data.get("mobility_notes", ""),

                # Durability
                "durability_rating": int(data.get("durability_rating", 1)),
                "durability_notes": data.get("durability_notes", ""),

                # Auto
                "auto_path": data.get("auto_path", ""),
                "auto_notes": data.get("auto_notes", ""),
                
                # Notes
                "notes": data.get("notes", ""),
                
                # Auto Coral scoring
                "auto_coral_level1": int(data.get("auto_coral_level1", 0)),
                "auto_coral_level2": int(data.get("auto_coral_level2", 0)),
                "auto_coral_level3": int(data.get("auto_coral_level3", 0)),
                "auto_coral_level4": int(data.get("auto_coral_level4", 0)),
                
                # Teleop Coral scoring
                "teleop_coral_level1": int(data.get("teleop_coral_level1", 0)),
                "teleop_coral_level2": int(data.get("teleop_coral_level2", 0)),
                "teleop_coral_level3": int(data.get("teleop_coral_level3", 0)),
                "teleop_coral_level4": int(data.get("teleop_coral_level4", 0)),
                
                # Auto Algae scoring
                "auto_algae_net": int(data.get("auto_algae_net", 0)),
                "auto_algae_processor": int(data.get("auto_algae_processor", 0)),
                
                # Teleop Algae scoring
                "teleop_algae_net": int(data.get("teleop_algae_net", 0)),
                "teleop_algae_processor": int(data.get("teleop_algae_processor", 0)),
            }

            result = self.db.team_data.update_one(
                {"_id": ObjectId(team_id)},
                {"$set": updated_data},
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating team data: {str(e)}")
            return False

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
        try:
            pipeline = [
                {"$match": {"team_number": int(team_number)}},
                {
                    "$group": {
                        "_id": "$team_number",
                        "matches_played": {"$sum": 1},
                        "total_coral": {
                            "$sum": {
                                "$add": [
                                    "$coral_level1",
                                    "$coral_level2",
                                    "$coral_level3",
                                    "$coral_level4"
                                ]
                            }
                        },
                        "total_algae": {
                            "$sum": {"$add": ["$algae_net", "$algae_processor"]}
                        },
                        "successful_climbs": {
                            "$sum": {"$cond": ["$climb_success", 1, 0]}
                        },
                        "total_defense": {"$sum": "$defense_rating"},
                        "total_points": {"$sum": "$total_points"}
                    }
                }
            ]
            
            result = list(self.db.team_data.aggregate(pipeline))
            if not result:
                return {
                    "matches_played": 0,
                    "total_coral": 0,
                    "total_algae": 0,
                    "successful_climbs": 0,
                    "total_defense": 0,
                    "total_points": 0
                }
            
            stats = result[0]
            stats.pop("_id")  # Remove MongoDB ID
            return stats
        except Exception as e:
            logger.error(f"Error getting team stats: {str(e)}")
            return None

    @with_mongodb_retry(retries=3, delay=2)
    def get_team_matches(self, team_number):
        """Get all match data for a specific team"""
        try:
            pipeline = [
                {"$match": {"team_number": int(team_number)}},
                {"$sort": {"event_code": 1, "match_number": 1}},
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

            return list(self.db.team_data.aggregate(pipeline))
        except Exception as e:
            logger.error(f"Error getting team matches: {str(e)}")
            return []

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
