"""Entry point for LangGraph Agent Server / Studio (langgraph.json).

The server supplies the checkpointer and store itself, so none are passed here;
StoreBackend picks up the server's store at run time.
"""

from agent.agent import build_agent
from agent.tools import TOOLS

graph = build_agent(tools=TOOLS)
