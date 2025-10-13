# Copyright (c) Microsoft. All rights reserved.

import asyncio
import logging

from agent_framework import (
    ChatAgent,
    HostedCodeInterpreterTool,
    MagenticAgentDeltaEvent,
    MagenticAgentMessageEvent,
    MagenticBuilder,
    MagenticCallbackEvent,
    MagenticCallbackMode,
    MagenticFinalResultEvent,
    MagenticOrchestratorMessageEvent,
    WorkflowOutputEvent,
)
from agent_framework.openai import OpenAIChatClient, OpenAIResponsesClient

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ANSI color codes for terminal output (works on Linux/macOS terminals)
ORCH_COLOR = "\033[95m"  # bright magenta
RESET_COLOR = "\033[0m"

# State used by on_agent_stream callback
last_stream_agent_id: str | None = None
stream_line_open: bool = False

"""
Sample: Magentic Orchestration (multi-agent)

What it does:
- Orchestrates multiple agents using `MagenticBuilder` with streaming callbacks.

- ResearcherAgent (ChatAgent backed by an OpenAI chat client) for
    finding information.
- CoderAgent (ChatAgent backed by OpenAI Assistants with the hosted
    code interpreter tool) for analysis and computation.

The workflow is configured with:
- A Standard Magentic manager (uses a chat client for planning and progress).
- Callbacks for final results, per-message agent responses, and streaming
    token updates.

When run, the script builds the workflow, submits a task about estimating the
energy efficiency and CO2 emissions of several ML models, streams intermediate
events, and prints the final answer. The workflow completes when idle.

Prerequisites:
- OpenAI credentials configured for `OpenAIChatClient` and `OpenAIResponsesClient`.
"""

researcher_agent = ChatAgent(
    name="ResearcherAgent",
    description="Specialist in research and information gathering",
    instructions=(
        "You are a Researcher. You find information without additional computation or quantitative analysis."
    ),
    # This agent requires the gpt-4o-search-preview model to perform web searches.
    # Feel free to explore with other agents that support web search, for example,
    # the `OpenAIResponseAgent` or `AzureAgentProtocol` with bing grounding.
    chat_client=OpenAIChatClient(model_id="gpt-4o-search-preview"),
)

coder_agent = ChatAgent(
    name="CoderAgent",
    description="A helpful assistant that writes and executes code to process and analyze data.",
    instructions="You solve questions using code. Please provide detailed analysis and computation process.",
    chat_client=OpenAIResponsesClient(),
    tools=HostedCodeInterpreterTool(),
)

# Unified callback
async def on_event(event: MagenticCallbackEvent) -> None:
    """
    The `on_event` callback processes events emitted by the workflow.
    Events include: orchestrator messages, agent delta updates, agent messages, and final result events.
    """
    global last_stream_agent_id, stream_line_open
    if isinstance(event, MagenticOrchestratorMessageEvent):
        # Color the orchestrator messages for easier scanning in terminal
        print(
            f"\n{ORCH_COLOR}[ORCH:{event.kind}]{RESET_COLOR}\n\n{getattr(event.message, 'text', '')}\n{'-' * 26}"
        )
    elif isinstance(event, MagenticAgentDeltaEvent):
        if last_stream_agent_id != event.agent_id or not stream_line_open:
            if stream_line_open:
                print()
            print(f"\n{ORCH_COLOR}[STREAM:{event.agent_id}]: {RESET_COLOR}", end="", flush=True)
            last_stream_agent_id = event.agent_id
            stream_line_open = True
        print(event.text, end="", flush=True)
    # elif isinstance(event, MagenticAgentMessageEvent):
    #     if stream_line_open:
    #         print(" (final)")
    #         stream_line_open = False
    #         print()
    #     msg = event.message
    #     if msg is not None:
    #         response_text = (msg.text or "").replace("\n", " ")
    #         print(f"\n{ORCH_COLOR}[AGENT:{event.agent_id}] {RESET_COLOR}{msg.role.value}\n\n{response_text}\n{'-' * 26}")
    elif isinstance(event, MagenticFinalResultEvent):
        print("\n" + "=" * 50)
        print(f"{ORCH_COLOR}FINAL RESULT:{RESET_COLOR}")
        print("=" * 50)
        if event.message is not None:
            print(event.message.text)
        print("=" * 50)

workflow = (
    MagenticBuilder()
    .participants(researcher=researcher_agent, coder=coder_agent)
    .on_event(on_event, mode=MagenticCallbackMode.STREAMING)
    .with_standard_manager(
        chat_client=OpenAIChatClient(),
        max_round_count=10,
        max_stall_count=3,
        max_reset_count=2,
    )
    .build()
)

async def main() -> None:

    print("\nBuilding Magentic Workflow...")

    task = (
        "I am preparing a report on the energy efficiency of different machine learning model architectures. "
        "Compare the estimated training and inference energy consumption of ResNet-50, BERT-base, and GPT-2 "
        "on standard datasets (e.g., ImageNet for ResNet, GLUE for BERT, WebText for GPT-2). "
        "Then, estimate the CO2 emissions associated with each, assuming training on an Azure Standard_NC6s_v3 "
        "VM for 24 hours. Provide tables for clarity, and recommend the most energy-efficient model "
        "per task type (image classification, text classification, and text generation)."
    )

    print(f"\nTask: {task}")
    print("\nStarting workflow execution...")

    try:
        output: str | None = None
        async for event in workflow.run_stream(task):
            print(event)
            if isinstance(event, WorkflowOutputEvent):
                output = str(event.data.text)

        if output is not None:
            report_path = "report.md"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Wrote workflow output to {report_path}")

    except Exception as e:
        print(f"Workflow execution failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())