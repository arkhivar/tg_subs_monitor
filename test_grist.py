"""
Test script to debug Grist integration
"""
import os
import logging
from datetime import datetime
import config
from grist_api import GristDocAPI

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

def test_grist_direct():
    """Test direct connection to Grist API with detailed debugging."""
    try:
        # Get credentials from environment variables
        api_key = os.environ.get("GRIST_API_KEY")
        doc_id = os.environ.get("GRIST_DOC_ID")
        table_name = config.GRIST_TABLE_NAME

        logger.info(f"Testing Grist API with doc_id: {doc_id}, table: {table_name}")
        
        # Initialize the Grist API client
        api = GristDocAPI(doc_id, api_key)
        
        # Fetch all records from the table
        logger.info(f"Fetching all records from table: {table_name}")
        records = api.fetch_table(table_name)
        
        # Inspect the records
        logger.info(f"Records type: {type(records)}")
        logger.info(f"Records count: {len(records)}")
        
        # Print the first record if any
        if records:
            sample_record = records[0]
            logger.info(f"Sample record type: {type(sample_record)}")
            logger.info(f"Sample record: {sample_record}")
            
            # Get all attributes of the sample record
            logger.info(f"Sample record dir: {dir(sample_record)}")
            
            # Try to access specific fields we care about
            try:
                logger.info(f"Record id: {sample_record.id}")
                logger.info(f"Record user_id: {sample_record.user_id}")
                logger.info(f"Record current_status: {sample_record.current_status}")
                logger.info(f"Record join_date: {sample_record.join_date}")
                logger.info(f"Record reaction_counter: {sample_record.reaction_counter}")
            except AttributeError as e:
                logger.error(f"Error accessing field: {e}")
            
            # If the record is a dict-like object, print the keys
            if hasattr(sample_record, '__dict__'):
                logger.info(f"Sample record dict: {sample_record.__dict__}")
            elif hasattr(sample_record, 'keys'):
                logger.info(f"Sample record keys: {sample_record.keys()}")
                logger.info(f"Sample record values: {[sample_record[k] for k in sample_record.keys()]}")
        
        # Try to add a test record
        logger.info("Adding a test record...")
        test_data = {
            'user_id': '99999999',
            'username': 'test_direct',
            'first_name': 'Test',
            'last_name': 'Direct',
            'join_date': datetime.now().isoformat(),
            'current_status': 'active',
            'reaction_counter': 0,
            'is_admin': False
        }
        
        try:
            result = api.add_records(table_name, [test_data])
            logger.info(f"Add result: {result}")
        except Exception as e:
            logger.error(f"Error adding record: {e}")
        
        # Fetch the records again to see if our addition worked
        logger.info("Fetching records again...")
        updated_records = api.fetch_table(table_name)
        logger.info(f"Updated records count: {len(updated_records)}")
        
        # Check for our test record
        found = False
        for record in updated_records:
            try:
                user_id = record.user_id  # Try to access as attribute
                if user_id == '99999999':
                    found = True
                    logger.info(f"Found our test record: {record}")
                    break
            except AttributeError:
                if hasattr(record, 'get'):
                    user_id = record.get('user_id')
                    if user_id == '99999999':
                        found = True
                        logger.info(f"Found our test record: {record}")
                        break
        
        if not found:
            logger.warning("Test record not found in the updated list")
            
        return True
    except Exception as e:
        logger.error(f"Error testing Grist: {e}")
        return False

if __name__ == "__main__":
    test_grist_direct()