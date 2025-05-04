from google.adk.agents import Agent
from .prompt import ROOT_AGENT_INSTRUCTION
from .config import GEMINI_MODEL_ID
from .tools import search_gmail_for_transactions


root_agent = Agent(
    name="gmail_agent",
    model=GEMINI_MODEL_ID,
    description="A helpful financial assistant that searches for emails related to personal financial transactions.",
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[search_gmail_for_transactions],
)

