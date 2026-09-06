"""
Test direct connection to Grist API with detailed error reporting.
"""

import os
import logging
import sys
from grist_api import GristDocAPI

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_grist_connection():
    """Test direct connection to Grist API with detailed error reporting."""
    try:
        # Get credentials from environment
        api_key = os.environ.get("GRIST_API_KEY")
        doc_id = os.environ.get("GRIST_DOC_ID")
        
        print(f"Testing Grist connection with document ID: {doc_id}")
        print(f"API Key present: {'Yes' if api_key else 'No'}")
        
        if not api_key or not doc_id:
            print("Missing GRIST_API_KEY or GRIST_DOC_ID environment variables")
            return False
        
        # Initialize API client
        api = GristDocAPI(doc_id, api_key=api_key)
        print("Successfully initialized GristDocAPI client")
        
        # Test 1: List all tables in the document
        print("\nTest 1: Listing all tables in the document...")
        try:
            tables_data = api.list_tables()
            print(f"Success! Found {len(tables_data)} tables:")
            for i, table in enumerate(tables_data):
                print(f"  Table {i+1}: {table.get('id')}")
        except Exception as e:
            print(f"Error listing tables: {e}")
        
        # Test 2: Try to access a specific table
        table_name = "subscribers"
        print(f"\nTest 2: Trying to access table '{table_name}'...")
        try:
            records = api.fetch_table(table_name)
            print(f"Success! Found {len(records)} records in the '{table_name}' table")
            if records:
                print(f"First record sample: {records[0]}")
        except Exception as e:
            print(f"Error accessing table '{table_name}': {e}")
        
        # Test 3: Try with alternate table name
        table_name = "TABLE1"
        print(f"\nTest 3: Trying to access table '{table_name}'...")
        try:
            records = api.fetch_table(table_name)
            print(f"Success! Found {len(records)} records in the '{table_name}' table")
            if records:
                print(f"First record sample: {records[0]}")
        except Exception as e:
            print(f"Error accessing table '{table_name}': {e}")
        
        # If we got here without raising a critical exception, we connected successfully
        print("\nBasic connection to Grist API successful!")
        return True
        
    except Exception as e:
        print(f"Critical error testing Grist connection: {e}")
        return False

if __name__ == "__main__":
    success = test_grist_connection()
    sys.exit(0 if success else 1)