"""Prompt templates for memory extraction."""

MEMORY_UPDATE_PROMPT = """You are a memory management system. Analyze the following conversation and extract important facts about the user.

Current memory:
{current_memory}

New conversation:
{conversation}

Based on this conversation, output a JSON object with:
1. "newFacts": array of new facts to add. Each fact has:
   - "content": the fact (string)
   - "category": one of "preference", "knowledge", "context", "behavior", "goal"
   - "confidence": 0.0 to 1.0 (how confident you are)
2. "factsToRemove": array of fact IDs that are now outdated or incorrect

Rules:
- Only extract genuinely useful, long-term facts about the user
- DO NOT extract transient information (e.g., "user asked about X")
- Focus on preferences, skills, goals, context that would be useful in future conversations
- Set confidence based on how explicit/implicit the information is
- If the conversation doesn't contain useful new facts, return empty arrays

Output ONLY valid JSON, no markdown:"""


def format_conversation_for_update(messages) -> str:
    """Format LangChain messages into readable text for the LLM."""
    lines = []
    for msg in messages:
        role = type(msg).__name__.replace("Message", "")
        content = msg.content if hasattr(msg, "content") else str(msg)
        if isinstance(content, str) and content.strip():
            lines.append(f"{role}: {content}")
    return "\n".join(lines)
