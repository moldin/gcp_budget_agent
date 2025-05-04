from google.adk.agents import Agent
from transaction_categorizer.prompt import ROOT_AGENT_INSTRUCTION

from .config import GEMINI_MODEL_ID

root_agent = Agent(
    name="transaction_categorizer",
    model=GEMINI_MODEL_ID,
    description="A helpful financial assistant that categorizes personal transactions into predefined categories for use in a budget spreadsheet.",
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[],
)

