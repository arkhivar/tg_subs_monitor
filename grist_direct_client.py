"""
Grist Direct Client for Telegram Bot

This module provides a client for directly connecting to Grist
to store and retrieve subscriber data for the Telegram bot.
"""

import os
import json
import logging
from datetime import datetime
from grist_api import GristDocAPI

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GristDirectClient:
    """
    Client for direct Grist API integration via grist-api Python library.
    """
    
    def __init__(self):
        """Initialize the Grist client with API credentials from environment variables."""
        self.api_key = os.environ.get("GRIST_API_KEY")
        self.doc_id = os.environ.get("GRIST_DOC_ID")
        self.table_name = "subscribers"
        
        # Check for required credentials
        if not self.api_key or not self.doc_id:
            logger.error("Missing GRIST_API_KEY or GRIST_DOC_ID environment variables")
            self.api = None
        else:
            try:
                # Initialize the API client
                self.api = GristDocAPI(self.doc_id, api_key=self.api_key)
                logger.info(f"Initialized Grist client for document: {self.doc_id}")
            except Exception as e:
                logger.error(f"Error initializing Grist client: {e}")
                self.api = None
    
    def init_table(self):
        """
        Check if the subscribers table exists and create it if it doesn't.
        
        Returns:
            bool: Success status
        """
        try:
            logger.info("Initializing Grist table")
            
            # Don't create tables programmatically with Grist
            # The table must be created manually in the Grist UI first
            try:
                # Try to fetch table structure
                tables = self.api.list_tables()
                
                if self.table_name in tables:
                    logger.info(f"Table '{self.table_name}' exists in Grist document")
                    return True
                else:
                    logger.info(f"Table '{self.table_name}' doesn't exist. Please create it in the Grist UI.")
                    logger.info(f"Required columns: user_id (Text), username (Text), first_name (Text), " +
                              f"last_name (Text), join_date (Date), leave_date (Date), rejoin_date (Date), " +
                              f"current_status (Text), reaction_counter (Numeric), last_reacted (Date), is_admin (Toggle)")
                    return False
            except Exception as e:
                logger.error(f"Error checking table existence: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error in init_table: {e}")
            return False
    
    def get_subscriber(self, user_id):
        """
        Get a subscriber record by user_id.
        
        Args:
            user_id: The Telegram user ID
            
        Returns:
            dict: Subscriber data or None if not found
        """
        try:
            # Convert user_id to string for consistency
            user_id = str(user_id)
            logger.info(f"Getting subscriber with user_id: {user_id}")
            
            try:
                # Fetch all records and filter on the client side
                # This is a workaround for Grist API limitations
                records = self.api.fetch_table(self.table_name)
                
                # Find the record with matching user_id
                for record in records:
                    if record.get('user_id') == user_id:
                        logger.info(f"Found subscriber: {record}")
                        return record
                
                logger.info(f"No subscriber found with user_id: {user_id}")
                return None
            except Exception as e:
                logger.error(f"Error fetching from Grist: {e}")
                return None
            
        except Exception as e:
            logger.error(f"Error getting subscriber: {e}")
            return None
    
    def add_subscriber(self, user_data):
        """
        Add a new subscriber to the Grist table.
        
        Args:
            user_data: Dict containing user information
            
        Returns:
            bool: Success status
        """
        try:
            # Format the data for insertion
            current_time = datetime.now().isoformat()
            
            # Check if user_data already has user_id or if we need to use 'id'
            if 'user_id' in user_data:
                user_id = user_data.get('user_id')
            else:
                user_id = user_data.get('id')
            
            # Make sure user_id is a string
            user_id = str(user_id) if user_id is not None else None
            
            logger.info(f"Adding subscriber with user_id: {user_id}")
            
            # Check if the subscriber already exists
            existing = self.get_subscriber(user_id)
            if existing:
                logger.info(f"Subscriber already exists: {user_id}")
                
                # If they were inactive, update to active (rejoin)
                if existing.get('current_status') == 'inactive':
                    return self.update_subscriber_rejoin(user_id, existing.get('id'))
                
                return True
            
            # Create new record
            new_record = {
                'user_id': user_id,
                'username': user_data.get('username', ''),
                'first_name': user_data.get('first_name', ''),
                'last_name': user_data.get('last_name', ''),
                'join_date': user_data.get('join_date', current_time),
                'current_status': user_data.get('current_status', 'active'),
                'reaction_counter': user_data.get('reaction_counter', 0),
                'is_admin': user_data.get('is_admin', False)
            }
            
            # Add the record
            try:
                result = self.api.add_records(self.table_name, [new_record])
                logger.info(f"Successfully added subscriber: {result}")
                return True
            except Exception as e:
                logger.error(f"Error adding to Grist: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error adding subscriber: {e}")
            return False
    
    def update_subscriber_leave(self, user_id, record_id=None):
        """
        Update a subscriber record when they leave.
        
        Args:
            user_id: The Telegram user ID
            record_id: Optional record ID
            
        Returns:
            bool: Success status
        """
        try:
            # Convert user_id to string for consistency
            user_id = str(user_id)
            
            # Get the subscriber record
            subscriber = self.get_subscriber(user_id)
            if not subscriber:
                logger.error(f"No subscriber found with user_id: {user_id}")
                return False
            
            # Get the record ID
            grist_id = subscriber.get('id')
            if not grist_id:
                logger.error(f"No ID found for subscriber with user_id: {user_id}")
                return False
            
            current_time = datetime.now().isoformat()
            
            # Update the record
            try:
                subscriber_updates = {
                    'id': grist_id,
                    'leave_date': current_time,
                    'current_status': 'inactive'
                }
                
                # Update the record in Grist
                self.api.update_records(self.table_name, [subscriber_updates])
                logger.info(f"Successfully updated leave status for subscriber: {user_id}")
                return True
            except Exception as e:
                logger.error(f"Error updating record in Grist: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error updating leave status: {e}")
            return False
    
    def update_subscriber_rejoin(self, user_id, record_id=None):
        """
        Update a subscriber record when they rejoin.
        
        Args:
            user_id: The Telegram user ID
            record_id: Optional record ID
            
        Returns:
            bool: Success status
        """
        try:
            # Convert user_id to string for consistency
            user_id = str(user_id)
            
            # Get the subscriber record
            subscriber = self.get_subscriber(user_id)
            if not subscriber:
                logger.error(f"No subscriber found with user_id: {user_id}")
                return False
            
            # Get the record ID
            grist_id = subscriber.get('id')
            if not grist_id:
                logger.error(f"No ID found for subscriber with user_id: {user_id}")
                return False
            
            current_time = datetime.now().isoformat()
            
            # Update the record
            try:
                subscriber_updates = {
                    'id': grist_id,
                    'rejoin_date': current_time,
                    'current_status': 'active'
                }
                
                # Update the record in Grist
                self.api.update_records(self.table_name, [subscriber_updates])
                logger.info(f"Successfully updated rejoin status for subscriber: {user_id}")
                return True
            except Exception as e:
                logger.error(f"Error updating record in Grist: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error updating rejoin status: {e}")
            return False
    
    def update_reaction_count(self, user_id):
        """
        Update the reaction counter and last_reacted timestamp for a subscriber.
        
        Args:
            user_id: The Telegram user ID
            
        Returns:
            bool: Success status
        """
        try:
            # Convert user_id to string for consistency
            user_id = str(user_id)
            
            # Get the subscriber record
            subscriber = self.get_subscriber(user_id)
            if not subscriber:
                logger.error(f"No subscriber found with user_id: {user_id}")
                return False
            
            # Get the record ID and current count
            grist_id = subscriber.get('id')
            if not grist_id:
                logger.error(f"No ID found for subscriber with user_id: {user_id}")
                return False
            
            current_count = int(subscriber.get('reaction_counter', 0))
            current_time = datetime.now().isoformat()
            
            # Update the record
            try:
                subscriber_updates = {
                    'id': grist_id,
                    'reaction_counter': current_count + 1,
                    'last_reacted': current_time
                }
                
                # Update the record in Grist
                self.api.update_records(self.table_name, [subscriber_updates])
                logger.info(f"Successfully updated reaction count for subscriber: {user_id}")
                return True
            except Exception as e:
                logger.error(f"Error updating record in Grist: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error updating reaction count: {e}")
            return False
    
    def get_all_subscribers(self, status=None, limit=None):
        """
        Get all subscribers, optionally filtered by status.
        
        Args:
            status: Optional status filter ('active' or 'inactive')
            limit: Optional limit on the number of records to return
            
        Returns:
            list: List of subscriber records
        """
        try:
            logger.info(f"Getting all subscribers with status filter: {status}")
            
            try:
                # Fetch all records
                records = self.api.fetch_table(self.table_name)
                
                # Filter by status if needed
                if status:
                    records = [r for r in records if r.get('current_status') == status]
                
                # Apply limit if provided
                if limit and isinstance(limit, int):
                    records = records[:limit]
                
                logger.info(f"Found {len(records)} subscribers")
                return records
            except Exception as e:
                logger.error(f"Error fetching from Grist: {e}")
                return []
            
        except Exception as e:
            logger.error(f"Error getting all subscribers: {e}")
            return []

# For testing
if __name__ == "__main__":
    client = GristDirectClient()
    init_result = client.init_table()
    print(f"Table initialization result: {init_result}")
    
    # Test getting all subscribers
    subscribers = client.get_all_subscribers()
    print(f"Retrieved {len(subscribers)} subscribers")