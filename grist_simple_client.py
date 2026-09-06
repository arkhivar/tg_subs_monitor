"""
Simple Grist Client for Telegram Bot

This module provides a client for interacting with Grist to store subscriber data.
Uses a simplified approach with the grist-api library.
"""

import os
import logging
from datetime import datetime
from grist_api.grist_api import GristDocAPI

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GristSimpleClient:
    """
    Client for interacting with Grist API to store subscriber data.
    """
    
    def __init__(self):
        """Initialize the Grist client with API credentials from environment variables."""
        self.api_key = os.environ.get("GRIST_API_KEY")
        self.doc_id = os.environ.get("GRIST_DOC_ID")
        
        # Get table name from config or environment
        from config import SUBSCRIBERS_TABLE, GRIST_SERVER
        self.table_name = SUBSCRIBERS_TABLE
        
        # Check for required credentials
        if not self.api_key or not self.doc_id:
            logger.error("Missing GRIST_API_KEY or GRIST_DOC_ID environment variables")
            self.api = None
        else:
            try:
                # Initialize the API client.
                # grist-api's GristDocAPI accepts a `server` kwarg (verified for
                # 0.1.1) and appends '/api/docs/<doc_id>/' itself, so pass the
                # bare instance base URL from GRIST_SERVER (no '/api' suffix).
                self.api = GristDocAPI(self.doc_id, api_key=self.api_key, server=GRIST_SERVER)
                logger.info(f"Initialized Grist client for document: {self.doc_id} on server: {GRIST_SERVER}")
            except Exception as e:
                logger.error(f"Error initializing Grist client: {e}")
                self.api = None
    
    def init_table(self):
        """
        Check if the subscribers table exists by trying to fetch records.
        
        Returns:
            bool: Success status
        """
        try:
            logger.info(f"Checking if Grist table '{self.table_name}' exists")
            
            if not self.api:
                logger.error("Grist API client not initialized")
                return False
            
            try:
                # Try to fetch records to see if the table exists
                response = self.api.fetch_table(self.table_name)
                
                # Check the structure of what we received
                logger.debug(f"Grist response type: {type(response)}")
                
                # If we get here, the table exists
                if isinstance(response, list):
                    logger.info(f"Table '{self.table_name}' exists with {len(response)} records")
                else:
                    logger.info(f"Table '{self.table_name}' exists but returned unexpected data type: {type(response)}")
                
                return True
            except Exception as e:
                if "Table not found" in str(e):
                    logger.info(f"Table '{self.table_name}' doesn't exist. Please create it in the Grist UI.")
                    logger.info(f"Required columns: user_id (Text), username (Text), first_name (Text), " + 
                             f"last_name (Text), join_date (Date), leave_date (Date), rejoin_date (Date), " +
                             f"current_status (Text), reaction_counter (Numeric), last_reacted (Date), is_admin (Toggle)")
                    return False
                else:
                    logger.error(f"Error checking if table exists: {e}")
                    return False
        except Exception as e:
            logger.error(f"Error initializing table: {e}")
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
            if not self.api:
                logger.error("Grist API client not initialized")
                return None
            
            # Convert user_id to string for consistency
            user_id = str(user_id)
            logger.info(f"Getting subscriber with user_id: {user_id}")
            
            # Fetch all records
            try:
                # Get all records
                response = self.api.fetch_table(self.table_name)
                
                # Check the structure of what we received
                logger.debug(f"Grist response type: {type(response)}")
                
                # Extract records from the response
                all_records = response if isinstance(response, list) else []
                
                # Log the record structure for debugging
                if all_records and len(all_records) > 0:
                    sample_record = all_records[0]
                    logger.debug(f"Sample record structure: {sample_record}")
                    if hasattr(sample_record, '__dir__'):
                        logger.debug(f"Sample record attributes: {dir(sample_record)}")
                
                # Find the record with matching user_id - Grist returns objects with attributes, not dicts
                for record in all_records:
                    try:
                        # Access user_id as an attribute
                        record_user_id = getattr(record, 'user_id', None)
                        
                        if record_user_id == user_id:
                            logger.info(f"Found subscriber by user_id: {record}")
                            
                            # Convert the record to a dict for easier handling
                            if hasattr(record, '_asdict'):
                                # If it has _asdict method (like namedtuple), use it
                                return record._asdict()
                            elif hasattr(record, '__dict__'):
                                # If it has __dict__, use that
                                return record.__dict__
                            else:
                                # Create a dict from the attributes we care about
                                record_dict = {
                                    'id': getattr(record, 'id', None),
                                    'user_id': getattr(record, 'user_id', None),
                                    'username': getattr(record, 'username', None),
                                    'first_name': getattr(record, 'first_name', None),
                                    'last_name': getattr(record, 'last_name', None),
                                    'join_date': getattr(record, 'join_date', None),
                                    'leave_date': getattr(record, 'leave_date', None),
                                    'rejoin_date': getattr(record, 'rejoin_date', None),
                                    'current_status': getattr(record, 'current_status', None),
                                    'reaction_counter': getattr(record, 'reaction_counter', 0),
                                    'last_reacted': getattr(record, 'last_reacted', None),
                                    'is_admin': getattr(record, 'is_admin', False)
                                }
                                return record_dict
                    except Exception as e:
                        logger.error(f"Error accessing record attributes: {e}")
                        continue
                
                logger.info(f"No subscriber found with user_id: {user_id}")
                # Log all user IDs for debugging
                if all_records:
                    try:
                        user_ids = [getattr(r, 'user_id', None) for r in all_records]
                        logger.debug(f"Available user_ids in database: {user_ids}")
                    except Exception as e:
                        logger.error(f"Error getting user_ids for debugging: {e}")
                return None
            except Exception as e:
                logger.error(f"Error fetching records: {e}")
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
            logger.info(f"➕ NEW SUBSCRIBER: Processing add subscriber with data: {user_data}")
            
            if not self.api:
                logger.error("❌ Grist API client not initialized")
                return False
            
            # Check if user_data already has user_id or if we need to use 'id'
            if 'user_id' in user_data:
                user_id = user_data.get('user_id')
            else:
                user_id = user_data.get('id')
            
            # Make sure user_id is a string
            user_id = str(user_id) if user_id is not None else None
            logger.info(f"🆔 Adding subscriber with user_id: {user_id}")
            
            # Check if the subscriber already exists
            logger.info(f"🔍 Checking if subscriber already exists with user_id: {user_id}")
            existing = self.get_subscriber(user_id)
            if existing:
                logger.info(f"🔄 Subscriber already exists: {user_id}")
                
                # If they were inactive, update to active (rejoin)
                if existing.get('current_status') == 'inactive':
                    logger.info(f"♻️ Subscriber was inactive, updating to active (rejoin)")
                    return self.update_subscriber_rejoin(user_id, existing.get('id'))
                
                logger.info(f"✅ Subscriber already active, no changes needed")
                return True
            
            # Format the data for Grist
            current_time = datetime.now().isoformat()
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
            
            logger.info(f"📝 Prepared new record for Grist: {new_record}")
            
            # Add the record to the Grist table
            try:
                result = self.api.add_records(self.table_name, [new_record])
                logger.info(f"✅ Successfully added subscriber: {user_id}, Result: {result}")
                
                # Verify the record was added
                verification = self.get_subscriber(user_id)
                if verification:
                    logger.info(f"✓ Verified subscriber was added: {user_id}")
                else:
                    logger.warning(f"⚠️ Could not verify subscriber was added: {user_id}")
                
                return True
            except Exception as e:
                logger.error(f"❌ Error adding subscriber to Grist: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ Error adding subscriber: {e}")
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
            logger.info(f"🔴 LEAVE EVENT: Processing leave update for user_id: {user_id}, record_id: {record_id}")
            
            if not self.api:
                logger.error("Grist API client not initialized")
                return False
            
            # Convert user_id to string for consistency
            user_id = str(user_id)
            
            # Get the subscriber record if record_id is not provided
            if not record_id:
                logger.info(f"🔍 Looking up record_id for user_id: {user_id}")
                subscriber = self.get_subscriber(user_id)
                if not subscriber:
                    logger.error(f"❌ No subscriber found with user_id: {user_id}")
                    # Let's try to diagnose why the user isn't found
                    try:
                        # Get all records and log their user_ids
                        response = self.api.fetch_table(self.table_name)
                        all_records = response if isinstance(response, list) else []
                        user_ids = []
                        for record in all_records:
                            try:
                                record_user_id = getattr(record, 'user_id', None)
                                user_ids.append(record_user_id)
                            except:
                                pass
                        logger.info(f"📊 All user_ids in database: {user_ids}")
                    except Exception as e:
                        logger.error(f"❌ Error fetching all user_ids: {e}")
                    return False
                record_id = subscriber.get('id')
                logger.info(f"✅ Found record_id: {record_id} for user_id: {user_id}")
            
            current_time = datetime.now().isoformat()
            logger.info(f"⏰ Setting leave time to: {current_time}")
            
            # Update the record in Grist
            try:
                update_data = {
                    'id': record_id,
                    'leave_date': current_time,
                    'current_status': 'inactive'
                }
                
                logger.info(f"📝 Updating record with data: {update_data}")
                result = self.api.update_records(self.table_name, [update_data])
                logger.info(f"✅ Successfully updated leave status for subscriber: {user_id}, Result: {result}")
                return True
            except Exception as e:
                logger.error(f"❌ Error updating leave status in Grist: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ Error updating leave status: {e}")
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
            logger.info(f"🟢 JOIN EVENT: Processing rejoin update for user_id: {user_id}, record_id: {record_id}")
            
            if not self.api:
                logger.error("Grist API client not initialized")
                return False
            
            # Convert user_id to string for consistency
            user_id = str(user_id)
            
            # Get the subscriber record if record_id is not provided
            if not record_id:
                logger.info(f"🔍 Looking up record_id for user_id: {user_id}")
                subscriber = self.get_subscriber(user_id)
                if not subscriber:
                    logger.error(f"❌ No subscriber found with user_id: {user_id}")
                    # Let's try to diagnose why the user isn't found
                    try:
                        # Get all records and log their user_ids
                        response = self.api.fetch_table(self.table_name)
                        all_records = response if isinstance(response, list) else []
                        user_ids = []
                        for record in all_records:
                            try:
                                record_user_id = getattr(record, 'user_id', None)
                                user_ids.append(record_user_id)
                            except:
                                pass
                        logger.info(f"📊 All user_ids in database: {user_ids}")
                    except Exception as e:
                        logger.error(f"❌ Error fetching all user_ids: {e}")
                    return False
                record_id = subscriber.get('id')
                logger.info(f"✅ Found record_id: {record_id} for user_id: {user_id}")
            
            current_time = datetime.now().isoformat()
            logger.info(f"⏰ Setting rejoin time to: {current_time}")
            
            # Update the record in Grist
            try:
                update_data = {
                    'id': record_id,
                    'rejoin_date': current_time,
                    'current_status': 'active'
                }
                
                logger.info(f"📝 Updating record with data: {update_data}")
                result = self.api.update_records(self.table_name, [update_data])
                logger.info(f"✅ Successfully updated rejoin status for subscriber: {user_id}, Result: {result}")
                return True
            except Exception as e:
                logger.error(f"❌ Error updating rejoin status in Grist: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ Error updating rejoin status: {e}")
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
            logger.info(f"⚡ REACTION UPDATE: Processing reaction update for user_id: {user_id}")
            
            if not self.api:
                logger.error("❌ Grist API client not initialized")
                return False
            
            # Convert user_id to string for consistency
            user_id = str(user_id)
            logger.info(f"🔍 Looking up subscriber with user_id: {user_id}")
            
            # Get the subscriber record
            subscriber = self.get_subscriber(user_id)
            if not subscriber:
                logger.error(f"❌ No subscriber found with user_id: {user_id}")
                
                # Detailed error logging to diagnose the issue
                logger.info(f"🔬 Attempting to diagnose why user {user_id} was not found")
                try:
                    # Get all table data for debugging
                    response = self.api.fetch_table(self.table_name)
                    all_records = response if isinstance(response, list) else []
                    logger.info(f"📊 Found {len(all_records)} total records in the table")
                    
                    # Log the first few records for inspection
                    if all_records and len(all_records) > 0:
                        for i, record in enumerate(all_records[:3]):  # Just show first 3 for brevity
                            try:
                                record_id = getattr(record, 'id', 'unknown')
                                record_user_id = getattr(record, 'user_id', 'unknown')
                                logger.info(f"📝 Record {i+1}: id={record_id}, user_id={record_user_id}")
                            except Exception as e:
                                logger.error(f"❌ Error accessing record {i+1}: {e}")
                except Exception as e:
                    logger.error(f"❌ Error fetching all records for diagnosis: {e}")
                
                return False
                
            record_id = subscriber.get('id')
            logger.info(f"✅ Found subscriber record with ID: {record_id}")
            
            current_count = int(subscriber.get('reaction_counter', 0))
            logger.info(f"📊 Current reaction count: {current_count} → {current_count + 1}")
            
            current_time = datetime.now().isoformat()
            logger.info(f"⏱️ Setting last_reacted to: {current_time}")
            
            # Update the record in Grist
            try:
                update_data = {
                    'id': record_id,
                    'reaction_counter': current_count + 1,
                    'last_reacted': current_time
                }
                
                logger.info(f"📝 Updating Grist with data: {update_data}")
                result = self.api.update_records(self.table_name, [update_data])
                logger.info(f"✅ Successfully updated reaction count for subscriber: {user_id}")
                logger.info(f"📝 Update result: {result}")
                
                # Verify the update
                updated = self.get_subscriber(user_id)
                if updated:
                    new_count = updated.get('reaction_counter', 0)
                    logger.info(f"✓ Verified new reaction count: {new_count}")
                    if new_count == current_count + 1:
                        logger.info(f"✅ Update successful")
                    else:
                        logger.warning(f"⚠️ Update may not have applied correctly")
                
                return True
            except Exception as e:
                logger.error(f"Error updating reaction count in Grist: {e}")
                return False
        except Exception as e:
            logger.error(f"Error updating reaction count: {e}")
            return False
            
    def update_admin_reaction(self, admin_id, username=None, first_name=None, last_name=None):
        """
        Update or create an admin reaction record.
        This is used for special cases where we want to track admin reactions in channels.
        
        Args:
            admin_id: The Telegram admin user ID
            username: Optional admin username
            first_name: Optional first name
            last_name: Optional last name
            
        Returns:
            bool: Success status
        """
        try:
            # Make sure we have a string user ID
            admin_id = str(admin_id)
            logger.info(f"⭐ ADMIN REACTION: Processing admin reaction for: {admin_id}")
            
            if not self.api:
                logger.error("❌ Grist API client not initialized")
                return False
            
            # Check if this admin already exists
            subscriber = self.get_subscriber(admin_id)
            
            if subscriber:
                # Update existing admin record
                record_id = subscriber.get('id')
                current_count = int(subscriber.get('reaction_counter', 0))
                current_time = datetime.now().isoformat()
                
                # Update the record
                update_data = {
                    'id': record_id,
                    'reaction_counter': current_count + 1,
                    'last_reacted': current_time,
                    'is_admin': True  # Ensure admin flag is set
                }
                
                logger.info(f"📝 Updating admin reaction count: {current_count} → {current_count + 1}")
                self.api.update_records(self.table_name, [update_data])
                logger.info(f"✅ Updated reaction count for admin {admin_id}")
                return True
            else:
                # Create a new admin record
                admin_data = {
                    'user_id': admin_id,
                    'username': username or f"Admin: {admin_id}",
                    'first_name': first_name or 'Channel Admin',
                    'last_name': last_name or '',
                    'join_date': datetime.now().isoformat(),
                    'current_status': 'active',
                    'reaction_counter': 1,
                    'last_reacted': datetime.now().isoformat(),
                    'is_admin': True
                }
                
                logger.info(f"📝 Creating new admin record: {admin_data}")
                self.add_subscriber(admin_data)
                logger.info(f"✅ Created new admin record with reaction count 1")
                return True
        except Exception as e:
            logger.error(f"❌ Error updating admin reaction: {e}")
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
            if not self.api:
                logger.error("Grist API client not initialized")
                return []
            
            logger.info(f"Getting all subscribers with status: {status}")
            
            try:
                # Fetch all records from the Grist table
                response = self.api.fetch_table(self.table_name)
                
                # Check the structure of what we received
                logger.debug(f"Grist response type: {type(response)}")
                
                # Extract records from the response
                # In grist-api, fetch_table returns a list of records
                all_records = response if isinstance(response, list) else []
                
                # Convert the custom Grist objects to dictionaries for easier handling
                processed_records = []
                for record in all_records:
                    try:
                        # Check if this is a custom Grist object with attributes
                        if hasattr(record, 'user_id') or hasattr(record, 'id'):
                            # If it has _asdict method (like namedtuple), use it
                            if hasattr(record, '_asdict'):
                                processed_records.append(record._asdict())
                            else:
                                # Create a dict from the attributes we care about
                                record_dict = {
                                    'id': getattr(record, 'id', None),
                                    'user_id': getattr(record, 'user_id', None),
                                    'username': getattr(record, 'username', None),
                                    'first_name': getattr(record, 'first_name', None),
                                    'last_name': getattr(record, 'last_name', None),
                                    'join_date': getattr(record, 'join_date', None),
                                    'leave_date': getattr(record, 'leave_date', None),
                                    'rejoin_date': getattr(record, 'rejoin_date', None),
                                    'current_status': getattr(record, 'current_status', None),
                                    'reaction_counter': getattr(record, 'reaction_counter', 0),
                                    'last_reacted': getattr(record, 'last_reacted', None),
                                    'is_admin': getattr(record, 'is_admin', False)
                                }
                                processed_records.append(record_dict)
                        elif isinstance(record, dict):
                            # If it's already a dict, just add it
                            processed_records.append(record)
                        else:
                            # If it's something else with a __dict__, convert it
                            if hasattr(record, '__dict__'):
                                processed_records.append(record.__dict__)
                    except Exception as e:
                        logger.error(f"Error processing record: {e}")
                
                # Filter by status if provided and records have that field
                if status:
                    try:
                        records = [r for r in processed_records if r.get('current_status') == status]
                    except Exception as e:
                        logger.error(f"Error filtering records by status: {e}")
                        records = processed_records
                else:
                    records = processed_records
                
                # Apply limit if provided
                if limit and isinstance(limit, int) and limit > 0:
                    records = records[:limit]
                
                logger.info(f"Found {len(records)} subscribers")
                return records
            except Exception as e:
                logger.error(f"Error fetching subscribers from Grist: {e}")
                return []
        except Exception as e:
            logger.error(f"Error getting all subscribers: {e}")
            return []

# For testing
if __name__ == "__main__":
    client = GristSimpleClient()
    result = client.init_table()
    print(f"Initialization result: {result}")
    
    subscribers = client.get_all_subscribers()
    print(f"Found {len(subscribers)} subscribers")