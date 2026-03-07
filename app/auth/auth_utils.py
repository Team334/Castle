from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from flask_login import current_user
from werkzeug.security import generate_password_hash

from app.models import User
from app.utils import (DatabaseManager, allowed_file, get_gridfs,
                       with_mongodb_retry)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_password_strength(password):
    """
    Check if password meets minimum requirements:
    - At least 8 characters
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    return True, "Password meets all requirements"


class UserManager(DatabaseManager):
    def __init__(self, mongo_uri=None):
        super().__init__(mongo_uri)
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        """Ensure required collections exist"""
        if "users" not in self.db.list_collection_names():
            self.db.create_collection("users")
            logger.info("Created users collection")

    @with_mongodb_retry(retries=3, delay=2)
    async def create_user(
        self,
        email,
        username,
        password,
        team_number=None
    ) -> tuple[bool, str]:
        """Create a new user with retry mechanism"""
        
        try:
            # Check for existing email
            if self.db.users.find_one({"email": email}):
                return False, "Email already registered"

            # Check for existing username
            if self.db.users.find_one({"username": username}):
                return False, "Username already taken"

            # Check password strength
            password_valid, message = await check_password_strength(password)
            if not password_valid:
                return False, message

            # Create user document
            user_data = {
                "email": email,
                "username": username,
                "teamNumber": team_number,
                "password_hash": generate_password_hash(password),
                "created_at": datetime.now(timezone.utc),
                "last_login": None,
                "description": "",
                "profile_picture_id": None,
            }

            self.db.users.insert_one(user_data)
            logger.info(f"Created new user: {username}")
            return True, "User created successfully"

        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def authenticate_user(self, login: str, password: str) -> tuple[bool, User | None]:
        """Authenticate user with retry mechanism"""
        
        try:
            if user_data := self.db.users.find_one(
                {"$or": [{"email": login}, {"username": login}]}
            ):
                user = User.create_from_db(user_data)
                if user and user.check_password(password):
                    # Update last login
                    self.db.users.update_one(
                        {"_id": user._id},
                        {"$set": {"last_login": datetime.now(timezone.utc)}},
                    )
                    logger.info(f"Successful login: {login}")
                    return True, user
            logger.warning(f"Failed login attempt: {login}")
            return False, None
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False, None

    @with_mongodb_retry(retries=3, delay=2)
    def get_user_by_id(self, user_id: str) -> User | None:
        """Retrieve user by ID with retry mechanism"""
        
        try:
            from bson.objectid import ObjectId

            user_data = self.db.users.find_one({"_id": ObjectId(user_id)})
            return User.create_from_db(user_data) if user_data else None
        except Exception as e:
            logger.error(f"Error loading user: {str(e)}")
            return None

    @with_mongodb_retry(retries=3, delay=2)
    async def update_user_profile(self, user_id: str, updates: dict) -> tuple[bool, str]:
        """Update user profile information"""
        
        try:
            from bson.objectid import ObjectId

            # Filter out None values and empty strings
            valid_updates = {k: v for k, v in updates.items() if v is not None and v != ""}

            # Check if username is being updated and is unique
            if 'username' in valid_updates:
                if existing_user := self.db.users.find_one(
                    {
                        "username": valid_updates['username'],
                        "_id": {"$ne": ObjectId(user_id)},
                    }
                ):
                    return False, "Username already taken"

            result = self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": valid_updates}
            )

            if result.modified_count > 0:
                return True, "Profile updated successfully"
            return False, "No changes made"

        except Exception as e:
            logger.error(f"Error updating profile: {str(e)}")
            return False, "An internal error has occurred."

    def get_user_profile(self, username: str) -> User | None:
        """Get user profile by username"""
        
        try:
            user_data = self.db.users.find_one({"username": username})
            return User.create_from_db(user_data) if user_data else None
        except Exception as e:
            logger.error(f"Error loading profile: {str(e)}")
            return None

    @with_mongodb_retry(retries=3, delay=2)
    async def update_profile_picture(self, user_id: str, file_id: str) -> tuple[bool, str]:
        """Update user's profile picture and clean up old one"""
        
        try:
            from bson.objectid import ObjectId

            # Get the old profile picture ID first
            user_data = self.db.users.find_one({"_id": ObjectId(user_id)})
            old_picture_id = user_data.get('profile_picture_id') if user_data else None
            
            # Update the profile picture ID
            result = self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"profile_picture_id": file_id}}
            )
            
            # If update was successful and there was an old picture, delete it
            if result.modified_count > 0 and old_picture_id:
                try:
                    if get_gridfs().exists(ObjectId(old_picture_id)):
                        get_gridfs().delete(ObjectId(old_picture_id))
                        logger.info(f"Deleted old profile picture: {old_picture_id}")
                except Exception as e:
                    logger.error(f"Error deleting old profile picture: {str(e)}")
            
            return True, "Profile picture updated successfully"
            
        except Exception as e:
            logger.error(f"Error updating profile picture: {str(e)}")
            return False, "An internal error has occurred."

    def get_profile_picture(self, user_id: str) -> str | None:
        """Get user's profile picture ID"""
        
        try:
            from bson.objectid import ObjectId
            user_data = self.db.users.find_one({"_id": ObjectId(user_id)})
            return user_data.get('profile_picture_id') if user_data else None
        except Exception as e:
            logger.error(f"Error getting profile picture: {str(e)}")
            return None

    @with_mongodb_retry(retries=3, delay=2)
    async def delete_user(self, user_id: str) -> tuple[bool, str]:
        """Delete a user account and all associated data"""
        
        try:
            from bson.objectid import ObjectId

            # Get user data first
            user_data = self.db.users.find_one({"_id": ObjectId(user_id)})
            if not user_data:
                return False, "User not found"

            # Delete profile picture if exists
            if user_data.get('profile_picture_id'):
                try:
                    get_gridfs().delete(ObjectId(user_data['profile_picture_id']))
                except Exception as e:
                    logger.error(f"Error deleting profile picture: {str(e)}")

            # Delete user document
            result = self.db.users.delete_one({"_id": ObjectId(user_id)})
            
            if result.deleted_count > 0:
                return True, "Account deleted successfully"
            return False, "Failed to delete account"

        except Exception as e:
            logger.error(f"Error deleting user: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def change_password(self, user_id: str, current_password: str, new_password: str) -> tuple[bool, str]:
        """Change user password after verifying current password"""
        
        try:            
            # Get user data
            user_data = self.db.users.find_one({"_id": ObjectId(user_id)})
            if not user_data:
                return False, "User not found"
            
            # Check for account lockout due to too many failed attempts
            failed_attempts = user_data.get('failed_password_change_attempts', 0)
            last_failed = user_data.get('last_failed_password_change')
            
            if failed_attempts >= 5 and last_failed:
                # Lock for 15 minutes after 5 failed attempts
                time_since = (datetime.now(timezone.utc) - last_failed).total_seconds()
                if time_since < 900:  # 15 minutes
                    mins_left = int((900 - time_since) / 60) + 1
                    return False, f"Too many failed attempts. Try again in {mins_left} minutes"
            
            # Create user object to verify current password
            user = User.create_from_db(user_data)
            if not user.check_password(current_password):
                # Track failed attempt
                self.db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {
                        "$set": {"last_failed_password_change": datetime.now(timezone.utc)},
                        "$inc": {"failed_password_change_attempts": 1}
                    }
                )
                return False, "Current password is incorrect"
            
            # Check new password strength
            password_valid, message = await check_password_strength(new_password)
            if not password_valid:
                return False, message
            
            # Update password and reset failed attempts
            result = self.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "password_hash": generate_password_hash(new_password),
                        "password_changed_at": datetime.now(timezone.utc),
                        "failed_password_change_attempts": 0
                    },
                    "$unset": {"last_failed_password_change": ""}
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Password changed for user: {user.username}")
                return True, "Password changed successfully"
            return False, "Failed to update password"
            
        except Exception as e:
            logger.error(f"Error changing password: {str(e)}")
            return False, "An internal error has occurred."

    @with_mongodb_retry(retries=3, delay=2)
    async def update_user_settings(self, user_id: str, form_data: dict, profile_picture=None) -> tuple[bool, Optional[str]]:
        """Update user settings including profile picture"""
        
        try:
            updates = {}
            
            # Handle username update if provided
            if new_username := form_data.get('username'):
                if new_username != current_user.username:
                    # Check if username is taken
                    if self.db.users.find_one({"username": new_username}):
                        return False, "Username is already taken"
                    updates['username'] = new_username

            # Handle description update
            if description := form_data.get('description'):
                updates['description'] = description

            # Handle profile picture
            if profile_picture and allowed_file(profile_picture.filename):
                from werkzeug.utils import secure_filename
                if profile_picture and allowed_file(profile_picture.filename):
                    filename = secure_filename(profile_picture.filename)
                    file_id = get_gridfs().put(
                        profile_picture.stream.read(),
                        filename=filename,
                        content_type=profile_picture.content_type
                    )
                    updates['profile_picture_id'] = file_id

            if updates:
                success, message = await self.update_user_profile(user_id, updates)
                return success, message

            return True, "Profile updated successfully"
        except Exception as e:
            logger.error(f"Error updating user settings: {str(e)}")
            return False, "An internal error has occurred."
