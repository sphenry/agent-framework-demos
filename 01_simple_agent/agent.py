from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient
from agent_framework.devui import serve
import asyncio

def get_weather(location: str) -> str:
    """Get weather for a location."""
    return f"Weather in {location}: 72°F and sunny"

# Create your agent
agent = ChatAgent(
    name="01 - Weather Agent",
    chat_client=OpenAIChatClient(),
    tools=[get_weather]
)

async def main():
    response = await agent.run("What's the weather in New York?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())