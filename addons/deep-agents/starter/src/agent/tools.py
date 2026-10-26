"""Example read-only tool. Replace with your product's tools.

The workspace comes from runtime context, never from model arguments, so the model can't
read another workspace's data. Permissions don't cover custom tools: keep them read-only in code.
"""

from __future__ import annotations

from langchain.tools import ToolRuntime, tool

from .agent import Ctx


@tool
def get_workspace_info(runtime: ToolRuntime[Ctx]) -> str:
    """Read-only. Return basic information about the current workspace."""
    return f"workspace: {runtime.context.workspace_id}"


TOOLS = [get_workspace_info]
