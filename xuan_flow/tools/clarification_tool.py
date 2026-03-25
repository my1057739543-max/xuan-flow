from typing import Literal

from langchain_core.tools import tool


@tool("ask_clarification", parse_docstring=True)
def ask_clarification(
    question: str,
    clarification_type: Literal[
        "missing_info",
        "ambiguous_requirement",
        "approach_choice",
        "risk_confirmation",
        "suggestion",
    ],
    context: str | None = None,
    options: list[str] | None = None,
) -> str:
    """Ask the user for clarification when you need more information to proceed.

    Use this tool when you encounter situations where you cannot proceed without user input.
    Execution will halt and yield this question up to the user. Wait for their response.

    Args:
        question: The clarification question to ask the user. Be specific and clear.
        clarification_type: The type of clarification needed.
        context: Optional context explaining why clarification is needed. 
        options: Optional list of choices for the user.
    """
    # In Xuan-Flow, we simply return a message. 
    # The LeadAgent's node logic or system prompt should handle the 'wait' behavior.
    msg = f"Clarification Requested: {question}\nReason: {clarification_type}"
    if options:
        msg += f"\nOptions: {', '.join(options)}"
        
    return msg
