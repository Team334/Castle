from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timezone
from io import BytesIO
from typing import Dict, Optional, Tuple, Union

import gridfs
from bson.objectid import ObjectId
from PIL import Image, ImageDraw, ImageFont

from app.models import Assignment, Team, User
from app.utils import DatabaseManager, with_mongodb_retry, get_database_connection, get_gridfs
from flask import current_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Type aliases for better readability
TeamResult = Tuple[bool, Union[str, Team, Tuple[Team, User]]]
UserResult = Tuple[bool, Union[str, User]]
AssignmentResult = Tuple[bool, str]
DatabaseID = Union[str, ObjectId]

class TeamManager(DatabaseManager):
    """Handles all team-related operations"""
    
    def __init__(self, mongo_uri=None):
        # Use the singleton connection
        super().__init__(mongo_uri)
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        """Ensure required collections exist"""
        if "teams" not in self.db.list_collection_names():
            self.db.create_collection("teams")
            logger.info("Created teams collection")

    def generate_join_code(self) -> str:
        """Generate a unique 6-character join code"""
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            if not self.db.teams.find_one({"team_join_code": code}):
                return code

    async def _get_team(self, query: Dict) -> Optional[Team]:
        """Internal method to fetch team data"""
        try:
            if team_data := self.db.teams.find_one(query):
                return Team.create_from_db(team_data)
            return None
        except Exception as e:
            logger.error(f"Error fetching team: {str(e)}")
            return None

    @with_mongodb_retry()
    def get_team_by_number_sync(self, team_number: int) -> Optional[Team]:
        """Synchronous version of get_team_by_number"""
        
        if team_data := self.db.teams.find_one({"team_number": team_number}):
            return Team.create_from_db(team_data)
        return None

    @with_mongodb_retry()
    async def get_team_by_number(self, team_number: int) -> Optional[Team]:
        """Get team by team number"""
        
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
    async def create_team(self, team_number: int, creator_id: str, 
                         team_name: Optional[str] = None, 
                         description: Optional[str] = None, 
                         logo_id: Optional[str] = None) -> TeamResult:
        """Create a new team"""
        
        try:
            if await self.get_team_by_number(team_number):
                return False, "Team number already exists"
            
            # If no logo provided, create default
            if not logo_id:
                logo_bytes = self.create_default_team_logo(team_number)
                logo_id = get_gridfs().put(
                    logo_bytes,
                    filename=f"team_{team_number}_default_logo.png",
                    content_type='image/png'
                )

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
                "logo_id": str(logo_id)
            }

            result = self.db.teams.insert_one(team_data)

            # Update creator's team number
            self.db.users.update_one(
                {"_id": ObjectId(creator_id)},
                {"$set": {"teamNumber": team_number}}
            )

            return True, Team.create_from_db({"_id": result.inserted_id, **team_data})

        except Exception as e:
            logger.error(f"Error creating team: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def join_team(self, user_id: str, team_join_code: str):
        """Add a user to a team using the join code"""
        
        try:
            team_data = self.db.teams.find_one({"team_join_code": team_join_code})
            if not team_data:
                return False, "Invalid team join code"

            # Check if user is already in the team
            if user_id in team_data.get("users", []):
                return False, "User already in team"

            # Add user to team
            self.db.teams.update_one(
                {"_id": team_data["_id"]}, {"$addToSet": {"users": user_id}}
            )

            # Update user's team number
            self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"teamNumber": team_data["team_number"]}},
            )

            if updated_user := self.db.users.find_one({"_id": ObjectId(user_id)}):
                user = User.create_from_db(updated_user)
                logger.info(f"User {user_id} joined team {team_data['team_number']}")
                return True, (Team.create_from_db(team_data), user)

            return False, "Error updating user data"

        except Exception as e:
            logger.error(f"Error joining team: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def leave_team(self, user_id: str, team_number: int):
        """Remove a user from a team and remove their admin status"""
        
        try:
            # Get team to check if user is owner
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"

            # If owner is leaving, transfer ownership first
            if team.is_owner(user_id):
                success, message = await self.transfer_ownership(team_number)
                if not success:
                    return False, "Cannot leave team - no available users to transfer ownership to"

            # Remove user from team's users and admins lists
            result = self.db.teams.update_one(
                {"team_number": team_number},
                {"$pull": {"users": user_id, "admins": user_id}},
            )

            if result.modified_count == 0:
                return False, "User not found in team"

            # Remove team number from user
            self.db.users.update_one(
                {"_id": ObjectId(user_id)}, {"$unset": {"teamNumber": ""}}
            )

            logger.info(f"User {user_id} left team {team_number}")
            return True, "Successfully left team"

        except Exception as e:
            logger.error(f"Error leaving team: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def get_team_members(self, team_number: int):
        """Get all members of a team"""
        
        try:
            team = self.db.teams.find_one({"team_number": team_number})
            if not team:
                return []

            user_ids = team.get("users", [])
            users = self.db.users.find(
                {"_id": {"$in": [ObjectId(uid) for uid in user_ids]}}
            )
            return [User.create_from_db(user) for user in users]
        except Exception as e:
            logger.error(f"Error getting team members: {str(e)}")
            return []

    @with_mongodb_retry(retries=3, delay=2)
    async def add_admin(
        self, team_number: int, user_id: str, admin_id: str
    ) -> Tuple[bool, str]:
        """Add a new admin to the team"""
        
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
                {"team_number": team_number}, {"$addToSet": {"admins": user_id}}
            )

            if result.modified_count > 0:
                return True, "Admin added successfully"
            return False, "Failed to add admin"

        except Exception as e:
            logger.error(f"Error adding admin: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def remove_admin(
        self, team_number: int, user_id: str, admin_id: str
    ) -> Tuple[bool, str]:
        """Remove an admin from the team"""
        
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
                {"team_number": team_number}, {"$pull": {"admins": user_id}}
            )

            if result.modified_count > 0:
                return True, "Admin removed successfully"
            return False, "Failed to remove admin"

        except Exception as e:
            logger.error(f"Error removing admin: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def remove_user(self, team_number: int, user_id: str, admin_id: str):
        """Remove a user from a team (admin action)"""
        
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
                {"$pull": {"users": user_id, "admins": user_id}},
            )

            if result.modified_count == 0:
                return False, "User not found in team"

            # Update user's team number to None
            self.db.users.update_one(
                {"_id": ObjectId(user_id)}, {"$unset": {"teamNumber": ""}}
            )

            if updated_user := self.db.users.find_one({"_id": ObjectId(user_id)}):
                user = User.create_from_db(updated_user)
                return True, user

            return True, None

        except Exception as e:
            logger.error(f"Error removing user: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def create_or_update_assignment(self, team_number: int, assignment_data: dict, creator_id: str):
        """Create or update an assignment"""
        
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
            assignment["_id"] = result.inserted_id

            # Add assignment to team
            self.db.teams.update_one(
                {"team_number": team_number},
                {"$addToSet": {"assignments": str(result.inserted_id)}},
            )

            from app.notifications.notification_manager import NotificationManager
            import asyncio
            
            async def send_notifications():
                try:
                    # Reuse the existing database connection
                    notification_manager = NotificationManager(
                        self.mongo_uri,
                        vapid_private_key=current_app.config.get("VAPID_PRIVATE_KEY"),
                        vapid_claims={"sub": f"mailto:{current_app.config.get('VAPID_CLAIM_EMAIL')}"},
                        existing_connection=self.get_connection()
                    )
                    
                    # Use with context manager pattern to ensure proper cleanup
                    try:
                        await notification_manager.send_instant_assignment_notification(assignment, team_number)
                    finally:
                        # Don't close the connection here since it's shared
                        # Just remove the reference to the shared connection
                        notification_manager.client = None
                        notification_manager.db = None
                    
                except Exception as e:
                    logger.error(f"Background notification error: {str(e)}")

            # Start notification task in background
            asyncio.create_task(send_notifications())

            return True, "Assignment created successfully"
        except Exception as e:
            logger.error(f"Error creating/updating assignment: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    def update_assignment_status(
        self, assignment_id: str, user_id: str, new_status: str
    ):
        """Update the status of an assignment"""
        
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
                {"_id": ObjectId(assignment_id)}, {"$set": update_data}
            )

            return True, "Assignment status updated successfully"
        except Exception as e:
            logger.error(f"Error updating assignment status: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def get_team_assignments(self, team_number: int):
        """Get all assignments for a team"""
        
        try:
            assignments = self.db.assignments.find({"team_number": team_number})
            return [Assignment.create_from_db(assignment) for assignment in assignments]
        except Exception as e:
            logger.error(f"Error getting team assignments: {str(e)}")
            return []

    @with_mongodb_retry(retries=3, delay=2)
    async def clear_assignments(
        self, team_number: int, user_id: str
    ) -> Tuple[bool, str]:
        """Clear all assignments for a team if user is admin"""
        try:
            

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
            

            # Get the team to check owner status
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"

            # Check if user is owner
            if not team.is_owner(user_id):
                return False, "Only the team owner can delete the team"

            # Delete team logo from GridFS if it exists
            if team.logo_id:
                try:
                    # Delete the file and its chunks
                    get_gridfs().delete(team.logo_id)
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
                    {"_id": ObjectId(member_id)}, {"$set": {"teamNumber": None}}
                )

            return True, "Team deleted successfully"

        except Exception as e:
            logging.error(f"Error deleting team: {str(e)}")
            return False, "An error occurred while deleting the team"

    @with_mongodb_retry(retries=3, delay=2)
    async def delete_assignment(
        self, assignment_id: str, user_id: str
    ) -> Tuple[bool, str]:
        """Delete an assignment if user is admin"""
        try:
            

            # Get the assignment
            assignment = self.db.assignments.find_one({"_id": ObjectId(assignment_id)})
            if not assignment:
                return False, "Assignment not found"

            # Get the team to check admin status
            team = await self.get_team_by_number(assignment["team_number"])
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
    async def update_assignment(
        self, assignment_id: str, user_id: str, assignment_data: Dict
    ) -> Tuple[bool, str]:
        """Update an existing assignment"""
        
        try:
            # Get the assignment and team
            assignment = self.db.assignments.find_one({"_id": ObjectId(assignment_id)})
            if not assignment:
                return False, "Assignment not found"

            team = await self.get_team_by_number(assignment["team_number"])
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
                "updated_by": ObjectId(user_id),
            }

            result = self.db.assignments.update_one(
                {"_id": ObjectId(assignment_id)}, {"$set": update_data}
            )

            if result.modified_count > 0:
                return True, "Assignment updated successfully"
            return False, "No changes made to assignment"

        except Exception as e:
            logger.error(f"Error updating assignment: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def reset_user_team(self, user_id: str):
        """Reset user's team number to None"""
        
        try:
            result = self.db.users.update_one(
                {"_id": ObjectId(user_id)}, {"$unset": {"teamNumber": ""}}
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
        
        try:
            # Get the user's current team
            team = await self.get_team_by_number(team_number)

            # If team doesn't exist or user is not in the team
            if not team or user_id not in team.users:
                logger.warning(f"User {user_id} has invalid team number {team_number}")
                await self.reset_user_team(user_id)
                return (
                    False,
                    "Your team membership needs to be updated. Please join or create a team.",
                )

            return True, team
        except Exception as e:
            logger.error(f"Error validating user team: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def update_team_logo(self, team_number: int, new_logo_id) -> Tuple[bool, str]:
        """Update team logo and clean up old one"""
        try:
            # Get current team data
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"
            
            old_logo_id = team.logo_id
            
            # Update team with new logo
            result = self.db.teams.update_one(
                {"team_number": team_number},
                {"$set": {"logo_id": new_logo_id}}
            )
            
            if result.modified_count > 0:
                # Clean up old logo if it exists
                if old_logo_id:
                    try:
                        if get_gridfs().exists(old_logo_id):
                            get_gridfs().delete(old_logo_id)
                    except Exception as e:
                        logger.error(f"Error deleting old team logo: {str(e)}")
                        
                return True, "Team logo updated successfully"
            return False, "No changes made"
            
        except Exception as e:
            logger.error(f"Error updating team logo: {str(e)}")
            return False, "An internal error has occurred."

    def cleanup_gridfs(self):
        """Clean up orphaned chunks in GridFS"""
        try:
            # Get all file IDs from fs.files
            file_ids = {file['_id'] for file in self.db.fs.files.find({}, {'_id': 1})}

            # Delete chunks that don't have a corresponding file
            self.db.fs.chunks.delete_many({
                "files_id": {"$nin": list(file_ids)}
            })

            logger.info("GridFS cleanup completed successfully")
            return True
        except Exception as e:
            logger.error(f"Error during GridFS cleanup: {str(e)}")
            return False

    @with_mongodb_retry(retries=3, delay=2)
    async def update_team_info(self, team_number: int, updates: dict) -> Tuple[bool, str]:
        """Update team information"""
        try:
            # Filter out None values
            valid_updates = {k: v for k, v in updates.items() if v is not None}
            
            if not valid_updates:
                return False, "No changes to update"
            
            result = self.db.teams.update_one(
                {"team_number": team_number},
                {"$set": valid_updates}
            )
            
            if result.modified_count > 0:
                # Run cleanup after successful update
                self.cleanup_gridfs()
                return True, "Team information updated successfully"
            return False, "No changes made"
            
        except Exception as e:
            logger.error(f"Error updating team info: {str(e)}")
            return False, "An internal error has occurred."

    def create_default_team_logo(self, team_number: int) -> bytes:
        """Create a default team logo with centered text"""
        # Create a white background image
        img = Image.new('RGB', (200, 200), 'white')
        draw = ImageDraw.Draw(img)

        try:
            # Try to load custom font, fallback to default if not available
            font_large = ImageFont.truetype("./app/static/fonts/oxanium-vrb.ttf", 80)
            font_small = ImageFont.truetype("./app/static/fonts/oxanium-vrb.ttf", 40)
        except Exception:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Draw "Team" text
        team_text = "Team"
        bbox = draw.textbbox((0, 0), team_text, font=font_small)
        text_width = bbox[2] - bbox[0]
        x = (200 - text_width) / 2
        draw.text((x, 40), team_text, fill='black', font=font_small)

        # Draw team number
        number_text = str(team_number)
        bbox = draw.textbbox((0, 0), number_text, font=font_large)
        text_width = bbox[2] - bbox[0]
        x = (200 - text_width) / 2
        draw.text((x, 80), number_text, fill='black', font=font_large)

        # Save to BytesIO
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer.getvalue()

    @with_mongodb_retry(retries=3, delay=2)
    async def transfer_ownership(self, team_number: int):
        """Transfer team ownership to next admin or member"""
        
        try:
            team = await self.get_team_by_number(team_number)
            if not team:
                return False, "Team not found"

            # First try to find an admin to promote
            if team.admins:
                new_owner_id = team.admins[0]  # Take first admin
                team.admins.remove(new_owner_id)  # Remove from admins list
            # If no admins, take first regular member
            elif team.users:
                new_owner_id = team.users[0]
            else:
                # No users left, team should be deleted
                return False, "No users available to transfer ownership"

            # Update team with new owner
            result = self.db.teams.update_one(
                {"team_number": team_number},
                {
                    "$set": {"owner_id": ObjectId(new_owner_id)},
                    "$pull": {"admins": new_owner_id}
                }
            )

            if result.modified_count > 0:
                return True, "Ownership transferred successfully"
            return False, "Failed to transfer ownership"

        except Exception as e:
            logger.error(f"Error transferring ownership: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def get_user_team(self, user_id: str) -> Optional[Team]:
        """Get the team associated with a user"""
        
        try:
            # Find the user to get their team number
            user_data = self.db.users.find_one({"_id": ObjectId(user_id)})
            if not user_data or not user_data.get("teamNumber"):
                return None
                
            # Now get the team using the user's team number
            return await self.get_team_by_number(user_data["teamNumber"])
        except Exception as e:
            logger.error(f"Error getting user team: {str(e)}")
            return None
