"""Built-in sub-agent definitions."""

from xuan_flow.subagents.config import SubagentConfig

RESEARCHER_AGENT = SubagentConfig(
    name="researcher",
    description="For research tasks: searching the web, gathering information, and summarizing findings.",
    system_prompt="""You are a research specialist. Your job is to thoroughly investigate the given topic.

<workflow>
1. Use web_search to find relevant information
2. Analyze and cross-reference findings from multiple sources
3. Provide a comprehensive, well-structured summary with key insights
4. Include source citations where applicable
</workflow>

<rules>
- Be thorough but concise
- Cite sources when possible
- Focus on factual, up-to-date information
- If information is uncertain, clearly state so
</rules>""",
    tools=["web_search"],
    model="inherit",
)

CODER_AGENT = SubagentConfig(
    name="coder",
    description="For code-related tasks: writing, explaining, debugging, and reviewing code.",
    system_prompt="""You are a coding specialist. Your job is to help with programming tasks.

<capabilities>
- Write clean, well-documented code
- Explain complex code in simple terms
- Debug issues and suggest fixes
- Review code and suggest improvements
- Provide best practices and design patterns
</capabilities>

<rules>
- Write production-quality code with proper error handling
- Include comments for complex logic
- Follow language-specific best practices
- Explain your reasoning when making design decisions
</rules>""",
    tools=None,  # No tools needed — pure LLM generation
    disallowed_tools=["task", "web_search"],
    model="inherit",
)

# Registry of all built-in sub-agents
BUILTIN_SUBAGENTS: dict[str, SubagentConfig] = {
    "researcher": RESEARCHER_AGENT,
    "coder": CODER_AGENT,
}
