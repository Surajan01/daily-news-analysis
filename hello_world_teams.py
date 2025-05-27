#!/usr/bin/env python3
"""
Hello World Teams Connection Test
Simple script to verify Teams webhook integration works
"""

import requests
import json
import os
from datetime import datetime

def send_hello_world_message():
    """Send a simple test message to Teams"""
    
    # Get the webhook URL from environment variable
    webhook_url = os.getenv('TEAMS_WEBHOOK_URL')
    
    if not webhook_url:
        print("Error: TEAMS_WEBHOOK_URL environment variable not set")
        return False
    
    # Create message with proper Teams format including attachments array
    message = {
        "text": "Hello from GitHub Actions!",
        "attachments": []
    }
    
    try:
        # Send the message to Teams
        response = requests.post(
            webhook_url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(message),
            timeout=30
        )
        
        # Check if successful (Teams returns 202, not 200)
        if response.status_code in [200, 202]:
            print("✅ Message sent successfully to Teams!")
            return True
        else:
            print(f"❌ Failed to send message. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error sending message to Teams: {e}")
        return False

if __name__ == "__main__":
    print("Starting Hello World Teams test...")
    success = send_hello_world_message()
    
    if success:
        print("🎉 Test completed successfully!")
    else:
        print("💥 Test failed - check your webhook URL and try again")
        exit(1)
