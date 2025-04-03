import logging
import threading
from datetime import datetime, timedelta
import json
from bson import ObjectId
from typing import Dict, Optional, Tuple

from app.models import AssignmentSubscription
from app.utils import DatabaseManager, with_mongodb_retry, get_database_connection
from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)

class NotificationManager(DatabaseManager):
    """Manages push notifications and subscriptions"""
    
    def __init__(self, mongo_uri: str, vapid_private_key: str, vapid_claims: Dict[str, str]):
        """Initialize NotificationManager with MongoDB connection and VAPID keys
        
        Args:
            mongo_uri: MongoDB connection URI
            vapid_private_key: VAPID private key for WebPush
            vapid_claims: Dictionary containing email and subject for VAPID
        """
        # Use the singleton connection
        super().__init__(mongo_uri)
        
        self.vapid_private_key = vapid_private_key
        self.vapid_claims = vapid_claims
        self._shutdown_event = threading.Event()
        self._notification_thread = None
        self._ensure_collections()
        
    def _ensure_collections(self) -> None:
        """Ensure required collections exist"""
        if "assignment_subscriptions" not in self.db.list_collection_names():
            self.db.create_collection("assignment_subscriptions")
            logger.info("Created assignment_subscriptions collection")
            
    def start_notification_service(self):
        """Start the background thread that processes notifications"""
        if self._notification_thread is None or not self._notification_thread.is_alive():
            self._shutdown_event.clear()
            self._notification_thread = threading.Thread(
                target=self._notification_worker,
                daemon=True
            )
            self._notification_thread.start()
            logger.info("Notification service started")
    
    def stop_notification_service(self):
        """Stop the notification background thread"""
        if self._notification_thread and self._notification_thread.is_alive():
            self._shutdown_event.set()
            self._notification_thread.join(timeout=5)
            logger.info("Notification service stopped")
    
    def _notification_worker(self):
        """Background worker that checks for pending notifications"""
        logger.info("Notification worker started")
        
        while not self._shutdown_event.is_set():
            try:
                # Check for notifications that need to be sent
                self._process_pending_notifications()
                
                # Schedule notifications for upcoming assignments
                self._schedule_assignment_notifications()
                
                # Sleep for a 15s before checking again
                self._shutdown_event.wait(15)
            except Exception as e:
                logger.error(f"Error in notification worker: {str(e)}")
                # Sleep for 5 seconds before retrying after an error
                self._shutdown_event.wait(5)
    
    @with_mongodb_retry()
    def _process_pending_notifications(self):
        """Process all pending notifications that are due to be sent"""
        

        # Find notifications scheduled for now or earlier that haven't been sent
        now = datetime.now()
        pending_notifications = self.db.assignment_subscriptions.find({
            "scheduled_time": {"$lte": now},
            "sent": False,
            "status": "pending"
        })

        count = 0
        for notification in pending_notifications:
            subscription_obj = AssignmentSubscription.create_from_db(notification)

            try:
                if success := self._send_push_notification(subscription_obj):
                    subscription_obj.mark_as_sent()
                    self.db.assignment_subscriptions.update_one(
                        {"_id": subscription_obj._id},
                        {"$set": {
                            "sent": True,
                            "sent_at": datetime.now(),
                            "status": "sent",
                            "updated_at": datetime.now()
                        }}
                    )
                    count += 1
                else:
                    # Mark as error if sending failed
                    self.db.assignment_subscriptions.update_one(
                        {"_id": subscription_obj._id},
                        {"$set": {
                            "status": "error",
                            "error": "Failed to send push notification",
                            "updated_at": datetime.now()
                        }}
                    )
            except Exception as e:
                logger.error(f"Error processing notification {subscription_obj.id}: {str(e)}")
                self.db.assignment_subscriptions.update_one(
                    {"_id": subscription_obj._id},
                    {"$set": {
                        "status": "error",
                        "error": str(e),
                        "updated_at": datetime.now()
                    }}
                )

        if count > 0:
            logger.info(f"Sent {count} notifications")
    
    @with_mongodb_retry()
    def _schedule_assignment_notifications(self):
        """Schedule notifications for assignments with due dates"""
        
        
        # Get assignments with due dates
        assignments = self.db.assignments.find({
            "due_date": {"$exists": True, "$ne": None}
        })
        
        for assignment in assignments:
            # Get the subscriptions for this assignment
            self._schedule_assignment_reminder(assignment)
    
    def _schedule_assignment_reminder(self, assignment: Dict):
        """Schedule reminders for a specific assignment
        
        Args:
            assignment: The assignment document from MongoDB
        """
        assignment_id = str(assignment["_id"])
        due_date = assignment.get("due_date")
        team_number = assignment.get("team_number")

        if not due_date:
            return

        # Ensure due_date is a datetime object
        if isinstance(due_date, str):
            try:
                due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                logger.error(f"Invalid due date format for assignment {assignment_id}")
                return

        # Find existing subscriptions for this assignment
        existing = self.db.assignment_subscriptions.find({
            "assignment_id": assignment_id,
            "sent": False
        })
        existing_user_ids = [sub.get("user_id") for sub in existing]

        # Get all subscriptions for the team that don't have specific assignment subscriptions
        team_subscriptions = self.db.assignment_subscriptions.find({
            "team_number": team_number,
            "assignment_id": None,
            "user_id": {"$nin": existing_user_ids},
            "subscription_json": {"$exists": True, "$ne": {}}
        })

        # For each team subscription, create an assignment-specific subscription
        for sub in team_subscriptions:
            user_id = sub.get("user_id")

            # Check if user is assigned to this task
            if user_id not in assignment.get("assigned_to", []):
                continue

            # Calculate scheduled time based on reminder_time
            reminder_time = sub.get("reminder_time", 1440)  # Default: 1 day in minutes
            scheduled_time = due_date - timedelta(minutes=reminder_time)

            # Only schedule if it's in the future
            if scheduled_time <= datetime.now():
                continue

            # Create the notification
            new_notification = {
                "user_id": user_id,
                "team_number": team_number,
                "subscription_json": sub.get("subscription_json", {}),
                "assignment_id": assignment_id,
                "reminder_time": reminder_time,
                "scheduled_time": scheduled_time,
                "sent": False,
                "status": "pending",
                "title": f"Assignment Reminder: {assignment.get('title')}",
                "body": f"Your assignment '{assignment.get('title')}' is due soon",
                "url": "/team/manage",
                "data": {
                    "assignment_id": assignment_id,
                    "title": assignment.get("title"),
                    "due_date": due_date.isoformat(),
                    "type": "assignment_reminder",
                },
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            # Insert the new notification
            self.db.assignment_subscriptions.insert_one(new_notification)
    
    def _send_push_notification(self, subscription: AssignmentSubscription) -> bool:
        """Send a push notification using WebPush
        
        Args:
            subscription: The AssignmentSubscription object
            
        Returns:
            bool: True if the notification was sent successfully
        """
        try:
            subscription_info = subscription.subscription_json
            if not subscription_info:
                logger.warning(f"Empty subscription info for {subscription.id}")
                return False
                
            data = {
                "title": subscription.title,
                "body": subscription.body,
                "url": subscription.url,
                "data": {
                    "assignment_id": subscription.assignment_id,
                    "url": subscription.url,
                    **subscription.data  # Include any additional data
                },
                "icon": "/static/images/logo.png",
                "badge": "/static/images/logo.png",
                "image": "/static/images/logo.png",
                "actions": [
                    {
                        "action": "view",
                        "title": "View"
                    },
                    {
                        "action": "dismiss",
                        "title": "Dismiss"
                    }
                ],
                "timestamp": datetime.now().timestamp() * 1000  # JavaScript timestamp
            }
            
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(data),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )
            
            return True
        except WebPushException as e:
            logger.error(f"WebPush error for {subscription.id}: {str(e)}")
            
            # Handle subscription that has been closed
            if e.response and e.response.status_code in (404, 410):
                # Remove the subscription since it's no longer valid
                self.db.assignment_subscriptions.delete_one({"_id": subscription._id})
                logger.info(f"Removed invalid subscription {subscription.id}")
                
            return False
        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
            return False
    
    @with_mongodb_retry()
    async def create_subscription(self, user_id: str, team_number: int, 
                                subscription_json: Dict, 
                                assignment_id: Optional[str] = None,
                                reminder_time: int = 1440) -> Tuple[bool, str]:
        """Create or update a push notification subscription
        
        Args:
            user_id: The user ID
            team_number: The team number
            subscription_json: The subscription object from the browser
            assignment_id: Optional specific assignment ID to subscribe to
            reminder_time: Minutes before due date to send reminder (default: 1 day)
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        

        try:
            # Check if user is in the team
            team = self.db.teams.find_one({"team_number": team_number, "users": user_id})
            if not team:
                return False, "User is not a member of this team"

            # If this is for a specific assignment, check if it exists and user is assigned
            if assignment_id:
                assignment = self.db.assignments.find_one({
                    "_id": ObjectId(assignment_id),
                    "team_number": team_number
                })

                if not assignment:
                    return False, "Assignment not found"

                if user_id not in assignment.get("assigned_to", []):
                    return False, "User is not assigned to this assignment"

            # Check for existing subscription and update or create
            query = {
                "user_id": user_id,
                "team_number": team_number,
                "assignment_id": assignment_id or None,
            }

            # Calculate scheduled time if this is for a specific assignment
            scheduled_time = None
            if assignment_id and assignment.get("due_date"):
                due_date = assignment.get("due_date")

                # Ensure due_date is a datetime object
                if isinstance(due_date, str):
                    try:
                        due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        return False, "Invalid due date format"

                scheduled_time = due_date - timedelta(minutes=reminder_time)

                # Only schedule if it's in the future
                if scheduled_time <= datetime.now():
                    scheduled_time = None

            update_data = {
                "subscription_json": subscription_json,
                "reminder_time": reminder_time,
                "updated_at": datetime.now()
            }

            if scheduled_time:
                update_data["scheduled_time"] = scheduled_time
                update_data["sent"] = False
                update_data["status"] = "pending"

                # Set notification content
                update_data["title"] = f"Assignment Reminder: {assignment.get('title')}"
                update_data["body"] = f"Your assignment '{assignment.get('title')}' is due soon"
                update_data["url"] = "/team/manage"
                update_data["data"] = {
                    "assignment_id": assignment_id,
                    "title": assignment.get("title"),
                    "due_date": due_date.isoformat(),
                    "type": "assignment_reminder"
                }

            # Use upsert to either update existing or create new
            result = self.db.assignment_subscriptions.update_one(
                query,
                {"$set": update_data},
                upsert=True
            )

            if result.matched_count > 0:
                return True, "Subscription updated successfully"
            elif result.upserted_id:
                return True, "Subscription created successfully"
            else:
                return False, "Failed to create subscription"

        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return False, "An internal error has occurred."
    
    @with_mongodb_retry()
    async def delete_subscription(self, user_id: str, team_number: int = None, 
                                 assignment_id: Optional[str] = None) -> Tuple[bool, str]:
        """Delete a push notification subscription
        
        Args:
            user_id: The user ID
            team_number: Optional team number filter
            assignment_id: Optional assignment ID filter
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        
        
        try:
            query = {"user_id": user_id}
            
            if team_number:
                query["team_number"] = team_number
                
            if assignment_id:
                query["assignment_id"] = assignment_id
            
            result = self.db.assignment_subscriptions.delete_many(query)
            
            if result.deleted_count > 0:
                return True, f"Deleted {result.deleted_count} subscriptions"
            else:
                return False, "No subscriptions found"
                
        except Exception as e:
            logger.error(f"Error deleting subscription: {str(e)}")
            return False, "An internal error has occurred."
    
    # @with_mongodb_retry()
    # async def test_notification(self, user_id: str) -> Tuple[bool, str]:
    #     """Send a test notification to a user
        
    #     Args:
    #         user_id: The user ID
            
    #     Returns:
    #         Tuple[bool, str]: Success status and message
    #     """
    #     

    #     try:
    #         # Get the user's subscriptions
    #         subscriptions = self.db.assignment_subscriptions.find({
    #             "user_id": user_id,
    #             "subscription_json": {"$exists": True, "$ne": {}}
    #         })

    #         if not subscriptions:
    #             return False, "No subscription found for this user"

    #         for sub_data in subscriptions:
    #             subscription = AssignmentSubscription.create_from_db(sub_data)

    #             # Override notification data for test
    #             subscription.title = "Test Notification"
    #             subscription.body = "This is a test notification from the Scouting App"
    #             subscription.url = "/team/manage"
    #             subscription.data = {
    #                 "test": True, 
    #                 "type": "test_notification",
    #                 "timestamp": datetime.now().isoformat()
    #             }

    #             if _ := self._send_push_notification(subscription):
    #                 return True, "Test notification sent successfully"

    #         return False, "Failed to send test notification"

    #     except Exception as e:
    #         logger.error(f"Error sending test notification: {str(e)}")
    #         return False, "An internal error has occurred." 

    async def send_instant_assignment_notification(self, assignment_data: Dict, team_number: int) -> None:
        """Send instant notifications to users when they are assigned to a new assignment
        
        Args:
            assignment_data: The assignment data including title, description, etc.
            team_number: The team number
        """
        
        
        try:
            # Get all subscriptions for assigned users
            assigned_users = assignment_data.get("assigned_to", [])
            if not assigned_users:
                return
                
            # Find all valid subscriptions for these users
            subscriptions = self.db.assignment_subscriptions.find({
                "user_id": {"$in": assigned_users},
                "team_number": team_number,
                "subscription_json": {"$exists": True, "$ne": {}},
                "updated_at": {"$gte": datetime.now() - timedelta(days=1)}  # Only get recent subscriptions
            })
            
            # Group subscriptions by user_id and keep only the most recent one
            user_subscriptions = {}
            for sub_data in subscriptions:
                user_id = sub_data.get("user_id")
                updated_at = sub_data.get("updated_at", datetime.min)
                
                # Keep only the most recently updated subscription for each user
                if user_id not in user_subscriptions or updated_at > user_subscriptions[user_id].get("updated_at", datetime.min):
                    user_subscriptions[user_id] = sub_data
            
            expired_subscriptions = []
            notification_sent = False
            
            # Send notification using only the most recent subscription for each user
            for sub_data in user_subscriptions.values():
                try:
                    # Create subscription object
                    subscription = AssignmentSubscription({
                        **sub_data,
                        "title": f"New Assignment: {assignment_data.get('title')}",
                        "body": f"Assignment: {assignment_data.get('title')}",
                        "url": "/team/manage",
                        "data": {
                            "assignment_id": str(assignment_data.get("_id")),
                            "title": assignment_data.get("title"),
                            "type": "new_assignment"
                        },
                        "sent": False,
                        "status": "pending"
                    })
                    
                    # Try to send the notification
                    try:
                        if self._send_push_notification(subscription):
                            notification_sent = True
                            logger.info(f"Successfully sent notification for assignment {assignment_data.get('title')} to user {subscription.user_id}")
                        else:
                            logger.warning(f"Failed to send notification for assignment {assignment_data.get('title')} to user {subscription.user_id}")
                    except WebPushException as e:
                        if e.response and e.response.status_code in (404, 410):
                            expired_subscriptions.append(sub_data["_id"])
                            logger.info(f"Subscription {subscription.id} has expired")
                        else:
                            logger.error(f"WebPush error for {subscription.id}: {str(e)}")
                    
                except Exception as e:
                    logger.error(f"Error processing subscription: {str(e)}")
                    continue
            
            # Clean up expired subscriptions in bulk if any found
            if expired_subscriptions:
                self.db.assignment_subscriptions.delete_many({
                    "_id": {"$in": expired_subscriptions}
                })
                logger.info(f"Cleaned up {len(expired_subscriptions)} expired subscriptions")
            
            if not notification_sent:
                logger.warning(f"No notifications were sent for assignment {assignment_data.get('title')}")
                
        except Exception as e:
            logger.error(f"Error sending instant assignment notification: {str(e)}") 