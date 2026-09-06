#!/usr/bin/env python3

import os
import sys
import logging
from datetime import datetime
from grist_api.grist_api import GristDocAPI

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("direct_grist_test")

def test_direct_grist():
    """Test direct connection to Grist API with minimal code."""
    
    # Get credentials
    api_key = os.environ.get("GRIST_API_KEY")
    doc_id = os.environ.get("GRIST_DOC_ID")
    table_name = "channels"
    
    if not api_key or not doc_id:
        logger.error("Missing GRIST_API_KEY or GRIST_DOC_ID environment variables")
        return False
    
    logger.info(f"Testing Grist connection with API key and Doc ID: {doc_id}")
    
    try:
        # Initialize the API client
        api = GristDocAPI(doc_id, api_key=api_key)
        logger.info("Created GristDocAPI client")
        
        # Try to fetch records from the table
        try:
            logger.info(f"Attempting to fetch records from table '{table_name}'")
            records = api.fetch_table(table_name)
            logger.info(f"Successfully fetched {len(records)} records from table '{table_name}'")
            for record in records[:5]:  # Show up to 5 records
                logger.info(f"Record: {record}")
            return True
        except Exception as e:
            logger.error(f"Error fetching records: {e}")
            
            # Table might not exist, try to create it
            logger.info("Table might not exist. Adding test record to create table")
            
            # Create test data
            test_record = {
                "user_id": "test_user",
                "username": "test_username",
                "first_name": "Test",
                "last_name": "User",
                "join_date": datetime.now().isoformat(),
                "current_status": "active",
                "reaction_counter": 0
            }
            
            try:
                # This will create the table if it doesn't exist
                logger.info(f"Adding test record to create table '{table_name}'")
                result = api.add_records(table_name, [test_record])
                logger.info(f"Test record added successfully: {result}")
                
                # Try to fetch again to confirm
                records = api.fetch_table(table_name)
                logger.info(f"Table created and fetched {len(records)} records")
                return True
            except Exception as e:
                logger.error(f"Failed to create table: {e}")
                return False
    
    except Exception as e:
        logger.error(f"Error in direct Grist test: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting direct Grist test")
    if test_direct_grist():
        print("✅ Grist test successful!")
    else:
        print("❌ Grist test failed!")