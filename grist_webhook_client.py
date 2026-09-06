"""
Grist Webhook Client for Telegram Bot

This module provides a client for interacting with Grist via webhooks
to store and retrieve subscriber data for the Telegram bot.
"""

import os
import json
import logging
import requests
from datetime import datetime
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GristWebhookClient:
    """
    Client for interacting with Grist API via webhooks to manage subscriber data.
    """
    
    def __init__(self):
        """Initialize the Grist webhook client with API credentials from environment variables."""
        self.api_key = os.environ.get("GRIST_API_KEY")
        self.doc_id = os.environ.get("GRIST_DOC_ID")
        self.base_url = "https://api.getgrist.com/api"
        self.webhook_key = None  # Will be generated on table initialization
        
        self.table_name = "subscribers"
        self.columns = [
            "user_id", "username", "first_name", "last_name", 
            "join_date", "leave_date", "rejoin_date", "current_status",
            "reaction_counter", "last_reacted", "is_admin"
        ]
        
        # Check for required credentials
        if not self.api_key or not self.doc_id:
            logger.error("Missing GRIST_API_KEY or GRIST_DOC_ID environment variables")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Initialized Grist webhook client for document: {self.doc_id}")
    
    def init_table(self):
        """
        Check if the subscribers table exists and ensure it has the correct structure.
        Creates the webhook trigger if it doesn't exist.
        
        Returns:
            bool: Success status
        """
        try:
            logger.info(f"Initializing Grist table: {self.table_name}")
            
            # Step 1: Check if table exists by trying to fetch records
            url = f"{self.base_url}/docs/{self.doc_id}/tables/{self.table_name}/data"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 404:
                logger.info(f"Table '{self.table_name}' not found. Creating it.")
                success = self._create_table()
                if not success:
                    return False
            elif response.status_code == 200:
                logger.info(f"Table '{self.table_name}' exists.")
            else:
                logger.error(f"Error checking table: {response.status_code} - {response.text}")
                return False
            
            # Step 2: Create or update webhook
            return self._setup_webhook()
            
        except Exception as e:
            logger.error(f"Error initializing Grist table: {e}")
            return False
    
    def _create_table(self):
        """
        Create the subscribers table with the required columns using the Raw Data API.
        
        Returns:
            bool: Success status
        """
        try:
            # The Add Records API will create the table if it doesn't exist
            # We'll create one sample record to establish the table
            # First, try with the raw data endpoint
            try:
                url = f"{self.base_url}/docs/{self.doc_id}/tables/{self.table_name}/records"
                columns = [
                    {"id": "user_id", "type": "Text"}, 
                    {"id": "username", "type": "Text"},
                    {"id": "first_name", "type": "Text"},
                    {"id": "last_name", "type": "Text"},
                    {"id": "join_date", "type": "Text"},
                    {"id": "leave_date", "type": "Text"},
                    {"id": "rejoin_date", "type": "Text"},
                    {"id": "current_status", "type": "Text"},
                    {"id": "reaction_counter", "type": "Int"},
                    {"id": "last_reacted", "type": "Text"},
                    {"id": "is_admin", "type": "Bool"}
                ]
                
                create_payload = {
                    "columns": columns,
                    "records": []
                }
                
                response = requests.post(
                    url, 
                    headers=self.headers,
                    json=create_payload
                )
                
                if response.status_code in (200, 201):
                    logger.info(f"Successfully created table '{self.table_name}' using schema")
                    return True
                    
                logger.warning(f"Failed to create table with schema: {response.status_code} - {response.text}")
            except Exception as e:
                logger.warning(f"Error creating table with schema: {e}")
            
            # Fall back to adding a sample record
            sample_data = {
                "user_id": "sample_user",
                "username": "sample_username",
                "first_name": "Sample",
                "last_name": "User",
                "join_date": datetime.now().isoformat(),
                "current_status": "test",
                "reaction_counter": 0
            }
            
            url = f"{self.base_url}/docs/{self.doc_id}/tables/{self.table_name}/data"
            response = requests.post(
                url, 
                headers=self.headers,
                json=[sample_data]
            )
            
            if response.status_code in (200, 201):
                logger.info(f"Successfully created table '{self.table_name}'")
                
                # Now delete the sample record
                record_id = response.json().get('records', [0])[0]
                self._delete_sample_record(record_id)
                return True
            else:
                logger.error(f"Error creating table: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating Grist table: {e}")
            return False
    
    def _delete_sample_record(self, record_id):
        """Delete the sample record used to create the table."""
        try:
            url = f"{self.base_url}/docs/{self.doc_id}/tables/{self.table_name}/data/delete"
            response = requests.post(
                url, 
                headers=self.headers,
                json={"records": [record_id]}
            )
            
            if response.status_code == 200:
                logger.info("Successfully deleted sample record")
                return True
            else:
                logger.error(f"Error deleting sample record: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error deleting sample record: {e}")
            return False
    
    def _setup_webhook(self):
        """
        Create or update a webhook for this document.
        
        Returns:
            bool: Success status
        """
        try:
            # Generate a webhook key if we don't have one
            if not self.webhook_key:
                self.webhook_key = os.urandom(16).hex()
                
            # Create the webhook
            webhook_url = os.environ.get("GRIST_WEBHOOK_URL", "")
            if not webhook_url:
                logger.warning("GRIST_WEBHOOK_URL not set, using current host")
                # Use a default URL if not specified
                webhook_url = "https://replit.com/@username/project/grist-webhook"
            
            # Add auth token to webhook URL
            if "?" not in webhook_url:
                webhook_url = f"{webhook_url}?token={self.webhook_key}"
            else:
                webhook_url = f"{webhook_url}&token={self.webhook_key}"
                
            # Webhook resource endpoints
            webhook_list_url = f"{self.base_url}/docs/{self.doc_id}/webhooks"
            
            # First, check existing webhooks
            response = requests.get(webhook_list_url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Error listing webhooks: {response.status_code} - {response.text}")
                return False
            
            webhooks = response.json().get('webhooks', [])
            existing_webhook = None
            
            # Check if we already have a webhook for our URL
            for webhook in webhooks:
                if webhook.get('url') == webhook_url:
                    existing_webhook = webhook
                    break
            
            if existing_webhook:
                logger.info(f"Webhook already exists with ID: {existing_webhook.get('id')}")
                return True
            
            # Create new webhook
            webhook_data = {
                "url": webhook_url,
                "enabled": True,
                "eventTypes": ["add", "update", "delete"],
                "tableId": self.table_name
            }
            
            response = requests.post(
                webhook_list_url,
                headers=self.headers,
                json=webhook_data
            )
            
            if response.status_code in (200, 201):
                webhook_id = response.json().get('id')
                logger.info(f"Successfully created webhook with ID: {webhook_id}")
                return True
            else:
                logger.error(f"Error creating webhook: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting up webhook: {e}")
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
            
            # Construct the filter query
            query = {"filter": {"user_id": user_id}}
            
            url = f"{self.base_url}/docs/{self.doc_id}/tables/{self.table_name}/records"
            response = requests.get(
                url, 
                headers=self.headers,
                params={"filter": json.dumps(query)}
            )
            
            if response.status_code != 200:
                logger.error(f"Error getting subscriber: {response.status_code} - {response.text}")
                return None
            
            records = response.json().get('records', [])
            if not records:
                return None
                
            # Return the first matching record
            subscriber_data = records[0]
            return {
                'id': subscriber_data.get('id'),
                'user_id': subscriber_data.get('user_id'),
                'username': subscriber_data.get('username'),
                'first_name': subscriber_data.get('first_name'),
                'last_name': subscriber_data.get('last_name'),
                'join_date': subscriber_data.get('join_date'),
                'leave_date': subscriber_data.get('leave_date'),
                'rejoin_date': subscriber_data.get('rejoin_date'),
                'current_status': subscriber_data.get('current_status'),
                'reaction_counter': subscriber_data.get('reaction_counter', 0),
                'last_reacted': subscriber_data.get('last_reacted')
            }
            
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
            # Format data correctly
            current_time = datetime.now().isoformat()
            
            # Check if user_data already has user_id or if we need to use 'id'
            if 'user_id' in user_data:
                user_id = user_data.get('user_id')
            else:
                user_id = user_data.get('id')
            
            # Make sure user_id is a string
            user_id = str(user_id) if user_id is not None else None
            
            # Check if the subscriber already exists
            existing = self.get_subscriber(user_id)
            if existing:
                logger.info(f"Subscriber already exists: {user_id}")
                
                # If they were inactive, update to active (rejoin)
                if existing.get('current_status') == 'inactive':
                    return self.update_subscriber_rejoin(user_id, existing.get('id'))
                
                return True
            
            # Format the new subscriber data
            new_subscriber = {
                'user_id': user_id,
                'username': user_data.get('username', ''),
                'first_name': user_data.get('first_name', ''),
                'last_name': user_data.get('last_name', ''),
                'join_date': user_data.get('join_date', current_time),
                'current_status': user_data.get('current_status', 'active'),
                'reaction_counter': user_data.get('reaction_counter', 0),
                'is_admin': user_data.get('is_admin', False)
            }
            
            # Add the new subscriber
            url = f"{self.base_url}/docs/{self.doc_id}/tables/{self.table_name}/data"
            response = requests.post(
                url, 
                headers=self.headers,
                json=[new_subscriber]
            )
            
            if response.status_code in (200, 201):
                logger.info(f"Successfully added subscriber: {user_id}")
                return True
            else:
                logger.error(f"Error adding subscriber: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding subscriber: {e}")
            return False
    
    def update_subscriber_leave(self, user_id, record_id=None):
        """
        Update a subscriber record when they leave.
        
        Args:
            user_id: The Telegram user ID
            record_id: Optional record ID (if None, it will be looked up)
            
        Returns:
            bool: Success status
        """
        try:
            # Convert user_id to string for consistency
            user_id = str(user_id)
            
            # If no record_id provided, look it up
            if not record_id:
                subscriber = self.get_subscriber(user_id)
                if not subscriber:
                    logger.error(f"No subscriber found with user_id: {user_id}")
                    return False
                record_id = subscriber.get('id')
            
            current_time = datetime.now().isoformat()
            
            # Update the subscriber
            update_data = {
                'records': [{
                    'id': record_id,
                    'fields': {
                        'leave_date': current_time,
                        'current_status': 'inactive'
                    }
                }]
            }
            
            url = f"{self.base_url}/docs/{self.doc_id}/tables/{self.table_name}/data"
            response = requests.patch(
                url, 
                headers=self.headers,
                json=update_data
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully updated leave status for subscriber: {user_id}")
                return True
            else:
                logger.error(f"Error updating leave status: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating leave status: {e}")
            return False
    
    def update_subscriber_rejoin(self, user_id, record_id=None):
        """
        Update a subscriber record when they rejoin.
        
        Args:
            user_id: The Telegram user ID
            record_id: Optional record ID (if None, it will be looked up)
            
        Returns:
            bool: Success status
        """
        try:
            # Convert user_id to string for consistency
            user_id = str(user_id)
            
            # If no record_id provided, look it up
            if not record_id:
                subscriber = self.get_subscriber(user_id)
                if not subscriber:
                    logger.error(f"No subscriber found with user_id: {user_id}")
                    return False
                record_id = subscriber.get('id')
            
            current_time = datetime.now().isoformat()
            
            # Update the subscriber
            update_data = {
                'records': [{
                    'id': record_id,
                    'fields': {
                        'rejoin_date': current_time,
                        'current_status': 'active'
                    }
                }]
            }
            
            url = f"{self.base_url}/docs/{self.doc_id}/tables/{self.table_name}/data"
            response = requests.patch(
                url, 
                headers=self.headers,
                json=update_data
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully updated rejoin status for subscriber: {user_id}")
                return True
            else:
                logger.error(f"Error updating rejoin status: {response.status_code} - {response.text}")
                return False
                
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
            # Construct the filter query
            query = {}
            if status:
                query = {"filter": {"current_status": status}}
            
            # Add limit if provided
            params = {}
            if limit:
                params['limit'] = limit
            
            if query:
                params['filter'] = json.dumps(query)
            
            url = f"{self.base_url}/docs/{self.doc_id}/tables/{self.table_name}/records"
            response = requests.get(
                url, 
                headers=self.headers,
                params=params
            )
            
            if response.status_code != 200:
                logger.error(f"Error getting subscribers: {response.status_code} - {response.text}")
                return []
            
            records = response.json().get('records', [])
            
            # Format the records
            result = []
            for record in records:
                subscriber = {
                    'id': record.get('id'),
                    'user_id': record.get('user_id'),
                    'username': record.get('username'),
                    'first_name': record.get('first_name'),
                    'last_name': record.get('last_name'),
                    'join_date': record.get('join_date'),
                    'leave_date': record.get('leave_date'),
                    'rejoin_date': record.get('rejoin_date'),
                    'current_status': record.get('current_status'),
                    'reaction_counter': record.get('reaction_counter', 0),
                    'last_reacted': record.get('last_reacted')
                }
                result.append(subscriber)
            
            logger.info(f"Found {len(result)} subscribers")
            return result
            
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
            # Convert user_id to string for consistency
            user_id = str(user_id)
            
            # Get the current subscriber
            subscriber = self.get_subscriber(user_id)
            if not subscriber:
                logger.error(f"No subscriber found with user_id: {user_id}")
                return False
            
            record_id = subscriber.get('id')
            current_count = subscriber.get('reaction_counter', 0)
            current_time = datetime.now().isoformat()
            
            # Update the subscriber
            update_data = {
                'records': [{
                    'id': record_id,
                    'fields': {
                        'reaction_counter': current_count + 1,
                        'last_reacted': current_time
                    }
                }]
            }
            
            url = f"{self.base_url}/docs/{self.doc_id}/tables/{self.table_name}/data"
            response = requests.patch(
                url, 
                headers=self.headers,
                json=update_data
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully updated reaction count for subscriber: {user_id}")
                return True
            else:
                logger.error(f"Error updating reaction count: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating reaction count: {e}")
            return False
    
    def handle_webhook(self, request_data, token):
        """
        Process incoming webhook data from Grist.
        
        Args:
            request_data: Dict containing the webhook data
            token: Authentication token from the request
            
        Returns:
            dict: Response with processing status
        """
        try:
            # Validate webhook token
            if token != self.webhook_key:
                logger.error(f"Invalid webhook token: {token}")
                return {"status": "error", "message": "Invalid token"}
            
            # Process the webhook data
            event_type = request_data.get('type')
            table_id = request_data.get('tableId')
            
            if table_id != self.table_name:
                logger.warning(f"Webhook for different table: {table_id}")
                return {"status": "ignored", "message": "Not our table"}
            
            # Log the event
            logger.info(f"Processing webhook event: {event_type} for table {table_id}")
            
            # Here you can add custom logic for different webhook events
            if event_type == 'add':
                # New record added
                records = request_data.get('records', [])
                logger.info(f"New records added: {len(records)}")
            elif event_type == 'update':
                # Records updated
                records = request_data.get('records', [])
                logger.info(f"Records updated: {len(records)}")
            elif event_type == 'delete':
                # Records deleted
                record_ids = request_data.get('recordIds', [])
                logger.info(f"Records deleted: {len(record_ids)}")
            
            return {
                "status": "success", 
                "message": f"Processed {event_type} event",
                "processed": True
            }
            
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            return {"status": "error", "message": str(e)}

# For testing
if __name__ == "__main__":
    client = GristWebhookClient()
    init_result = client.init_table()
    print(f"Table initialization result: {init_result}")
    
    # Test getting all subscribers
    subscribers = client.get_all_subscribers()
    print(f"Retrieved {len(subscribers)} subscribers")