from datetime import datetime, timezone
from typing import Dict

from bson import ObjectId
from flask_login import UserMixin
from werkzeug.security import check_password_hash


class User(UserMixin):
    def __init__(self, data):
        self._id = data.get('_id')
        self.username = data.get('username')
        self.email = data.get("email")
        self.teamNumber = data.get("teamNumber")
        self.password_hash = data.get("password_hash")
        self.last_login = data.get("last_login")
        self.created_at = data.get("created_at")
        self.description = data.get("description", "")
        self.profile_picture_id = data.get("profile_picture_id")

    @property
    def id(self):
        return str(self._id)

    def get_id(self):
        return str(self._id)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def create_from_db(user_data):
        """Creates a User instance from database data"""
        if not user_data:
            return None
        # Ensure _id is ObjectId
        if "_id" in user_data and not isinstance(user_data["_id"], ObjectId):
            user_data["_id"] = ObjectId(user_data["_id"])
        return User(user_data)

    def to_dict(self):
        return {
            "_id": self._id,
            "email": self.email,
            "username": self.username,
            "teamNumber": self.teamNumber,
            "password_hash": self.password_hash,
            "last_login": self.last_login,
            "created_at": self.created_at,
            "description": self.description,
            "profile_picture_id": str(self.profile_picture_id) if self.profile_picture_id else None,
        }

    def update_team_number(self, team_number):
        """Update the user's team number"""
        self.teamNumber = team_number
        return self


class TeamData:
    def __init__(self, data):
        self.id = str(data.get('_id'))
        self.team_number = data.get('team_number')
        self.match_number = data.get('match_number')
        self.event_code = data.get('event_code')
        self.alliance = data.get('alliance', '')
        
        # 2026 Game Scoring - Fuel
        self.auto_fuel = data.get('auto_fuel', 0)
        self.transition_fuel = data.get('transition_fuel', 0)
        self.teleop_shift_1_fuel = data.get('teleop_shift_1_fuel', 0)
        self.teleop_shift_2_fuel = data.get('teleop_shift_2_fuel', 0)
        self.teleop_shift_3_fuel = data.get('teleop_shift_3_fuel', 0)
        self.teleop_shift_4_fuel = data.get('teleop_shift_4_fuel', 0)
        self.endgame_fuel = data.get('endgame_fuel', 0)

        # Climb
        self.climb_level = data.get('climb_level', 0)  # 0=None, 1-3
        self.climb_success = data.get('climb_success', False)
        
        # Defense
        self.defense_rating = data.get('defense_rating', 1)  # 1-5 scale
        self.defense_notes = data.get('defense_notes', '')
        
        # Auto
        self.auto_path = data.get('auto_path', '')  # Store coordinates of drawn path
        self.auto_notes = data.get('auto_notes', '')
        
        # Notes
        self.notes = data.get('notes', '')
        
        # Scouter information
        self.scouter_id = data.get('scouter_id')
        self.scouter_name = data.get('scouter_name')
        self.scouter_team = data.get('scouter_team')
        self.is_owner = data.get('is_owner', True)

        # Robot Disabled Status
        self.robot_disabled = data.get('robot_disabled', 'None')  # 'None', 'Partially', 'Full'
        

    @classmethod
    def create_from_db(cls, data):
        return cls(data)

    def to_dict(self):
        return {
            'id': self.id,
            'team_number': self.team_number,
            'match_number': self.match_number,
            'event_code': self.event_code,
            'alliance': self.alliance,
            
            # 2026 Game Scoring
            'auto_fuel': self.auto_fuel,
            'transition_fuel': self.transition_fuel,
            'teleop_shift_1_fuel': self.teleop_shift_1_fuel,
            'teleop_shift_2_fuel': self.teleop_shift_2_fuel,
            'teleop_shift_3_fuel': self.teleop_shift_3_fuel,
            'teleop_shift_4_fuel': self.teleop_shift_4_fuel,
            'endgame_fuel': self.endgame_fuel,
            'climb_level': self.climb_level,
            
            'climb_success': self.climb_success,
            'defense_rating': self.defense_rating,
            'defense_notes': self.defense_notes,
            'auto_path': self.auto_path,
            'auto_notes': self.auto_notes,
            'robot_disabled': self.robot_disabled,
            'notes': self.notes,
            'scouter_id': self.scouter_id,
            'scouter_name': self.scouter_name,
            'scouter_team': self.scouter_team,
            'is_owner': self.is_owner,
        }

    @property
    def formatted_date(self):
        """Returns formatted creation date"""
        if self.created_at:
            return self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        return "N/A"
    
    

class PitScouting:
    def __init__(self, data: Dict):
        self._id = data.get("_id")
        self.team_number = data.get("team_number")
        self.scouter_id = data.get("scouter_id")
        
        # Drive base information
        self.drive_type = data.get("drive_type", {
            "swerve": False,
            "tank": False,
            "other": ""
        })
        self.swerve_modules = data.get("swerve_modules", "")
        
        # Motor details
        self.motor_details = data.get("motor_details", {
            "falcons": False,
            "neos": False,
            "krakens": False,
            "vortex": False,
            "other": ""
        })
        self.motor_count = data.get("motor_count", 0)
        
        # Dimensions (in)
        self.dimensions = data.get("dimensions", {
            "length": 0,
            "width": 0,
            "height": 0,
        })
        
        # Programming and Autonomous
        self.programming_language = data.get("programming_language", "")
        self.autonomous_capabilities = data.get("autonomous_capabilities", {
            "has_auto": False,
            "num_routes": 0,
            "preferred_start": "",
            "notes": ""
        })
        
        # Driver Experience
        self.driver_experience = data.get("driver_experience", {
            "years": 0,
            "notes": ""
        })

        # Analysis
        self.notes = data.get("notes", "")
        
        # Metadata
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")

    @staticmethod
    def create_from_db(data: Dict):
        """Create a PitScouting instance from database data"""
        if not data:
            return None
        if "_id" in data and not isinstance(data["_id"], ObjectId):
            data["_id"] = ObjectId(data["_id"])
        return PitScouting(data)

    def to_dict(self):
        """Convert the object to a dictionary for database storage"""
        return {
            "id": self.id,
            "team_number": self.team_number,
            "scouter_id": self.scouter_id,
            "scouter_name": self.scouter_name,
            "drive_type": self.drive_type,
            "swerve_modules": self.swerve_modules,
            "drive_motors": self.drive_motors,
            "motor_details": self.motor_details,
            "dimensions": self.dimensions,
            "mechanisms": self.mechanisms,
            "programming_language": self.programming_language,
            "autonomous_capabilities": self.autonomous_capabilities,
            "driver_experience": self.driver_experience,
            "pictures": self.pictures,
            "notes": self.notes,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class Team:
    def __init__(self, data: Dict):
        self._id = data.get("_id")
        self.team_number = data.get("team_number")
        self.team_join_code = data.get("team_join_code")
        self.users = data.get("users", [])  # List of User IDs
        self.admins = data.get("admins", [])  # List of admin User IDs
        self.owner_id = data.get("owner_id")  # Single owner ID
        self.created_at = data.get("created_at")
        self.team_name = data.get("team_name")
        self.description = data.get("description", "")
        self.logo_id = data.get("logo_id")  # This should be kept as ObjectId

    def to_dict(self):
        return {
            "id": self.id,
            "team_number": self.team_number,
            "team_join_code": self.team_join_code,
            "users": self.users,
            "admins": self.admins,
            "owner_id": str(self.owner_id) if self.owner_id else None,
            "created_at": self.created_at,
            "team_name": self.team_name,
            "description": self.description,
            "logo_id": str(self.logo_id) if self.logo_id else None,
        }

    def is_admin(self, user_id: str) -> bool:
        """Check if a user is an admin or owner of the team"""
        return user_id in self.admins or self.is_owner(user_id)

    def is_owner(self, user_id: str) -> bool:
        """Check if a user is the owner of the team"""
        return str(self.owner_id) == user_id

    @property
    def id(self):
        return str(self._id)

    @staticmethod
    def create_from_db(data: Dict):
        if not data:
            return None
        # Convert string ID to ObjectId if necessary
        if "_id" in data and not isinstance(data["_id"], ObjectId):
            data["_id"] = ObjectId(data["_id"])
        if "logo_id" in data and not isinstance(data["logo_id"], ObjectId) and data["logo_id"]:
            data["logo_id"] = ObjectId(data["logo_id"])
        return Team(data)

    def add_user(self, user: UserMixin):
        # Assuming user is an instance of User (or any UserMixin subclass)
        if isinstance(user, UserMixin):
            self.users.append(user.get_id())  # Store the User ID
        else:
            raise ValueError("Expected a UserMixin instance")

    def remove_user(self, user: UserMixin):
        if isinstance(user, UserMixin):
            self.users = [uid for uid in self.users if uid != user.get_id()]
        else:
            raise ValueError("Expected a UserMixin instance")

class Assignment:
    def __init__(self, id, title, description, team_number, creator_id, assigned_to, due_date=None, status='pending', created_at=None):
        self.id = str(id)
        self.title = title
        self.description = description
        self.team_number = team_number
        self.creator_id = creator_id
        self.assigned_to = assigned_to
        self.status = status
        # Convert string to datetime if needed
        if isinstance(due_date, str):
            try:
                self.due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                self.due_date = None
        else:
            self.due_date = due_date
            
        # Handle created_at
        if isinstance(created_at, str):
            try:
                self.created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                self.created_at = datetime.now(timezone.utc)
        else:
            self.created_at = created_at or datetime.now(timezone.utc)

    @classmethod
    def create_from_db(cls, data):
        return cls(
            id=data['_id'],
            title=data.get('title'),
            description=data.get('description'),
            team_number=data.get('team_number'),
            creator_id=data.get('creator_id'),
            assigned_to=data.get('assigned_to', []),
            due_date=data.get('due_date'),
            status=data.get('status', 'pending'),
            created_at=data.get('created_at')
        )

    def to_dict(self):
        return {
            "id": self.id,
            "team_number": self.team_number,
            "title": self.title,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "due_date": self.due_date,
            "created_by": str(self.created_by) if self.created_by else None,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

class AssignmentSubscription:
    def __init__(self, data: Dict):
        self._id = data.get("_id")
        self.user_id = data.get("user_id")
        self.team_number = data.get("team_number")
        
        # Push notification details
        self.subscription_json = data.get("subscription_json", {})  # The Web Push subscription object
        
        # Assignment specific details
        self.assignment_id = data.get("assignment_id")  # Optional - None means it's a general subscription
        self.reminder_time = data.get("reminder_time", 1440)  # Minutes before due date (default: 1 day)
        
        # Scheduled notification details
        self.scheduled_time = data.get("scheduled_time")  # When to send the notification
        self.sent = data.get("sent", False)
        self.sent_at = data.get("sent_at")
        self.status = data.get("status", "pending")  # pending, sent, error
        self.error = data.get("error")
        
        # Notification content
        self.title = data.get("title", "Assignment Reminder")
        self.body = data.get("body", "You have an upcoming assignment")
        self.url = data.get("url", "/")
        self.data = data.get("data", {})
        
        # Metadata
        self.created_at = data.get("created_at", datetime.now())
        self.updated_at = data.get("updated_at", datetime.now())

    @property
    def id(self):
        return str(self._id)

    @staticmethod
    def create_from_db(data: Dict):
        """Create an AssignmentSubscription instance from database data"""
        if not data:
            return None
        if "_id" in data and not isinstance(data["_id"], ObjectId):
            data["_id"] = ObjectId(data["_id"])
        return AssignmentSubscription(data)

    def to_dict(self):
        """Convert the object to a dictionary for database storage"""
        return {
            "user_id": self.user_id,
            "team_number": self.team_number,
            "subscription_json": self.subscription_json,
            "assignment_id": self.assignment_id,
            "reminder_time": self.reminder_time,
            "scheduled_time": self.scheduled_time,
            "sent": self.sent,
            "sent_at": self.sent_at,
            "status": self.status,
            "error": self.error,
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "data": self.data,
            "created_at": self.created_at,
            "updated_at": datetime.now()
        }
    
    def mark_as_sent(self):
        """Mark the notification as sent"""
        self.sent = True
        self.sent_at = datetime.now()
        self.status = "sent"
        self.updated_at = datetime.now()
