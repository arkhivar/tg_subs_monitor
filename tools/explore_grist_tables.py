"""
Explore Grist document structure
"""

import os
import logging
import sys
import requests
import json

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def explore_grist_structure():
    """Explore Grist document structure using the raw API."""
    try:
        # Get credentials from environment
        api_key = os.environ.get("GRIST_API_KEY")
        doc_id = os.environ.get("GRIST_DOC_ID")
        
        print(f"Exploring Grist document structure for ID: {doc_id}")
        print(f"API Key present: {'Yes' if api_key else 'No'}")
        
        if not api_key or not doc_id:
            print("Missing GRIST_API_KEY or GRIST_DOC_ID environment variables")
            return False
        
        # Base URL for Grist API. GRIST_SERVER holds the bare instance base URL
        # (no '/api' suffix) — same convention as config.py/grist_simple_client.py —
        # so the '/api' prefix is appended here explicitly.
        grist_server = os.environ.get("GRIST_SERVER", "https://api.getgrist.com").rstrip("/")
        base_url = f"{grist_server}/api/docs/{doc_id}"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # Test 1: Get document metadata
        print("\nTest 1: Getting document metadata...")
        try:
            response = requests.get(f"{base_url}", headers=headers)
            if response.status_code == 200:
                print(f"Success! Document metadata retrieved successfully.")
                print(f"Document name: {response.json().get('name', 'Unknown')}")
            else:
                print(f"Error: Got status code {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error getting document metadata: {e}")
        
        # Test 2: Get document structure
        print("\nTest 2: Getting document structure...")
        try:
            response = requests.get(f"{base_url}/structure", headers=headers)
            if response.status_code == 200:
                print(f"Success! Document structure retrieved successfully.")
                data = response.json()
                
                # Extract tables
                if "tables" in data:
                    tables = data["tables"]
                    print(f"Found {len(tables)} tables:")
                    for i, table in enumerate(tables):
                        print(f"  Table {i+1}: ID={table.get('id')}, Title={table.get('title')}")
                        
                        # Print columns
                        if "columns" in table:
                            print(f"    Columns:")
                            for col in table["columns"]:
                                print(f"      {col.get('id')} ({col.get('type')})")
                else:
                    print("No tables found in document structure")
            else:
                print(f"Error: Got status code {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error getting document structure: {e}")
        
        # Test 3: Try direct access to table data
        print("\nTest 3: Try different table names...")
        table_names = ["Users", "Chats", "Membership", "Events"]
        for table_name in table_names:
            try:
                response = requests.get(f"{base_url}/tables/{table_name}/data", headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Print table data
                    print(f"Success! Table '{table_name}' found with {len(data.get('records', []))} records")
                    if len(data.get('records', [])) > 0:
                        print(f"  First record: {json.dumps(data['records'][0], indent=2)}")
                else:
                    print(f"Error with table '{table_name}': Got status code {response.status_code}")
            except Exception as e:
                print(f"Error accessing table '{table_name}': {e}")
        
        print("\nExploration completed!")
        return True
        
    except Exception as e:
        print(f"Critical error exploring Grist structure: {e}")
        return False

if __name__ == "__main__":
    success = explore_grist_structure()
    sys.exit(0 if success else 1)