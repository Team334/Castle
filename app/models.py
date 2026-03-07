from datetime import datetime, timezone
from typing import Dict, List, Optional

from bson import ObjectId
from flask_login import UserMixin
from werkzeug.security import check_password_hash


class User(UserMixin):
    def __init__(self, data):
        self._id: ObjectId = data.get('_id')
        self.username: str = data.get('username')
        self.email: str = data.get("email")
        self.teamNumber: int = data.get("teamNumber")
        self.password_hash: str = data.get("password_hash")
        self.last_login: str = data.get("last_login")
        self.created_at: str = data.get("created_at")
        self.description: str = data.get("description", "")
        self.profile_picture_id: str = data.get("profile_picture_id")

    @property
    def id(self):
        return str(self._id)

    def get_id(self) -> str:
        return str(self._id)

    def is_authenticated(self) -> bool:
        return True

    def is_active(self) -> bool:
        return True

    def is_anonymous(self) -> bool:
        return False

    def check_password(self, password: str) -> bool:
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

    def to_dict(self) -> Dict:
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

    def update_team_number(self, team_number: int) -> "User":
        """Update the user's team number"""
        self.teamNumber = team_number
        return self


class TeamData:
    def __init__(self, data):
        self.id: str = str(data.get('_id'))
        self.team_number: int = data.get('team_number')
        self.match_number: int = data.get('match_number')
        self.event_code: str = data.get('event_code')
        self.alliance: str = data.get('alliance', '')
        
        # 2026 Game Scoring - Fuel
        self.auto_fuel: int = data.get('auto_fuel', 0)
        self.transition_fuel: int = data.get('transition_fuel', 0)
        self.teleop_shift_1_fuel: int = data.get('teleop_shift_1_fuel', 0)
        self.teleop_shift_2_fuel: int = data.get('teleop_shift_2_fuel', 0)
        self.teleop_shift_3_fuel: int = data.get('teleop_shift_3_fuel', 0)
        self.teleop_shift_4_fuel: int = data.get('teleop_shift_4_fuel', 0)
        self.endgame_fuel: int = data.get('endgame_fuel', 0)
        self.ferried_fuel: int = data.get('ferried_fuel', 0)

        # Climb
        self.auto_climb: bool = data.get('auto_climb', False)
        self.climb_level: int = data.get('climb_level', 0)  # 0=None, 1-3
        self.climb_success: bool = data.get('climb_success', False)
        
        # Defense
        self.defense_rating: int = data.get('defense_rating', 1)  # 1-5 scale
        self.defense_notes: str = data.get('defense_notes', '')
        
        # Auto
        self.auto_path: str = data.get('auto_path', '')  # Store coordinates of drawn path
        self.auto_notes: str = data.get('auto_notes', '')
        
        # Notes
        self.notes: str = data.get('notes', '')
        
        # Scouter information
        self.scouter_id: ObjectId = data.get('scouter_id')
        self.scouter_name: str = data.get('scouter_name')
        self.scouter_team: str = data.get('scouter_team')
        self.is_owner: bool = data.get('is_owner', True)

        # Robot Disabled Status
        self.robot_disabled: str = data.get('robot_disabled', 'None')  # 'None', 'Partially', 'Full'
        

    @classmethod
    def create_from_db(cls, data) -> "TeamData":
        return cls(data)

    @property
    def formatted_date(self) -> str:
        """Returns formatted creation date"""
        if self.created_at:
            return self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        return "N/A"
    
    

class PitScouting:
    def __init__(self, data: Dict) -> None:
        self._id = data.get("_id")
        self.team_number = data.get("team_number")
        self.scouter_id = data.get("scouter_id")
        
        # Drive base information
        self.drive_type: Dict[str, bool or str] = data.get("drive_type", {
            "swerve": False,
            "tank": False,
            "other": ""
        })
        self.swerve_modules: str = data.get("swerve_modules", "")
        
        # Motor details
        self.motor_details: Dict[str, bool or str] = data.get("motor_details", {
            "falcons": False,
            "neos": False,
            "krakens": False,
            "vortex": False,
            "other": ""
        })
        self.motor_count: int = data.get("motor_count", 0)
        
        # Dimensions (in)
        self.dimensions: Dict[str, int] = data.get("dimensions", {
            "length": 0,
            "width": 0,
            "height": 0,
        })
        
        # Programming and Autonomous
        self.programming_language: str = data.get("programming_language", "")
        self.autonomous_capabilities: Dict = data.get("autonomous_capabilities", {
            "has_auto": False,
            "num_routes": 0,
            "preferred_start": "",
            "notes": ""
        })
        
        # Driver Experience
        self.driver_experience: Dict = data.get("driver_experience", {
            "years": 0,
            "notes": ""
        })

        # Analysis
        self.notes: str = data.get("notes", "")
        
        # Metadata
        self.created_at: Optional[datetime] = data.get("created_at")
        self.updated_at: Optional[datetime] = data.get("updated_at")

    @staticmethod
    def create_from_db(data: Dict):
        """Create a PitScouting instance from database data"""
        if not data:
            return None
        if "_id" in data and not isinstance(data["_id"], ObjectId):
            data["_id"] = ObjectId(data["_id"])
        return PitScouting(data)

class Team:
    def __init__(self, data: Dict) -> None:
        self._id: Optional[ObjectId] = data.get("_id")
        self.team_number: Optional[int] = data.get("team_number")
        self.team_join_code: Optional[str] = data.get("team_join_code")
        self.users: List[str] = data.get("users", [])  # List of User IDs
        self.admins: List[str] = data.get("admins", [])  # List of admin User IDs
        self.owner_id: Optional[str] = data.get("owner_id")  # Single owner ID
        self.created_at: Optional[datetime] = data.get("created_at")
        self.team_name: Optional[str] = data.get("team_name")
        self.description: str = data.get("description", "")
        self.logo_id: Optional[ObjectId] = data.get("logo_id")  # This should be kept as ObjectId

    def is_admin(self, user_id: str) -> bool:
        """Check if a user is an admin or owner of the team"""
        return user_id in self.admins or self.is_owner(user_id)

    def is_owner(self, user_id: str) -> bool:
        """Check if a user is the owner of the team"""
        return str(self.owner_id) == user_id

    @property
    def id(self) -> Optional[str]:
        return str(self._id) if self._id else None

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

    def add_user(self, user: UserMixin) -> None:
        # Assuming user is an instance of User (or any UserMixin subclass)
        if isinstance(user, UserMixin):
            self.users.append(user.get_id())  # Store the User ID
        else:
            raise ValueError("Expected a UserMixin instance")

    def remove_user(self, user: UserMixin) -> None:
        if isinstance(user, UserMixin):
            self.users = [uid for uid in self.users if uid != user.get_id()]
        else:
            raise ValueError("Expected a UserMixin instance")

class Assignment:
    def __init__(self, id: str, title: str, description: str, team_number: int, 
                 creator_id: str, assigned_to: List[str], due_date: Optional[datetime] = None, 
                 status: str = 'pending', created_at: Optional[datetime] = None
    ) -> None:
        self.id: str = str(id)
        self.title: str = title
        self.description: str = description
        self.team_number: int = team_number
        self.creator_id: str = creator_id
        self.assigned_to: List[str] = assigned_to
        self.status: str = status
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


class AssignmentSubscription:
    def __init__(self, data: Dict) -> None:
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

    def mark_as_sent(self) -> None:
        """Mark the notification as sent"""
        self.sent = True
        self.sent_at = datetime.now()
        self.status = "sent"
        self.updated_at = datetime.now()
