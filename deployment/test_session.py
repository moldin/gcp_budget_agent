import os
import sys

import vertexai
from absl import app, flags
from dotenv import load_dotenv
from vertexai import agent_engines
from vertexai.preview import reasoning_engines


load_dotenv()

def create_session(resource_id: str, user_id: str) -> None:
    """Creates a new session for the specified user."""
    remote_app = vertexai.agent_engines.get(resource_id)
    remote_session = remote_app.create_session(user_id=user_id)
    print("Created session:")
    print(f"  Session ID: {remote_session['id']}")
    print(f"  User ID: {remote_session['user_id']}")
    print(f"  App name: {remote_session['app_name']}")
    print(f"  Last update time: {remote_session['last_update_time']}")
    print("\nUse this session ID with --session_id when sending messages.")
    return remote_session['id']



if __name__ == "__main__":
    
    resource_id = "projects/81141175628/locations/europe-west1/reasoningEngines/6287517661018456064"
    user_id = "test_user"
    session_id = create_session(resource_id, user_id)
    


#Created session:
#  Session ID: 8219962673148723200
#  User ID: test_user
#  App name: 8239977633064943616
#  Last update time: 1746342599.463633