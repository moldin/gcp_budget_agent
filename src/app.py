import os
import sys

import vertexai
from absl import app, flags
from dotenv import load_dotenv
from vertexai import agent_engines
from vertexai.preview import reasoning_engines

from transaction_categorizer.agent import root_agent

load_dotenv()

def create_session(resource_id: str, user_id: str) -> None:
    """Creates a new session for the specified user."""
    remote_app = agent_engines.get(resource_id)
    remote_session = remote_app.create_session(user_id=user_id)
    session_id = remote_session['id']
    print("Created session:")
    print(f"  Session ID: {remote_session['id']}")
    print(f"  User ID: {remote_session['user_id']}")
    print(f"  App name: {remote_session['app_name']}")
    print(f"  Last update time: {remote_session['last_update_time']}")
    print("\nUse this session ID with --session_id when sending messages.")
    return session_id

def list_sessions(resource_id: str, user_id: str) -> None:
    """Lists all sessions for the specified user."""
    remote_app = agent_engines.get(resource_id)
    sessions = remote_app.list_sessions(user_id=user_id)
    # --- DEBUG PRINTS ---
    print(f"DEBUG: Type of sessions: {type(sessions)}")
    print(f"DEBUG: Value of sessions: {sessions}")
    # --- END DEBUG PRINTS ---
    print(f"Sessions for user '{user_id}':")
    if not sessions:
        print("  No sessions found.")
        return
    for session_resource_name in sessions:
        # list_sessions likely returns a list of resource names (strings)
        print(f"- {session_resource_name}")


def get_session(resource_id: str, user_id: str, session_id: str) -> None:
    """Gets a specific session."""
    remote_app = agent_engines.get(resource_id)
    session = remote_app.get_session(user_id=user_id, session_id=session_id)
    print("Session details:")
    print(f"  ID: {session['id']}")
    print(f"  User ID: {session['user_id']}")
    print(f"  App name: {session['app_name']}")
    print(f"  Last update time: {session['last_update_time']}")

def send_message(resource_id: str, user_id: str, session_id: str, message: str) -> None:
    """Sends a message to the deployed agent."""
    remote_app = agent_engines.get(resource_id)

    print(f"Sending message to session {session_id}:")
    print(f"Message: {message}")
    print("\nResponse:")
    events = []
    for event in remote_app.stream_query(
        user_id=user_id,
        session_id=session_id,
        message=message,
    ):
        events.append(event)
    return events


if __name__ == "__main__":
    
    message = "Hello, how are you?"
    resource_id = "projects/81141175628/locations/us-central1/reasoningEngines/8239977633064943616"
    user_id = "test_user"
    session_id = create_session(resource_id, user_id)

    message = " Categorize this: 2025-03-19    5484689546      BARBER & BOO/25-03-18   -964,00 22 100,62"
    message = "Catagorize this: 2025-03-11	5484654361	EASYPARK    /25-03-11	-34,50	23 035,62"
    events = send_message(resource_id, user_id, session_id, message)
    print(events)

