import os
import base64
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class EmailHandler:
    def __init__(self, credentials_file='credentials.json', token_file='token.json'):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Gmail API"""
        creds = None
        
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=creds)
        print(" gmail API authenticated successfully")

    
    def get_recent_emails(self, max_results=10, hours=24):
        """Fetch recent emails from last X hours"""
        try:
            after_date = datetime.now() - timedelta(hours=hours)
            query = f'after:{int(after_date.timestamp())}'
            
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                return []
            
            emails = []
            for msg in messages:
                email_data = self.get_email_details(msg['id'])
                if email_data:
                    emails.append(email_data)
            
            return emails
        
        except Exception as e:
            print(f" error fetching emails: {e}")
            return []
        
    
    def get_email_details(self, msg_id):
        """Get detailed information about a specific email"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            headers = message['payload']['headers']
            
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            body = self.get_email_body(message['payload'])
            
            is_unread = 'UNREAD' in message.get('labelIds', [])
            is_important = 'IMPORTANT' in message.get('labelIds', [])
            
            return {
                'id': msg_id,
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body[:500],  
                'is_unread': is_unread,
                'is_important': is_important,
                'snippet': message.get('snippet', '')
            }
        
        except Exception as e:
            print(f" error getting email details: {e}")
            return None
        
    def get_email_body(self, payload):
        """Extract email body from payload"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
        elif 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        
        return body
    

    def count_unread_urgent(self):
        """Count unread and urgent emails"""
        try:
            unread = self.service.users().messages().list(
                userId='me',
                q='is:unread',
                maxResults=100
            ).execute()
            
            important = self.service.users().messages().list(
                userId='me',
                q='is:important is:unread',
                maxResults=100
            ).execute()
            
            return {
                'unread_count': len(unread.get('messages', [])),
                'urgent_count': len(important.get('messages', []))
            }
        
        except Exception as e:
            print(f" error counting emails: {e}")
            return {'unread_count': 0, 'urgent_count': 0}
        
        
if __name__ == "__main__":
    handler = EmailHandler()
    
    emails = handler.get_recent_emails(max_results=5)
    
    for email in emails:
        print(f"\nFrom: {email['sender']}")
        print(f"Subject: {email['subject']}")
        print(f"Unread: {email['is_unread']}, Important: {email['is_important']}")
        print(f"Snippet: {email['snippet'][:100]}...")
    
    print("\n=== Email Counts ===")
    counts = handler.count_unread_urgent()
    print(f"Unread: {counts['unread_count']}")
    print(f"Urgent: {counts['urgent_count']}")