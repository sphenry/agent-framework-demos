from agent_framework import ChatAgent, MCPStreamableHTTPTool, HostedMCPTool
from agent_framework.openai import OpenAIChatClient
from agent_framework.devui import serve
import asyncio

mslearn_mcp = HostedMCPTool(  
    name="Microsoft Learn MCP",
    url="https://learn.microsoft.com/api/mcp",
    approval_mode="never_require",

)

# Create your agent
agent = ChatAgent(
    name="02 - Microsoft Learn MCP",
    instructions="You are a helpful assistant that can help with microsoft documentation questions.",
    chat_client=OpenAIChatClient(),
    tools=[mslearn_mcp],
)

async def main():
    response = await agent.run("How to create an Azure storage account using az cli?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())