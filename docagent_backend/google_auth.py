"""
Simple Google Authentication for Google Docs API.
"""

import os
import json
import logging
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/documents']

class GoogleAuth:
    def __init__(self, credentials_path="credentials.json"):
        self.credentials_path = credentials_path
        self.token_path = "token.json"
        self._service = None
    
    def get_service(self):
        """Get authenticated Google Docs service."""
        if self._service:
            return self._service
        
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        # If no valid credentials, run OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        self._service = build('docs', 'v1', credentials=creds)
        logger.info("Google Docs service authenticated successfully")
        return self._service
    