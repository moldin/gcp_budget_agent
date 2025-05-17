import os
import pickle
import base64
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional, Any
import urllib.parse

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

# SCOPES: If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# --- Configuration ---
# Ensure your client secret JSON file is at this path or update the path.
# You can download this file from the Google Cloud Console for your OAuth 2.0 Client ID.
CLIENT_SECRET_FILE = 'credentials/client_secret.json'
TOKEN_PICKLE_FILE = 'credentials/token.pickle'
CREDENTIALS_DIR = 'credentials'

def get_gmail_service() -> Optional[Any]:
    """
    Authenticates with the Gmail API and returns a service object.
    Handles token storage and refresh.
    """
    creds = None
    if not os.path.exists(CREDENTIALS_DIR):
        try:
            os.makedirs(CREDENTIALS_DIR)
        except OSError as e:
            print(f"Error creating credentials directory {CREDENTIALS_DIR}: {e}")
            return None

    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, 'rb') as token_file:
            try:
                creds = pickle.load(token_file)
            except pickle.UnpicklingError:
                os.remove(TOKEN_PICKLE_FILE)
                creds = None # Will trigger re-authentication
            except EOFError: # File might be empty or corrupted
                os.remove(TOKEN_PICKLE_FILE)
                creds = None


    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e: # Catches google.auth.exceptions.RefreshError among others
                if os.path.exists(TOKEN_PICKLE_FILE): # Delete problematic token
                    os.remove(TOKEN_PICKLE_FILE)
                creds = None # Will trigger re-authentication
        
        if not creds: # creds is None if refresh failed or no token existed
            if not os.path.exists(CLIENT_SECRET_FILE):
                print(f"Error: Client secret file not found at {CLIENT_SECRET_FILE}")
                print("Please download your OAuth 2.0 client credentials from Google Cloud Console")
                print("and place it as 'client_secret.json' in the 'credentials' directory.")
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            except FileNotFoundError:
                print(f"Error: Client secret file not found at {CLIENT_SECRET_FILE}")
                return None
            except Exception as e:
                print(f"Error during OAuth flow: {e}")
                return None

        # Save the credentials for the next run
        with open(TOKEN_PICKLE_FILE, 'wb') as token_file:
            pickle.dump(creds, token_file)
            print(f"Token saved to {TOKEN_PICKLE_FILE}")

    try:
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        print(f"Error building Gmail service: {e}")
        return None

def is_text_clearly_a_url(text: str, href: Optional[str] = None) -> bool:
    """Helper function to determine if a string is likely a URL."""
    if not text:
        return False
    
    # Condition 1: Starts with common schemes or 'www.'
    if text.startswith(('http://', 'https://', 'www.', 'ftp://', 'mailto:')):
        return True
    
    # Condition 2: Is identical to the href attribute (if href is provided)
    if href and text == href:
        return True
        
    # Condition 3: Heuristic for URL-like strings 
    if len(text) > 20 and ' ' not in text and \
       any(c in text for c in ['.', '/', '?', '=', '&', '~', '%', '#', '@']):
        if (text.count('.') >= 1 or text.count('/') >=1) and re.search(r'[a-zA-Z]', text):
            return True
    return False

def _decode_email_part_data(data: str, mime_type: str) -> str:
    """
    Decodes base64url encoded email part data.
    If HTML, uses BeautifulSoup to extract text. Links are formatted as [Descriptive Text] or [Link].
    If Plain, normalizes whitespace.
    """
    try:
        byte_data = base64.urlsafe_b64decode(data)
        text_content = byte_data.decode('utf-8', errors='replace')

        if mime_type == 'text/html':
            soup = BeautifulSoup(text_content, 'html.parser')

            for unwanted_tag in soup(["script", "style", "head", "title", "meta", "link"]):
                unwanted_tag.decompose()

            for a_tag in soup.find_all('a', href=True):
                actual_href = a_tag.get('href', '')
                text_from_anchor = a_tag.get_text(strip=True)
                display_text_for_brackets = "Link" # Default to "[Link]"

                if text_from_anchor: 
                    if not is_text_clearly_a_url(text_from_anchor, actual_href):
                        display_text_for_brackets = text_from_anchor
                # If display_text is still "Link", try alt text from image
                if display_text_for_brackets == "Link":
                    img_tag = a_tag.find('img', alt=True)
                    if img_tag:
                        alt_text = img_tag.get('alt', '').strip()
                        if alt_text: 
                            if not is_text_clearly_a_url(alt_text, actual_href):
                                display_text_for_brackets = alt_text
                replacement_string = f"[{display_text_for_brackets}]"
                a_tag.replace_with(soup.new_string(replacement_string + " "))

            text = soup.get_text(separator=' ', strip=False)
            text = re.sub(r'[ \t]+', ' ', text)
            text = "\n".join([line.strip() for line in text.splitlines()])
            text = re.sub(r'\n\n+', '\n\n', text)
            text = text.strip()
            return text
        else: # For text/plain
            text_content = re.sub(r'[ \t]+', ' ', text_content)
            text_content = re.sub(r'\n\n+', '\n\n', text_content)
            return text_content.strip()
    except Exception as e:
        import traceback 
        return "(Error processing email content due to exception)"    

def format_email_for_display(email_data: Dict[str, Any]) -> str:
    """
    Formats the new-style email dict (with keys: subject, from, to, body, date) into a display string.
    """
    if not email_data:
        return "No email data to display."

    date_str = email_data.get('date', 'N/A')
    from_str = email_data.get('from', 'N/A')
    to_str = email_data.get('to', 'N/A')
    subject_str = email_data.get('subject', '(No Subject)')
    body_str = email_data.get('body')
    if not body_str or body_str.startswith("(Error"):
        body_str = "(No readable body content found or error in processing)"

    output_lines = [
        f"Date: {date_str}",
        f"From: {from_str}",
        f"To: {to_str}",
        f"Subject: {subject_str}",
        "Body:",
        body_str
    ]
    return "\n".join(output_lines)

def _find_best_text_in_parts(parts: List[Dict]) -> Optional[str]:
    """
    Recursively searches a list of email parts for the best text representation.
    PRIORITIZES text/html, then falls back to text/plain.
    """
    html_content: Optional[str] = None
    plain_content: Optional[str] = None

    for i, part in enumerate(parts):
        mime_type = part.get('mimeType', '').lower()
        part_body = part.get('body', {})
        part_data = part_body.get('data')

        if mime_type.startswith('multipart/') and 'parts' in part:
            nested_content = _find_best_text_in_parts(part['parts'])
            if nested_content:
                return nested_content 
        elif mime_type == 'text/html' and part_data:
            if not html_content:
                html_content = _decode_email_part_data(part_data, mime_type)
        elif mime_type == 'text/plain' and part_data:
            if not plain_content:
                plain_content = _decode_email_part_data(part_data, mime_type)

    if html_content:
        return html_content
    if plain_content:
        return plain_content
    return None

def extract_email_body(payload: Dict) -> Optional[str]:
    """
    Extracts the most suitable text body from a Gmail message payload.
    """
    if not payload:
        return None

    mime_type = payload.get('mimeType', '').lower()
    
    if 'parts' in payload:
        return _find_best_text_in_parts(payload['parts'])
    elif 'body' in payload and 'data' in payload['body']:
        if mime_type == 'text/plain' or mime_type == 'text/html':
            return _decode_email_part_data(payload['body']['data'], mime_type)
    
    return None

def get_email_details_structured(service: Any, user_id: str, msg_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches and structures the details of a single email message.
    Returns a dictionary containing parsed information and the raw payload.
    """
    try:
        message_resource = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()
        
        if not message_resource:
            return None

        email_data: Dict[str, Any] = {
            "id": message_resource.get('id'),
            "threadId": message_resource.get('threadId'),
            "snippet": message_resource.get('snippet'),
            "historyId": message_resource.get('historyId'),
            "internalDate": message_resource.get('internalDate'), # Unix timestamp as string
            "labelIds": message_resource.get('labelIds', []),
            "sizeEstimate": message_resource.get('sizeEstimate'),
            
            "headers_parsed": {}, # For quick access to common headers
            "extracted_body_text": None,
            "raw_payload": message_resource.get('payload') # The raw payload for further inspection
        }

        payload = message_resource.get('payload')
        if payload:
            headers = payload.get('headers', [])
            parsed_headers: Dict[str, Any] = {}
            for header in headers:
                name = header.get('name', '').lower()
                value = header.get('value')
                if name:
                    if name in parsed_headers:
                        if isinstance(parsed_headers[name], list):
                            parsed_headers[name].append(value)
                        else:
                            parsed_headers[name] = [parsed_headers[name], value]
                    else:
                        parsed_headers[name] = value
            
            email_data['headers_parsed']['subject'] = parsed_headers.get('subject')
            email_data['headers_parsed']['from'] = parsed_headers.get('from')
            email_data['headers_parsed']['to'] = parsed_headers.get('to')
            email_data['headers_parsed']['cc'] = parsed_headers.get('cc')
            email_data['headers_parsed']['date'] = parsed_headers.get('date')
            email_data['headers_parsed']['message_id'] = parsed_headers.get('message-id')
            email_data['all_headers'] = parsed_headers

            email_data['extracted_body_text'] = extract_email_body(payload)
        
        return email_data
        
    except HttpError as error:
        print(f"Error fetching message details for ID {msg_id}: {error}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred fetching message {msg_id}: {e}")
        return None

def query_gmail_emails_structured(
    query: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
    max_results: int = 10
) -> Dict[str, List[Dict[str, Optional[str]]]]:
    """
    Queries Gmail for emails and returns them as a dict with key 'emails' and a list of dicts with fields: subject, from, to, body, date.

    Args:
        query (str): The Gmail search query string (e.g., 'Apple 99').
        after (str, optional): Start date in 'YYYY/MM/DD' format.
        before (str, optional): End date in 'YYYY/MM/DD' format.
        max_results (int): Maximum number of emails to return.

    Returns:
        Dict[str, List[Dict[str, Optional[str]]]]: A dict with key 'emails' and a list of dicts, each with keys: subject, from, to, body, date.
    """
    service = get_gmail_service()
    if not service:
        print("Failed to get Gmail service. Aborting query.")
        return {"emails": []}

    search_query = query
    if after:
        search_query += f" after:{after}"
    if before:
        search_query += f" before:{before}"
    
    user_id = 'me'
    emails_list: List[Dict[str, Optional[str]]] = []

    try:
        response = service.users().messages().list(
            userId=user_id,
            q=search_query,
            maxResults=max_results
        ).execute()
        
        message_refs = response.get('messages', [])
        
        if not message_refs:
            print("No emails found matching the query.")
            return {"emails": []}

        for msg_ref in message_refs:
            msg_id = msg_ref['id']
            email_details = get_email_details_structured(service, user_id, msg_id)
            if email_details:
                headers = email_details.get('headers_parsed', {})
                emails_list.append({
                    'subject': headers.get('subject'),
                    'from': headers.get('from'),
                    'to': headers.get('to'),
                    'body': email_details.get('extracted_body_text'),
                    'date': headers.get('date'),
                })
                
    except HttpError as error:
        print(f"An API error occurred during Gmail query: {error}")
        return {"emails": []}
    except Exception as e:
        print(f"An unexpected error occurred during Gmail query: {e}")
        return {"emails": []}

    return {"emails": emails_list}

if __name__ == "__main__":
    print("Gmail Query Tool - Clean Text Output")
    print("------------------------------------")

    # Ensure 'credentials/client_secret.json' exists.
    # First run will open a browser for authentication.
    
    # Adjust query, dates, and max_results as needed for your testing
    search_term = "Morgonrapport" # Example search term
    start_date = "2025/05/13"  # Adjust to a relevant past date
    end_date = "2025/05/15"    # Adjust to a relevant past date or today
    num_emails_to_fetch = 2

    print(f"\nQuerying for emails containing '{search_term}' between {start_date} and {end_date} (max {num_emails_to_fetch} results)...")
    
    # Assuming query_gmail_emails_structured is defined as in the previous refactoring
    retrieved_emails = query_gmail_emails_structured(
        query=search_term,
        after=start_date,
        before=end_date,
        max_results=num_emails_to_fetch
    )

    if retrieved_emails:
        print(f"\n--- Displaying Retrieved Emails ({len(retrieved_emails['emails'])}) ---")
        for i, email_detail_dict in enumerate(retrieved_emails['emails']):
            print(f"\n#################### Email #{i+1} ####################")
            formatted_email_string = format_email_for_display(email_detail_dict)
            print(formatted_email_string)
            print("################## End of Email ##################\n")
    else:
        print("\nNo emails were retrieved, or an error occurred during the process.")

    print("\n--- Script Finished ---")
    print("This is the new version")
    print(retrieved_emails)