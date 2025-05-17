from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from .prompt import ROOT_AGENT_INSTRUCTION
from .config import GEMINI_MODEL_ID
#from .tools import search_gmail_for_transactions as gmail_search_tool
#from .tools import gmail_search_tool
from google.adk.tools import VertexAiSearchTool
from .sub_agents.gmail_agent.agent import gmail_agent
from dotenv import load_dotenv
from .config import GEMINI_MODEL_ID

import os
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
# MAIL_DATASTORE_ID = os.getenv("MAIL_DATASTORE_ID")
# gmail_search_tool = VertexAiSearchTool(
#     data_store_id=f"{MAIL_DATASTORE_ID}"
# )

gmail_search_tool = AgentTool(agent=gmail_agent)


root_agent = Agent(
    name="transaction_categorizer",
    model=GEMINI_MODEL_ID,
    description="A helpful financial assistant that categorizes personal transactions into predefined categories for use in a budget spreadsheet. Can search Gmail for transaction details through 'gmail_search_tool'.",
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[gmail_search_tool],
)

