#!/usr/bin/env python3
# checks if acitivy if uploaded in the last 60 minutes and hide it from home feed

import requests
import os
import json
import time
from datetime import datetime, timedelta
import logging
from pathlib import Path
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from urllib.parse import urlencode

# Configuration
CLIENT_ID = "12345"
CLIENT_SECRET = "123454321234543214543212"
TOKEN_URL = "https://www.strava.com/oauth/token"
AUTH_URL = "https://www.strava.com/oauth/authorize"
API_BASE = "https://www.strava.com/api/v3"
REDIRECT_URI = "http://localhost:8000/callback"

# Setup logging
LOG_FILE = Path.home() / "strava_exclude_job.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Token storage
TOKEN_FILE = Path.home() / ".strava_token.json"

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
    """Update activity to exclude it from home feed"""
    url = f"{API_BASE}/activities/{activity_id}"
    headers = {'Authorization': f"Bearer {access_token}"}
    data = {'hide_from_home': True}
    
    response = requests.put(url, headers=headers, json=data)
    if response.status_code != 200:
        logging.error(f"Failed to update activity {activity_id}: {response.text}")
        return False
    
    logging.info(f"Successfully updated activity {activity_id}")
    return True

def get_recent_activities(access_token, minutes=60):
    """Get activities created in the last X minutes (default: 60 minutes/1 hour)"""
    url = f"{API_BASE}/athlete/activities"
    headers = {'Authorization': f"Bearer {access_token}"}
    
    # Get more activities to ensure we don't miss any
    params = {'per_page': 30}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        logging.error(f"Failed to retrieve activities: {response.text}")
        raise Exception(f"Failed to retrieve activities: {response.text}")
    
    activities = response.json()
    
    # Calculate the cutoff time
    cutoff_time = datetime.now() - timedelta(minutes=minutes)
    
    # Filter activities created in the last X minutes
    recent_activities = []
    for activity in activities:
        activity_time = datetime.strptime(activity['start_date'], "%Y-%m-%dT%H:%M:%SZ")
        if activity_time >= cutoff_time:
            recent_activities.append(activity)
    
    return recent_activities

def main():
    try:
        logging.info("Starting Strava auto-exclude job")
        
        # Get valid access token
        access_token = get_access_token()
        
        # Get recent activities from the past hour
        recent_activities = get_recent_activities(access_token, minutes=60)
        
        if not recent_activities:
            logging.info("No recent activities found to process")
            return
        
        # Process each recent activity
        for activity in recent_activities:
            logging.info(f"Processing activity: {activity['name']} (ID: {activity['id']})")
            success = update_activity(activity['id'], access_token)
            if success:
                logging.info(f"Activity '{activity['name']}' excluded from home feed")
        
        logging.info(f"Job completed, processed {len(recent_activities)} activities")
        
    except Exception as e:
        logging.error(f"Error in job: {e}")

# Save tokens after first manual run
def save_initial_token(token_data):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f)
    logging.info("Initial token saved")

if __name__ == "__main__":
    main()
