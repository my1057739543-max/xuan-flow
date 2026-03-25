"""Quick verification of all Module 1 components."""

print("=" * 50)
print("  Xuan-Flow Module 1 Verification")
print("=" * 50)

# 1. Config
from xuan_flow.config.app_config import get_app_config
config = get_app_config()
print(f"\n[1] Config: models={[m.name for m in config.models]}, memory={config.memory.enabled}")

# 2. Models
from xuan_flow.models.factory import create_chat_model
# Don't actually create (would need valid API key), just test import
print("[2] Models: factory import OK")

# 3. ThreadState
from xuan_flow.agents.thread_state import ThreadState
print(f"[3] ThreadState: fields={list(ThreadState.__annotations__.keys())}")

# 4. Tools
import asyncio
from xuan_flow.tools.registry import get_available_tools
tools_no_sub = asyncio.run(get_available_tools(subagent_enabled=False))
tools_with_sub = asyncio.run(get_available_tools(subagent_enabled=True))
print(f"[4] Tools: without_subagent={[t.name for t in tools_no_sub]}, with_subagent={[t.name for t in tools_with_sub]}")

# 5. SubAgents
from xuan_flow.subagents.registry import list_subagents, get_subagent_config
agents = list_subagents()
print(f"[5] SubAgents: {[a.name for a in agents]}")
researcher = get_subagent_config("researcher")
print(f"    researcher tools: {researcher.tools}")
coder = get_subagent_config("coder")
print(f"    coder disallowed: {coder.disallowed_tools}")

# 6. Memory
from xuan_flow.memory.store import get_memory_data, format_memory_for_injection
data = get_memory_data()
print(f"[6] Memory: facts={len(data.get('facts', []))}")
injection = format_memory_for_injection(data)
print(f"    injection: {'(empty)' if not injection else injection[:50]}")

# 7. Lead Agent import
from xuan_flow.agents.lead_agent import _build_system_prompt
prompt = _build_system_prompt(subagent_enabled=True)
print(f"[7] LeadAgent: prompt length={len(prompt)} chars")
assert "Xuan-Flow" in prompt
assert "subagent_system" in prompt

# 8. Memory middleware
from xuan_flow.agents.middlewares.memory_middleware import update_memory_background
print("[8] MemoryMiddleware: import OK")

print("\n" + "=" * 50)
print("  ✅ All Module 1 components verified!")
print("=" * 50)
