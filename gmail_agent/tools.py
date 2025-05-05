import logging
from google.oauth2.credentials import Credentials

from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build, Resource
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Ensure necessary imports for ADK Tool Context and Google libraries
from google.adk.tools import ToolContext
from googleapiclient.errors import HttpError

import base64
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
SERVICE_ACCOUNT_FILE = 'credentials/aspiro-budget-analysis-7ad00ed2ffef.json'
USER_EMAIL_TO_IMPERSONATE = 'mats@oldin.se'

# --- Cached Gmail Service ---
_gmail_service_cache: Optional[Resource] = None

def _get_cached_gmail_service() -> Resource:
    """Initializes and caches the Gmail service object using Service Account."""
    global _gmail_service_cache
    if _gmail_service_cache is None:
        try:
            logger.info("Initializing Gmail service for the first time...")
            creds = ServiceAccountCredentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE,
                scopes=SCOPES,
                subject=USER_EMAIL_TO_IMPERSONATE
            )
            _gmail_service_cache = build('gmail', 'v1', credentials=creds, cache_discovery=False)
            logger.info("Gmail service initialized successfully.")
        except FileNotFoundError:
            logger.error(f"Service account key file not found at: {SERVICE_ACCOUNT_FILE}")
            raise # Re-raise the error to prevent tool execution without credentials
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {e}")
            raise # Re-raise other unexpected errors
    return _gmail_service_cache

# --- Low-level API Calls (kept internal) ---
def _search_messages_internal(service: Resource, user_id: str, q: str) -> List[Dict]:
    """Internal function to search messages."""
    try:
        response = service.users().messages().list(userId=user_id, q=q).execute()
        return response.get('messages', [])
    except HttpError as error:
        logger.error(f"An API error occurred during message search: {error}")
        return [] # Return empty list on error

def _get_message_internal(service: Resource, user_id: str, msg_id: str) -> Optional[Dict]:
    """Internal function to get a single message (full content)."""
    try:
        # Request full format to get body content
        return service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()
    except HttpError as error:
        logger.error(f"An API error occurred getting message {msg_id}: {error}")
        return None # Return None on error

# --- Helper Function for Body Parsing ---
def _extract_body_from_payload(payload: Dict) -> str:
    """Extracts text body from Gmail message payload, prioritizing plain text."""
    body = "(Could not extract body)"
    if 'parts' in payload:
        # Handle multipart messages (common)
        plain_text_part = None
        html_part = None
        for part in payload['parts']:
            mime_type = part.get('mimeType')
            if mime_type == 'text/plain':
                plain_text_part = part
                break # Prioritize plain text
            elif mime_type == 'text/html':
                html_part = part
            elif mime_type.startswith('multipart/'):
                 # Recursive call for nested multipart
                 nested_body = _extract_body_from_payload(part)
                 if nested_body != "(Could not extract body)":
                     return nested_body # Return first found body from nested parts

        target_part = plain_text_part if plain_text_part else html_part

        if target_part and 'body' in target_part and 'data' in target_part['body']:
            try:
                data = target_part['body']['data']
                byte_data = base64.urlsafe_b64decode(data)
                body = byte_data.decode('utf-8') # Assuming UTF-8
                # Optional: Basic HTML stripping if it was HTML
                if target_part.get('mimeType') == 'text/html':
                     # Very basic tag removal, consider a library for robustness
                     body = re.sub('<[^>]+>', '', body)
                     body = re.sub(r'\s+', ' ', body).strip() # Clean up whitespace
            except Exception as e:
                logger.warning(f"Failed to decode/parse message part body: {e}")
                body = "(Error decoding body)"

    elif 'body' in payload and 'data' in payload['body']:
        # Handle single-part messages
        try:
            data = payload['body']['data']
            byte_data = base64.urlsafe_b64decode(data)
            body = byte_data.decode('utf-8')
            if payload.get('mimeType') == 'text/html':
                 body = re.sub('<[^>]+>', '', body)
                 body = re.sub(r'\s+', ' ', body).strip()
        except Exception as e:
            logger.warning(f"Failed to decode/parse single-part message body: {e}")
            body = "(Error decoding body)"

    return body

# --- ADK Tool Definition ---
def search_gmail_for_transactions(query: str, max_results: int = 5) -> str:
    """
    Searches the user's Gmail inbox for transaction-related emails using a specific query.
    This tool is essential for gathering context (like merchant name, item details) from email
    receipts or notifications to accurately categorize financial transactions and generate
    informative summaries. It retrieves the FULL BODY content of the emails.

    Args:
        query (str): The Gmail search query string. MUST follow standard Gmail search operators.
                     It is CRUCIAL to include:
                     1. Relevant keywords (e.g., "Amazon", "Swish", "ICA"). Generalize from raw data
                        (e.g., "ICA NARA..." -> "ICA").
                     2. Date constraints (`after:YYYY/MM/DD before:YYYY/MM/DD`) spanning a few days
                        around the transaction date for relevance and efficiency.
                     3. Optionally, the transaction amount (e.g., `"123.45"` in quotes) to narrow results.
                     Examples:
                     - '"Spotify AB" "109" after:2024/04/20 before:2024/04/25'
                     - 'subject:(Your Uber receipt) after:2024/04/28 before:2024/05/02'
                     - 'Klarna OR Paypal "Order confirmation" after:2025/01/15 before:2025/01/20'
        max_results (int): The maximum number of email details (Subject/Body) to retrieve and return (default: 5).

    Returns:
        str:
            - If emails are found: A multi-line string summarizing the top `max_results` emails,
              formatted as:\n- Subject: [Email Subject]\n  Body: [Extracted Email Body Text]\n(repeated for each email)
            - If no emails are found matching the query: The specific string "No emails found matching the query."
            - If an error occurs during Gmail API interaction: An error message string (e.g., "Error: Could not initialize Gmail service...").
    """
    logger.info(f"Tool 'search_gmail_for_transactions' called with query: '{query}', max_results: {max_results}")
    user_id = USER_EMAIL_TO_IMPERSONATE # Always use the impersonated user for service account

    try:
        service = _get_cached_gmail_service()
    except Exception as e:
        return f"Error: Could not initialize Gmail service. Check logs. Details: {e}"

    logger.info(f"Searching Gmail for user '{user_id}' with query: {query}")
    message_refs = _search_messages_internal(service, user_id, query)

    if not message_refs:
        logger.info("No messages found matching the query.")
        return "No emails found matching the query."

    results_summary = []
    fetch_count = 0
    logger.info(f"Found {len(message_refs)} references. Fetching details for up to {max_results}...")

    for msg_ref in message_refs:
        if fetch_count >= max_results:
            logger.info(f"Reached max_results limit ({max_results}).")
            break

        msg_id = msg_ref['id']
        message_detail = _get_message_internal(service, user_id, msg_id)

        if message_detail:
            fetch_count += 1
            snippet = message_detail.get('snippet', '(No snippet)') # Keep snippet as fallback info if needed?
            subject = "(No Subject Header)"
            payload = message_detail.get('payload', {})
            headers = payload.get('headers', [])
            for header in headers:
                if header.get('name', '').lower() == 'subject':
                    subject = header.get('value', '(Empty Subject)')
                    break

            # Extract body using the helper function
            body_text = _extract_body_from_payload(payload)
            # Limit body length for the summary to avoid overly long outputs
            max_body_length = 1000
            truncated_body = body_text[:max_body_length] + ("..." if len(body_text) > max_body_length else "")

            results_summary.append(f"- Subject: {subject}\n  Body: {truncated_body}") # Use body instead of snippet
        else:
            pass # Error already logged

    if not results_summary:
         return "Found email references, but could not retrieve details. Check logs."

    summary_str = f"Found {len(results_summary)} emails (out of {len(message_refs)} matching references):\n" + "\n".join(results_summary)
    logger.info("Returning email summary.")
    return summary_str