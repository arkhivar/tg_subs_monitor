"""
Grist Client for Telegram Bot

This module provides a client for interacting with Grist to store and retrieve
subscriber data for the Telegram bot.
"""

import os
import json
import logging
from datetime import datetime
import time
from grist_api import GristDocAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GristClient:
    """
    Client for interacting with Grist API to manage subscriber data.
    """
    
    def __init__(self):
        """Initialize the Grist client with API credentials from environment variables."""
        # Get API credentials from environment variables
        self.api_key = os.environ.get("GRIST_API_KEY")
        self.doc_id = os.environ.get("GRIST_DOC_ID")
        self.table_name = "channels"  # Default table name for subscribers
        
        if not self.api_key:
            logger.error("GRIST_API_KEY environment variable not set")
            raise ValueError("GRIST_API_KEY environment variable not set")
            
        if not self.doc_id:
            logger.error("GRIST_DOC_ID environment variable not set")
            raise ValueError("GRIST_DOC_ID environment variable not set")
            
        logger.info(f"Initializing Grist client with document ID: {self.doc_id}")
        
        # Initialize Grist API client
        self.api = GristDocAPI(self.doc_id, api_key=self.api_key)
    
    def init_table(self):
        """
        Check if the channels table exists and ensure it has the correct structure.
        Creates the table if it doesn't exist.
        
        Returns:
            bool: Success status
        """
        try:
            logger.info(f"Ensuring Grist table '{self.table_name}' is set up")
            
            # First check if we can access the API by trying to fetch records
            try:
                # Try to fetch a single record to verify access
                try:
                    records = self.api.fetch_table(self.table_name, limit=1)
                    logger.info(f"Successfully connected to Grist table {self.table_name}")
                    logger.info(f"Found {len(records)} records in table")
                    return True
                except Exception as e:
                    if "Table not found" in str(e):
                        # Table doesn't exist, create it
                        logger.info(f"Table '{self.table_name}' does not exist, creating it")
                        return self._create_table()
                    else:
                        logger.error(f"Error accessing table '{self.table_name}': {e}")
                        return False
            
            except Exception as e:
                logger.error(f"Error connecting to Grist API: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing Grist table: {e}")
            return False
    
    def _create_table(self):
        """
        Create the channels table with the required columns.
        
        Returns:
            bool: Success status
        """
        try:
            # The Grist API Python client doesn't have a direct method to create a table
            # Instead, we'll add a record to the table and let Grist create it for us
            
            # Prepare a sample record with all our required fields
            sample_data = {
                "user_id": "sample_user",
                "username": "sample_username",
                "first_name": "Sample",
                "last_name": "User",
                "join_date": datetime.now().isoformat(),
                "current_status": "active",
                "reaction_counter": 0
            }
            
            logger.info(f"Creating table '{self.table_name}' with sample record")
            
            # Add the sample record to create the table
            try:
                records = self.api.add_records(self.table_name, [sample_data])
                if records and len(records) > 0:
                    logger.info(f"Successfully created Grist table '{self.table_name}'")
                    
                    # Now delete the sample record
                    try:
                        self.api.delete_records(self.table_name, [records[0]['id']])
                        logger.info("Removed sample record")
                    except:
                        # It's okay if we can't delete it, the table is created
                        logger.warning("Could not delete sample record, but table was created")
                        
                    return True
                else:
                    logger.error("Failed to create table: no record ID returned")
                    return False
            except Exception as e:
                logger.error(f"Error creating table with sample record: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error creating Grist table: {e}")
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
            
            # Query the Grist table for the user
            records = self.api.fetch_table(
                self.table_name, 
                filter={"user_id": user_id}
            )
            
            if records and len(records) > 0:
                subscriber = records[0]
                logger.info(f"Found subscriber: {subscriber}")
                return subscriber
            else:
                logger.info(f"No subscriber found with user_id: {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting subscriber {user_id}: {e}")
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
            
            # Make sure user_id is a string - this is critical for Grist
            if user_id is not None:
                user_id = str(user_id)
                
            logger.info(f"Adding subscriber with user_id: {user_id}")
            
            # Create a clean data object with only the required fields
            data = {
                "user_id": user_id,
                "username": user_data.get('username', ''),
                "first_name": user_data.get('first_name', ''),
                "last_name": user_data.get('last_name', ''),
                "join_date": user_data.get('join_date', current_time),
                "current_status": user_data.get('current_status', 'active'),
                "reaction_counter": user_data.get('reaction_counter', 0)
            }
            
            # Remove any None values
            data = {k: v for k, v in data.items() if v is not None}
            
            # For Grist, ensure reaction_counter is a number
            if 'reaction_counter' in data and not isinstance(data['reaction_counter'], (int, float)):
                try:
                    data['reaction_counter'] = int(data['reaction_counter'])
                except (ValueError, TypeError):
                    data['reaction_counter'] = 0
            
            logger.info(f"Prepared subscriber data: {data}")
            
            # Add the record to Grist
            records = self.api.add_records(self.table_name, [data])
            
            if records and len(records) > 0:
                logger.info(f"Successfully added subscriber: {user_id}")
                logger.info(f"Record ID: {records[0]['id']}")
                return True
            else:
                logger.error("Failed to add subscriber: no record returned")
                return False
                
        except Exception as e:
            logger.error(f"Error adding subscriber: {e}")
            return False
    
    def update_subscriber_leave(self, user_id, record_id):
        """
        Update a subscriber record when they leave.
        
        Args:
            user_id: The Telegram user ID
            record_id: The Grist record ID
            
        Returns:
            bool: Success status
        """
        try:
            # Format the data for update
            current_time = datetime.now().isoformat()
            data = {
                "leave_date": current_time,
                "current_status": "inactive"
            }
            
            logger.info(f"Updating leave status for subscriber {user_id} (Record ID: {record_id})")
            
            # Update the record in Grist
            self.api.update_records(self.table_name, [record_id], [data])
            logger.info(f"Successfully updated leave status for subscriber: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating leave status: {e}")
            return False
    
    def update_subscriber_rejoin(self, user_id, record_id):
        """
        Update a subscriber record when they rejoin.
        
        Args:
            user_id: The Telegram user ID
            record_id: The Grist record ID
            
        Returns:
            bool: Success status
        """
        try:
            # Format the data for update
            current_time = datetime.now().isoformat()
            data = {
                "rejoin_date": current_time,
                "current_status": "active"
            }
            
            logger.info(f"Updating rejoin status for subscriber {user_id} (Record ID: {record_id})")
            
            # Update the record in Grist
            self.api.update_records(self.table_name, [record_id], [data])
            logger.info(f"Successfully updated rejoin status for subscriber: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating rejoin status: {e}")
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
            logger.info(f"Getting all subscribers with status={status}, limit={limit}")
            
            # Set up the filter if status is provided
            filter_dict = None
            if status:
                filter_dict = {"current_status": status}
            
            # Set up the limit if provided
            limit_val = None
            if limit and isinstance(limit, int):
                limit_val = limit
            
            # Query the Grist table
            records = self.api.fetch_table(
                self.table_name,
                filter=filter_dict,
                limit=limit_val
            )
            
            logger.info(f"Found {len(records)} subscribers")
            return records
            
        except Exception as e:
            logger.error(f"Error getting all subscribers: {e}")
            return []
    
    def update_reaction_count(self, user_id):
        """
        Update the reaction counter and last_reacted timestamp for a subscriber.
        
        Args:
            user_id: The Telegram user ID
            
        Returns:
            bool: Success status
        """
        try:
            # Find the subscriber record
            subscriber = self.get_subscriber(user_id)
            
            if not subscriber:
                logger.error(f"No subscriber found with user_id: {user_id}")
                return False
            
            # Get the current reaction count
            current_count = subscriber.get('reaction_counter', 0)
            
            # Make sure it's a number
            if not isinstance(current_count, (int, float)):
                try:
                    current_count = int(current_count)
                except (ValueError, TypeError):
                    current_count = 0
            
            # Increment the count
            new_count = current_count + 1
            
            # Format the data for update
            current_time = datetime.now().isoformat()
            data = {
                "reaction_counter": new_count,
                "last_reacted": current_time
            }
            
            logger.info(f"Updating reaction count for subscriber {user_id} from {current_count} to {new_count}")
            
            # Update the record in Grist
            self.api.update_records(self.table_name, [subscriber['id']], [data])
            logger.info(f"Successfully updated reaction count for subscriber: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating reaction count: {e}")
            return False