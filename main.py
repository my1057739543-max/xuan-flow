"""Xuan-Flow CLI entry point — interactive conversation with the Lead Agent.

This serves as a development/testing interface for Module 1.
Module 2 will add a FastAPI Gateway, and Module 3 will add a Web UI.
"""

import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

# Suppress noisy loggers
for name in ["httpx", "httpcore", "openai", "urllib3"]:
    logging.getLogger(name).setLevel(logging.WARNING)

logger = logging.getLogger("xuan-flow")


async def async_main():
    from langchain_core.messages import HumanMessage

    from xuan_flow.agents.lead_agent import make_lead_agent
    from xuan_flow.agents.middlewares.memory_middleware import update_memory_background

    print("=" * 60)
    print("  🌊 Xuan-Flow — Lightweight Multi-Agent Assistant")
    print("  Type 'quit' or 'exit' to stop.")
    print("=" * 60)
    print()

    # Create agent
    try:
        agent = await make_lead_agent()
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        print("   Make sure config.yaml is present and API keys are set in .env")
        sys.exit(1)

    messages = []

    while True:
        try:
            # Note: input() is blocking, which is fine for this simple CLI
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Bye!")
            break

        # Add user message
        messages.append(HumanMessage(content=user_input))

        # Invoke agent
        try:
            result = await agent.ainvoke(
                {"messages": messages},
                config={"recursion_limit": 50},
            )

            # Extract response
            response_messages = result.get("messages", [])
            if response_messages:
                last_msg = response_messages[-1]
                content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                if isinstance(content, list):
                    content = "\n".join(
                        block.get("text", str(block)) if isinstance(block, dict) else str(block)
                        for block in content
                    )
                print(f"\nAssistant: {content}\n")

                # Update messages history with full result
                messages = response_messages

                # Trigger background memory update
                update_memory_background(messages)
            else:
                print("\nAssistant: (no response)\n")

        except KeyboardInterrupt:
            print("\n(interrupted)")
            continue
        except Exception as e:
            logger.exception("Error during agent invocation")
            print(f"\n❌ Error: {e}\n")


def main():
    import asyncio
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
