#!/usr/bin/env python3

import requests
import os
import json
import time
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from urllib.parse import urlencode
import sys

# Configuration
CLIENT_ID = os.environ.get('CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', '')
TOKEN_URL = "https://www.strava.com/oauth/token"
AUTH_URL = "https://www.strava.com/oauth/authorize"
API_BASE = "https://www.strava.com/api/v3"
REDIRECT_URI = os.environ.get('REDIRECT_URI', "http://localhost:8000/callback")
ACTIVITY_LOOKBACK_MINUTES = int(os.environ.get('ACTIVITY_LOOKBACK_MINUTES', 300))  # Timeframe to check for recent activities

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Token storage
TOKEN_FILE = Path(os.environ.get('TOKEN_FILE', Path.home() / ".strava_token.json"))

# Validate required environment variables
def validate_credentials():
    if not CLIENT_ID:
        error_msg = "ERROR: CLIENT_ID environment variable is not set"
        logging.error(error_msg)
        print(error_msg)
        sys.exit(1)
    
    if not CLIENT_SECRET:
        error_msg = "ERROR: CLIENT_SECRET environment variable is not set"
        logging.error(error_msg)
        print(error_msg)
        sys.exit(1)
    
    logging.info("Credentials validated successfully")

# Global variable to store the authorization code
auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        
        if '/callback' in self.path:
            query = self.path.split('?', 1)[1] if '?' in self.path else ''
            params = {k: v for k, v in [p.split('=') for p in query.split('&')] if k and v}
            
            if 'code' in params:
                auth_code = params['code']
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"Authorization successful! You can close this window and return to the script.")
                
                # Stop the server after getting the code
                threading.Timer(0.1, lambda: self.server.shutdown()).start()

    def log_message(self, format, *args):
        # Suppress the default server log
        return

def get_auth_code():
    """Get authorization code through OAuth flow"""
    global auth_code
    
    # Start temporary web server to catch the redirect
    server = HTTPServer(('localhost', 8000), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    # Generate authorization URL
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'activity:write,activity:read_all'
    }
    
    auth_url = f"{AUTH_URL}?{urlencode(params)}"
    print(f"Opening browser for authorization...")
    webbrowser.open(auth_url)
    
    # Wait for the callback to be processed
    server_thread.join()
    server.server_close()
    
    if not auth_code:
        raise Exception("Failed to get authorization code")
    
    return auth_code

def get_initial_token(auth_code):
    """Exchange authorization code for access token"""
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'grant_type': 'authorization_code'
    }
    
    response = requests.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        logging.error(f"Token exchange failed: {response.text}")
        raise Exception(f"Token exchange failed: {response.text}")
    
    token_data = response.json()
    save_initial_token(token_data)
    return token_data.get('access_token')

def get_access_token():
    """Get a valid access token, refreshing if necessary"""
    try:
        if TOKEN_FILE.exists():
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
            
            # Check if token is expired
            if token_data.get('expires_at', 0) <= time.time():
                logging.info("Token expired, refreshing...")
                return refresh_token(token_data.get('refresh_token'))
            else:
                logging.info("Using existing token")
                return token_data.get('access_token')
        else:
            logging.info("No token file found. Starting manual authorization...")
            auth_code = get_auth_code()
            return get_initial_token(auth_code)
    except Exception as e:
        logging.error(f"Error getting access token: {e}")
        raise

def refresh_token(refresh_token):
    """Refresh the access token"""
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    
    response = requests.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        logging.error(f"Token refresh failed: {response.text}")
        raise Exception(f"Token refresh failed: {response.text}")
    
    token_data = response.json()
    
    # Save the new token
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f)
    
    logging.info("Token refreshed successfully")
    return token_data.get('access_token')

def update_activity(activity_id, access_token):
    """Update activity to exclude it from home feed if not already excluded"""
    url = f"{API_BASE}/activities/{activity_id}"
    headers = {'Authorization': f"Bearer {access_token}"}
    
    # Fetch activity details to check if it's already excluded
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logging.error(f"Failed to fetch activity {activity_id}: {response.text}")
        return False
    
    activity_details = response.json()
    if activity_details.get('hide_from_home', False):
        logging.info(f"Activity {activity_id} is already excluded from home feed")
        return True
    
    # Update activity to exclude it from home feed
    data = {'hide_from_home': True}
    response = requests.put(url, headers=headers, json=data)
    if response.status_code != 200:
        logging.error(f"Failed to update activity {activity_id}: {response.text}")
        return False
    
    logging.info(f"Successfully updated activity {activity_id}")
    return True

def get_recent_activities(access_token, minutes=ACTIVITY_LOOKBACK_MINUTES):
    """Get the most recent 10 activities created in the last X minutes (default: 300 minutes/5 hours)"""
    url = f"{API_BASE}/athlete/activities"
    headers = {'Authorization': f"Bearer {access_token}"}
    
    # Fetch the last 10 activities
    params = {'per_page': 10, 'page': 1}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        logging.error(f"Failed to retrieve activities: {response.text}")
        raise Exception(f"Failed to retrieve activities: {response.text}")
    
    activities = response.json()
    
    # Calculate the cutoff time in UTC using timezone.utc
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    # Add debug logging
    logging.info(f"Current UTC time: {datetime.now(timezone.utc)}, Cutoff time: {cutoff_time}")
    
    # Filter activities created in the last X minutes
    recent_activities = [
        activity for activity in activities
        if datetime.strptime(activity['start_date'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) >= cutoff_time
    ]
    
    logging.info(f"Found {len(recent_activities)} activities within the last {minutes} minutes")
    return recent_activities

def main():
    try:
        logging.info("Starting Strava hide from home feed job")

        validate_credentials()

        access_token = get_access_token()
        
        # Get recent activities using the ACTIVITY_LOOKBACK_MINUTES value
        recent_activities = get_recent_activities(access_token, minutes=ACTIVITY_LOOKBACK_MINUTES)
        
        if not recent_activities:
            logging.info("No recent activities found to process")
            return
        
        # Track statistics
        already_excluded = []
        newly_excluded = []
        
        # Process each recent activity
        for activity in recent_activities:
            activity_id = activity['id']
            activity_name = activity['name']
            logging.info(f"Processing activity: {activity_name} (ID: {activity_id})")
            
            # Get current status first
            url = f"{API_BASE}/activities/{activity_id}"
            headers = {'Authorization': f"Bearer {access_token}"}
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                logging.error(f"Failed to fetch activity {activity_id}: {response.text}")
                continue
                
            activity_details = response.json()
            
            if activity_details.get('hide_from_home', False):
                logging.info(f"Activity '{activity_name}' (ID: {activity_id}) is already excluded from home feed")
                already_excluded.append({"id": activity_id, "name": activity_name})
                continue
            
            # Update the activity if not already excluded
            success = update_activity(activity_id, access_token)
            if success:
                logging.info(f"Activity '{activity_name}' (ID: {activity_id}) newly excluded from home feed")
                newly_excluded.append({"id": activity_id, "name": activity_name})
        
        # Summary stats
        logging.info(f"Job completed. Found {len(recent_activities)} recent activities:")
        
        if already_excluded:
            logging.info(f"Activities already excluded ({len(already_excluded)}):")
            for activity in already_excluded:
                logging.info(f"  - ID: {activity['id']}, Name: {activity['name']}")
        
        if newly_excluded:
            logging.info(f"Activities newly excluded ({len(newly_excluded)}):")
            for activity in newly_excluded:
                logging.info(f"  - ID: {activity['id']}, Name: {activity['name']}")
        
        if not already_excluded and not newly_excluded:
            logging.info("No activities were excluded")
        
    except Exception as e:
        logging.error(f"Error in job: {e}")

# Save tokens after first manual run
def save_initial_token(token_data):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f)
    logging.info("Initial token saved")

if __name__ == "__main__":
    main()
