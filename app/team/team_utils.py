from functools import wraps
import secrets
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
from bson.objectid import ObjectId
from datetime import datetime, timezone
from app.models import Team, User, Assignment
import logging
import time
import random
import string

from typing import Dict, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def with_mongodb_retry(retries=3, delay=2):
    def decorator(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries):
                try:
                    return await f(*args, **kwargs)
                except (ServerSelectionTimeoutError, ConnectionFailure) as e:
                    last_error = e
                    if attempt < retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {retries} attempts failed: {str(e)}")
            raise last_error
        return wrapper
    return decorator

class TeamManager:
    def __init__(self, mongo_uri):
        self.mongo_uri = mongo_uri
        self.client = None
        self.db = None
        self.connect()

    def connect(self):
        """Establish connection to MongoDB with basic error handling"""
        try:
            if self.client is None:
                self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
                self.client.server_info()
                self.db = self.client.get_default_database()
                logger.info("Successfully connected to MongoDB")

                # Ensure teams collection exists
                if "teams" not in self.db.list_collection_names():
                    self.db.create_collection("teams")
                    logger.info("Created teams collection")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    def ensure_connected(self):
        """Ensure we have a valid connection, reconnect if necessary"""
        try:
            if self.client is None:
                self.connect()
            else:
                self.client.server_info()
        except Exception:
            logger.warning("Lost connection to MongoDB, attempting to reconnect...")
            self.connect()

    def generate_join_code(self):
        """Generate a unique 6-character join code"""
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            if not self.db.teams.find_one({"team_join_code": code}):
                return code

    @with_mongodb_retry(retries=3, delay=2)
    async def create_team(self, team_number: int, creator_id: str, team_name: str = None, 
                     description: str = None, logo_id: str = None):
        """Create a new team with the given parameters"""
        self.ensure_connected()
        try:
            if existing_team := self.db.teams.find_one({"team_number": team_number}):
                return False, "Team number already exists"

            # Convert logo_id to ObjectId if provided
            logo_object_id = ObjectId(logo_id) if logo_id else None

            team_data = {
                "team_number": team_number,
                "team_join_code": self.generate_join_code(),
                "users": [creator_id],
                "admins": [creator_id],
                "owner_id": creator_id,
                "created_at": datetime.now(timezone.utc),
                "created_by": creator_id,
                "team_name": team_name,
                "description": description,
                "logo_id": logo_object_id
            }

            result = self.db.teams.insert_one(team_data)

            # Update creator's team number
            self.db.users.update_one(
                {"_id": ObjectId(creator_id)},
                {"$set": {"teamNumber": team_number}}
            )

            # Create team object with the inserted data
            team = Team.create_from_db({"_id": result.inserted_id, **team_data})
            return True, team

        except Exception as e:
            logger.error(f"Error creating team: {str(e)}")
            return False, f"Failed to create team: {str(e)}"

    @with_mongodb_retry(retries=3, delay=2)
    async def join_team(self, user_id: str, team_join_code: str):
        """Add a user to a team using the join code"""
        self.ensure_connected()
        try:
            team_data = self.db.teams.find_one({"team_join_code": team_join_code})
            if not team_data:
                return False, "Invalid team join code"

            # Check if user is already in the team
            if user_id in team_data.get("users", []):
                return False, "User already in team"

            # Add user to team
            self.db.teams.update_one(
                {"_id": team_data["_id"]}, 
                {"$addToSet": {"users": user_id}}
            )

            # Update user's team number
            self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"teamNumber": team_data["team_number"]}}
            )

            # Get updated user data
            updated_user = self.db.users.find_one({"_id": ObjectId(user_id)})
            if updated_user:
                user = User.create_from_db(updated_user)
                logger.info(f"User {user_id} joined team {team_data['team_number']}")
                return True, (Team.create_from_db(team_data), user)
            
            return False, "Error updating user data"

        except Exception as e:
            logger.error(f"Error joining team: {str(e)}")
            return False, f"Error joining team: {str(e)}"

    @with_mongodb_retry(retries=3, delay=2)
    async def leave_team(self, user_id: str, team_number: int):
        """Remove a user from a team and remove their admin status"""
        self.ensure_connected()
        try:
            # Get team to check if user is owner
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"
            
            # Don't allow owner to leave (they must delete the team)
            if team.is_owner(user_id):
                return False, "Team owner cannot leave. Please delete the team instead."

            # Remove user from team's users and admins lists
            result = self.db.teams.update_one(
                {"team_number": team_number}, 
                {
                    "$pull": {
                        "users": user_id,
                        "admins": user_id
                    }
                }
            )

            if result.modified_count == 0:
                return False, "User not found in team"

            # Remove team number from user
            self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$unset": {"teamNumber": ""}}
            )

            logger.info(f"User {user_id} left team {team_number}")
            return True, "Successfully left team"

        except Exception as e:
            logger.error(f"Error leaving team: {str(e)}")
            return False, f"Error leaving team: {str(e)}"

    @with_mongodb_retry(retries=3, delay=2)
    async def get_team_by_number(self, team_number: int):
        """Get team by team number"""
        self.ensure_connected()
        try:
            if team_number is None:
                logger.warning("get_team_by_number called with None team_number")
                return None
            
            team_data = self.db.teams.find_one({"team_number": team_number})
            if team_data is None:
                logger.warning(f"No team found with team_number: {team_number}")
                return None
            
            return Team.create_from_db(team_data)
        except Exception as e:
            logger.error(f"Error getting team: {str(e)}")
            return None

    @with_mongodb_retry(retries=3, delay=2)
    async def get_team_members(self, team_number: int):
        """Get all members of a team"""
        self.ensure_connected()
        try:
            team = self.db.teams.find_one({"team_number": team_number})
            if not team:
                return []
            
            user_ids = team.get("users", [])
            users = self.db.users.find({"_id": {"$in": [ObjectId(uid) for uid in user_ids]}})
            return [User.create_from_db(user) for user in users]
        except Exception as e:
            logger.error(f"Error getting team members: {str(e)}")
            return []

    @with_mongodb_retry(retries=3, delay=2)
    async def add_admin(self, team_number: int, user_id: str, admin_id: str) -> Tuple[bool, str]:
        """Add a new admin to the team"""
        self.ensure_connected()
        try:
            # Get the team to check owner status
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"
            
            # Check if the requesting user is the owner
            if not team.is_owner(admin_id):
                return False, "Only team owner can add new admins"

            # Check if the user is a team member
            if user_id not in team.users:
                return False, "User is not a member of this team"

            # Check if user is already an admin
            if user_id in team.admins:
                return False, "User is already an admin"

            # Add the user as an admin
            result = self.db.teams.update_one(
                {"team_number": team_number},
                {"$addToSet": {"admins": user_id}}
            )

            if result.modified_count > 0:
                return True, "Admin added successfully"
            return False, "Failed to add admin"

        except Exception as e:
            logger.error(f"Error adding admin: {str(e)}")
            return False, f"Error adding admin: {str(e)}"

    @with_mongodb_retry(retries=3, delay=2)
    async def remove_admin(self, team_number: int, user_id: str, admin_id: str) -> Tuple[bool, str]:
        """Remove an admin from the team"""
        self.ensure_connected()
        try:
            # Get the team to check owner status
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"
            
            # Check if the requesting user is the owner
            if not team.is_owner(admin_id):
                return False, "Only team owner can remove admins"

            # Can't remove the owner from admin status
            if team.is_owner(user_id):
                return False, "Cannot remove admin status from team owner"

            # Check if the user is actually an admin
            if user_id not in team.admins:
                return False, "User is not an admin"

            # Remove the user from admins
            result = self.db.teams.update_one(
                {"team_number": team_number},
                {"$pull": {"admins": user_id}}
            )

            if result.modified_count > 0:
                return True, "Admin removed successfully"
            return False, "Failed to remove admin"

        except Exception as e:
            logger.error(f"Error removing admin: {str(e)}")
            return False, f"Error removing admin: {str(e)}"

    @with_mongodb_retry(retries=3, delay=2)
    async def remove_user(self, team_number: int, user_id: str, admin_id: str):
        """Remove a user from a team (admin action)"""
        self.ensure_connected()
        try:
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"

            # Check if admin has permission
            if not team.is_admin(admin_id):
                return False, "Only team admins can remove users"

            # Can't remove the owner
            if team.is_owner(user_id):
                return False, "Cannot remove the team owner"

            # Remove user from team
            result = self.db.teams.update_one(
                {"team_number": team_number},
                {"$pull": {"users": user_id, "admins": user_id}}
            )

            if result.modified_count == 0:
                return False, "User not found in team"

            # Update user's team number to None
            self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$unset": {"teamNumber": ""}}
            )

            # Get updated user data
            updated_user = self.db.users.find_one({"_id": ObjectId(user_id)})
            if updated_user:
                user = User.create_from_db(updated_user)
                return True, user

            return True, None

        except Exception as e:
            logger.error(f"Error removing user: {str(e)}")
            return False, f"Error removing user: {str(e)}"

    @with_mongodb_retry(retries=3, delay=2)
    async def create_assignment(self, team_number: int, creator_id: str, assignment_data: Dict):
        """Create a new assignment for the team"""
        self.ensure_connected()
        try:
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"
            
            if not team.is_admin(creator_id):
                return False, "Only team admins can create assignments"

            assignment = {
                "team_number": team_number,
                "title": assignment_data.get("title"),
                "description": assignment_data.get("description", ""),
                "assigned_to": assignment_data.get("assigned_to", []),
                "status": "pending",
                "due_date": assignment_data.get("due_date"),
                "created_by": ObjectId(creator_id),
                "created_at": datetime.now(timezone.utc),
            }

            result = self.db.assignments.insert_one(assignment)
            
            # Add assignment to team
            self.db.teams.update_one(
                {"team_number": team_number},
                {"$addToSet": {"assignments": str(result.inserted_id)}}
            )

            return True, Assignment.create_from_db({"_id": result.inserted_id, **assignment})
        except Exception as e:
            logger.error(f"Error creating assignment: {str(e)}")
            return False, f"Error creating assignment: {str(e)}"

    @with_mongodb_retry(retries=3, delay=2)
    async def update_assignment_status(self, assignment_id: str, user_id: str, new_status: str):
        """Update the status of an assignment"""
        self.ensure_connected()
        try:
            assignment = self.db.assignments.find_one({"_id": ObjectId(assignment_id)})
            if not assignment:
                return False, "Assignment not found"

            if user_id not in assignment.get("assigned_to", []):
                return False, "User is not assigned to this task"

            update_data = {"status": new_status}
            if new_status == "completed":
                update_data["completed_at"] = datetime.now(timezone.utc)

            self.db.assignments.update_one(
                {"_id": ObjectId(assignment_id)},
                {"$set": update_data}
            )

            return True, "Assignment status updated successfully"
        except Exception as e:
            logger.error(f"Error updating assignment status: {str(e)}")
            return False, f"Error updating assignment status: {str(e)}"

    @with_mongodb_retry(retries=3, delay=2)
    async def get_team_assignments(self, team_number: int):
        """Get all assignments for a team"""
        self.ensure_connected()
        try:
            assignments = self.db.assignments.find({"team_number": team_number})
            return [Assignment.create_from_db(assignment) for assignment in assignments]
        except Exception as e:
            logger.error(f"Error getting team assignments: {str(e)}")
            return []

    @with_mongodb_retry(retries=3, delay=2)
    async def clear_assignments(self, team_number: int, user_id: str) -> Tuple[bool, str]:
        """Clear all assignments for a team if user is admin"""
        try:
            self.ensure_connected()
            
            # Get the team to check admin status
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"
            
            # Check if user is admin
            if not team.is_admin(user_id):
                return False, "You don't have permission to clear assignments"
            
            # Delete all assignments for the team
            result = self.db.assignments.delete_many({"team_number": team_number})
            
            if result.deleted_count > 0:
                return True, f"Successfully cleared {result.deleted_count} assignments"
            return True, "No assignments to clear"
            
        except Exception as e:
            logging.error(f"Error clearing assignments: {str(e)}")
            return False, "An error occurred while clearing assignments"

    @with_mongodb_retry(retries=3, delay=2)
    async def delete_team(self, team_number: int, user_id: str) -> Tuple[bool, str]:
        """Delete a team and all associated data if user is owner"""
        try:
            self.ensure_connected()
            
            # Get the team to check owner status
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"
            
            # Check if user is owner
            if not team.is_owner(user_id):
                return False, "Only the team owner can delete the team"
            
            # Delete team logo from GridFS if it exists
            if team.logo_id:
                from gridfs import GridFS
                fs = GridFS(self.db)
                try:
                    # Delete the file and its chunks
                    fs.delete(team.logo_id)
                except Exception as e:
                    logger.error(f"Error deleting team logo: {str(e)}")
            
            # Get all team members before deletion
            team_members = team.users

            # Delete all team data
            self.db.teams.delete_one({"team_number": team_number})
            self.db.assignments.delete_many({"team_number": team_number})
            
            # Update all team members to remove team number
            for member_id in team_members:
                self.db.users.update_one(
                    {"_id": ObjectId(member_id)},
                    {"$set": {"teamNumber": None}}
                )
            
            return True, "Team deleted successfully"
            
        except Exception as e:
            logging.error(f"Error deleting team: {str(e)}")
            return False, "An error occurred while deleting the team"

    async def delete_assignment(self, assignment_id: str, user_id: str) -> Tuple[bool, str]:
        """Delete an assignment if user is admin"""
        try:
            self.ensure_connected()
            
            # Get the assignment
            assignment = self.db.assignments.find_one({"_id": ObjectId(assignment_id)})
            if not assignment:
                return False, "Assignment not found"
            
            # Get the team to check admin status
            team = await self.get_team_by_number(assignment['team_number'])
            if not team:
                return False, "Team not found"
            
            # Check if user is admin
            if not team.is_admin(user_id):
                return False, "You don't have permission to delete assignments"
            
            # Delete the assignment
            result = self.db.assignments.delete_one({"_id": ObjectId(assignment_id)})
            
            if result.deleted_count > 0:
                return True, "Assignment deleted successfully"
            return False, "Failed to delete assignment"
            
        except Exception as e:
            logging.error(f"Error deleting assignment: {str(e)}")
            return False, "An error occurred while deleting the assignment"

    @with_mongodb_retry(retries=3, delay=2)
    async def update_assignment(self, assignment_id: str, user_id: str, assignment_data: Dict) -> Tuple[bool, str]:
        """Update an existing assignment"""
        self.ensure_connected()
        try:
            # Get the assignment and team
            assignment = self.db.assignments.find_one({"_id": ObjectId(assignment_id)})
            if not assignment:
                return False, "Assignment not found"
            
            team = await self.get_team_by_number(assignment['team_number'])
            if not team:
                return False, "Team not found"
            
            # Check if user has permission (must be admin)
            if not team.is_admin(user_id):
                return False, "Only team admins can edit assignments"

            # Update the assignment
            update_data = {
                "title": assignment_data.get("title"),
                "description": assignment_data.get("description"),
                "assigned_to": assignment_data.get("assigned_to"),
                "due_date": assignment_data.get("due_date"),
                "updated_at": datetime.now(timezone.utc),
                "updated_by": ObjectId(user_id)
            }

            result = self.db.assignments.update_one(
                {"_id": ObjectId(assignment_id)},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                return True, "Assignment updated successfully"
            return False, "No changes made to assignment"

        except Exception as e:
            logger.error(f"Error updating assignment: {str(e)}")
            return False, f"Error updating assignment: {str(e)}"

    @with_mongodb_retry(retries=3, delay=2)
    async def reset_user_team(self, user_id: str):
        """Reset user's team number to None"""
        self.ensure_connected()
        try:
            result = self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$unset": {"teamNumber": ""}}
            )
            if result.modified_count > 0:
                logger.info(f"Reset team number for user {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error resetting user team: {str(e)}")
            return False

    @with_mongodb_retry(retries=3, delay=2)
    async def validate_user_team(self, user_id: str, team_number: int):
        """Validate that a user's team exists and update if it doesn't"""
        self.ensure_connected()
        try:
            # Get the user's current team
            team = await self.get_team_by_number(team_number)
            
            # If team doesn't exist or user is not in the team
            if not team or user_id not in team.users:
                logger.warning(f"User {user_id} has invalid team number {team_number}")
                await self.reset_user_team(user_id)
                return False, "Your team membership needs to be updated. Please join or create a team."
            
            return True, team
        except Exception as e:
            logger.error(f"Error validating user team: {str(e)}")
            return False, f"Error validating team membership: {str(e)}"

    def __del__(self):
        """Cleanup MongoDB connection"""
        if self.client:
            self.client.close()