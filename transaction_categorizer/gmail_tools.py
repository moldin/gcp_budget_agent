import os.path
import base64
import re
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def authenticate_gmail():
    """Shows basic usage of the Gmail API.
    Handles authentication and returns the Gmail API service object.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}. Need to re-authenticate.")
                # Potentially delete token.json here if refresh fails persistently
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0) # This will open a browser tab for auth
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("gmail", "v1", credentials=creds)
        return service
    except HttpError as error:
        print(f"An error occurred building the service: {error}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during authentication: {e}")
        return None


def search_gmail_receipts(transaction_date_str, amount, merchant_name=None, search_window_days=3):
    """
    Searches Gmail for emails that might be receipts matching the criteria.

    Args:
        transaction_date_str (str): The date of the transaction (e.g., "YYYY-MM-DD").
        amount (float or str): The transaction amount.
        merchant_name (str, optional): The name of the merchant. Defaults to None.
        search_window_days (int, optional): Number of days before and after the
                                             transaction date to search. Defaults to 3.

    Returns:
        list: A list of dictionaries, each containing details of a potentially
              matching email (subject, date, from, snippet, id). Returns an empty
              list if no matches or an error occurs.
    """
    service = authenticate_gmail()
    if not service:
        print("Failed to authenticate or build Gmail service.")
        return []

    try:
        # --- 1. Prepare Search Parameters ---
        transaction_date = datetime.strptime(transaction_date_str, "%Y-%m-%d")
        start_date = transaction_date - timedelta(days=search_window_days)
        end_date = transaction_date + timedelta(days=search_window_days + 1) # +1 to include the end day

        # Format dates for Gmail query (YYYY/MM/DD)
        start_date_str_query = start_date.strftime("%Y/%m/%d")
        end_date_str_query = end_date.strftime("%Y/%m/%d")

        # Format amount for searching (tricky due to formatting variations)
        # Try searching for the amount with and without currency symbols potentially
        # Note: Searching for exact amounts in body text is unreliable via Gmail API query
        amount_str = str(amount) # Keep original formatting if it includes currency
        amount_num_str = re.sub(r'[^\d.]', '', amount_str) # Extract just numbers and dot

        # --- 2. Construct Search Query ---
        query_parts = []
        query_parts.append(f"after:{start_date_str_query} before:{end_date_str_query}")

        # Add keywords commonly found in receipts/invoices
        query_parts.append('subject:("order confirmation" OR "your receipt" OR "invoice" OR "payment confirmation" OR "order details" OR "booking confirmation") OR "receipt" OR "invoice" OR "order"')

        # Add merchant name if provided (search in subject or from)
        if merchant_name:
            # Escape special characters in merchant name for query if needed
            safe_merchant = merchant_name.replace('"', '\\"')
            query_parts.append(f'(subject:("{safe_merchant}") OR from:("{safe_merchant}"))')

        # *Optional & Less Reliable*: Try adding amount to query.
        # This might miss emails if formatting differs (e.g., $12.34 vs 12.34 USD)
        # Using just the number might be slightly better but could yield false positives.
        # Consider filtering based on amount *after* retrieving emails if this is too noisy.
        if amount_num_str:
             query_parts.append(f'("{amount_str}" OR "{amount_num_str}")') # Search for original or numeric string

        # Combine query parts
        query = " ".join(query_parts)
        print(f"Executing Gmail Search Query: {query}") # For debugging

        # --- 3. Execute Search ---
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=10) # Limit results
            .execute()
        )
        messages = results.get("messages", [])

        # --- 4. Process Results ---
        matching_emails = []
        if not messages:
            print("No messages found matching the criteria.")
            return []
        else:
            print(f"Found {len(messages)} potential messages. Fetching details...")
            for message_info in messages:
                msg_id = message_info["id"]
                # Get message details (metadata and snippet are usually enough)
                # Use format='metadata' and specify headers for efficiency
                # Add 'snippet' to get a preview
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="metadata", metadataHeaders=['Subject', 'Date', 'From'])
                    .execute()
                )

                headers = msg.get('payload', {}).get('headers', [])
                email_data = {'id': msg_id, 'snippet': msg.get('snippet', '')}
                for header in headers:
                    name = header.get('name')
                    value = header.get('value')
                    if name == 'Subject':
                        email_data['subject'] = value
                    elif name == 'Date':
                        email_data['date'] = value
                    elif name == 'From':
                        email_data['from'] = value

                # Basic check: Does the snippet seem relevant? (Optional refinement)
                # You could add checks here, e.g., if the amount string appears in the snippet
                snippet_lower = email_data['snippet'].lower()
                amount_match = amount_str in snippet_lower or amount_num_str in snippet_lower
                # You might want to refine this logic or make it optional
                # For now, return all found emails based on the query

                matching_emails.append(email_data)

            return matching_emails

    except HttpError as error:
        print(f"An API error occurred: {error}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []

# --- Example Usage (for testing outside ADK) ---
if __name__ == "__main__":
    # Ensure credentials.json is in the same directory
    # The first time you run this, it will open a browser for authentication
    # Replace with your actual test data
    test_date = "2025-05-01" # Use a date where you expect a receipt
    test_amount = "25.99"   # Use an amount from an expected receipt
    test_merchant = "Example Store" # Optional: Add merchant name

    print(f"Searching for receipts around {test_date} for amount {test_amount} from {test_merchant or 'any merchant'}...")
    found_emails = search_gmail_receipts(test_date, test_amount, test_merchant)

    if found_emails:
        print("\n--- Found Potential Matching Emails ---")
        for email in found_emails:
            print(f"  ID: {email.get('id')}")
            print(f"  From: {email.get('from')}")
            print(f"  Date: {email.get('date')}")
            print(f"  Subject: {email.get('subject')}")
            print(f"  Snippet: {email.get('snippet')}")
            print("-" * 10)
    else:
        print("\nNo matching emails found.")