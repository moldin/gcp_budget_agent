import logging
from google.oauth2.credentials import Credentials

from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build, Resource
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Ensure necessary imports for ADK Tool Context and Google libraries
from google.adk.tools import ToolContext
from googleapiclient.errors import HttpError

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
    """Internal function to get a single message."""
    try:
        return service.users().messages().get(userId=user_id, id=msg_id, format='metadata', metadataHeaders=['subject']).execute() # Fetch only snippet and subject
    except HttpError as error:
        logger.error(f"An API error occurred getting message {msg_id}: {error}")
        return None # Return None on error

# --- ADK Tool Definition ---
def search_gmail_for_transactions(query: str, max_results: int = 5) -> str:
    """
    Searches the user's Gmail inbox for transaction-related emails based on a provided query string
    and returns a summary of the found emails (Subject and Snippet).

    Args:
        query (str): The Gmail search query string. Use standard Gmail search operators.
                     Examples:
                     - 'Swish "150" after:2024/04/20 before:2024/04/25' (Finds Swish AND 150 between dates)
                     - '"Apple Store" OR "App Store" 99 after:2024/01/01' (Finds (Apple Store OR App Store) AND 99 since start of year)
                     - 'subject:(Your Uber receipt) after:2024/04/28' (Finds emails with specific subject after date)
                     Make sure not to be too specific, e.g. instead of "K*BOKUS.COM" you could assume "bokus" is enough, or "ICA NARA JAR/25-03-19" could be just "ICA" etc.
                     Make sure to include date constraints (after:, before:) for efficiency.
        max_results (int): The maximum number of emails to fetch details for (default: 5).

    Returns:
        str: A summary string listing the subject and snippet of found emails,
             or a message indicating no emails were found or an error occurred.
    """
    logger.info(f"Tool 'search_gmail_for_transactions' called with query: '{query}', max_results: {max_results}")
    user_id = USER_EMAIL_TO_IMPERSONATE # Always use the impersonated user for service account

    try:
        service = _get_cached_gmail_service()
    except Exception as e:
        # If service init failed (e.g., file not found), return error message
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
            snippet = message_detail.get('snippet', '(No snippet)')
            subject = "(No Subject Header)"
            headers = message_detail.get('payload', {}).get('headers', [])
            for header in headers:
                if header.get('name', '').lower() == 'subject':
                    subject = header.get('value', '(Empty Subject)')
                    break
            results_summary.append(f"- Subject: {subject}\n  Snippet: {snippet}")
        else:
            # Logged error in _get_message_internal, skip adding to summary
            pass # Or add an error placeholder: results_summary.append(f"- Error fetching details for message ID: {msg_id}")

    if not results_summary:
         # This could happen if refs were found but fetching details failed for all
         return "Found email references, but could not retrieve details. Check logs."

    summary_str = f"Found {len(results_summary)} emails (out of {len(message_refs)} matching references):\n" + "\n".join(results_summary)
    logger.info("Returning email summary.")
    return summary_str