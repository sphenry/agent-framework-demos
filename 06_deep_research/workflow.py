# Adapted from: https://cookbook.openai.com/examples/deep_research_api/introduction_to_deep_research_api_agents

from urllib import response
from agent_framework.devui import serve
from agent_framework import HostedWebSearchTool
from agent_framework.openai import OpenAIResponsesClient
from agent_framework import WorkflowBuilder, WorkflowContext, AgentRunEvent, executor, AgentExecutorResponse, Case, Default

import asyncio

import time
from collections.abc import Awaitable, Callable
from random import randint
from typing import Annotated, List
from pydantic import BaseModel


from agent_framework import (
    FunctionInvocationContext,AgentRunContext
)
from sympy import true

# ─────────────────────────────────────────────────────────────
#  Prompts
# ─────────────────────────────────────────────────────────────

CLARIFYING_AGENT_PROMPT =  """
    If the user hasn't specifically asked for research (unlikely), ask them what research they would like you to do.

        GUIDELINES:
        1. **Be concise while gathering all necessary information** Ask 2–3 clarifying questions to gather more context for research.
        - Make sure to gather all the information needed to carry out the research task in a concise, well-structured manner. Use bullet points or numbered lists if appropriate for clarity. Don't ask for unnecessary information, or information that the user has already provided.
        2. **Maintain a Friendly and Non-Condescending Tone**
        - For example, instead of saying “I need a bit more detail on Y,” say, “Could you share more detail on Y?”
        3. **Adhere to Safety Guidelines**
        """

RESEARCH_INSTRUCTION_AGENT_PROMPT = """

        Based on the following guidelines, take the users query, and rewrite it into detailed research instructions. OUTPUT ONLY THE RESEARCH INSTRUCTIONS, NOTHING ELSE. Transfer to the research agent.

        GUIDELINES:
        1. **Maximize Specificity and Detail**
        - Include all known user preferences and explicitly list key attributes or dimensions to consider.
        - It is of utmost importance that all details from the user are included in the expanded prompt.

        2. **Fill in Unstated But Necessary Dimensions as Open-Ended**
        - If certain attributes are essential for a meaningful output but the user has not provided them, explicitly state that they are open-ended or default to “no specific constraint.”

        3. **Avoid Unwarranted Assumptions**
        - If the user has not provided a particular detail, do not invent one.
        - Instead, state the lack of specification and guide the deep research model to treat it as flexible or accept all possible options.

        4. **Use the First Person**
        - Phrase the request from the perspective of the user.

        5. **Tables**
        - If you determine that including a table will help illustrate, organize, or enhance the information in your deep research output, you must explicitly request that the deep research model provide them.
        Examples:
        - Product Comparison (Consumer): When comparing different smartphone models, request a table listing each model’s features, price, and consumer ratings side-by-side.
        - Project Tracking (Work): When outlining project deliverables, create a table showing tasks, deadlines, responsible team members, and status updates.
        - Budget Planning (Consumer): When creating a personal or household budget, request a table detailing income sources, monthly expenses, and savings goals.
        Competitor Analysis (Work): When evaluating competitor products, request a table with key metrics—such as market share, pricing, and main differentiators.

        6. **Headers and Formatting**
        - You should include the expected output format in the prompt.
        - If the user is asking for content that would be best returned in a structured format (e.g. a report, plan, etc.), ask the Deep Research model to “Format as a report with the appropriate headers and formatting that ensures clarity and structure.”

        7. **Language**
        - If the user input is in a language other than English, tell the model to respond in this language, unless the user query explicitly asks for the response in a different language.

        8. **Sources**
        - If specific sources should be prioritized, specify them in the prompt.
        - Prioritize Internal Knowledge. Only retrieve a single file once.
        - For product and travel research, prefer linking directly to official or primary websites (e.g., official brand sites, manufacturer pages, or reputable e-commerce platforms like Amazon for user reviews) rather than aggregator sites or SEO-heavy blogs.
        - For academic or scientific queries, prefer linking directly to the original paper or official journal publication rather than survey papers or secondary summaries.
        - If the query is in a specific language, prioritize sources published in that language.

        IMPORTANT: Ensure that the complete payload to this function is valid JSON
        IMPORTANT: SPECIFY REQUIRED OUTPUT LANGUAGE IN THE PROMPT
        """

class Clarifications(BaseModel):
    questions: List[str]

class NeedClarifications(BaseModel):
    agent_response: Annotated[bool, "Does the user need to provide clarifications? true/false"]

chat_client = OpenAIResponsesClient()
async def security_agent_middleware(
    context: AgentRunContext,
    next: Callable[[AgentRunContext], Awaitable[None]],
) -> None:
    """Agent middleware that checks for security violations."""
    # Check for potential security violations in the query
    # For this example, we'll check the last user message
    last_message = context.messages[-1] if context.messages else None
    if last_message and last_message.text:
        query = last_message.text
        if "password" in query.lower() or "secret" in query.lower():
            print("[SecurityAgentMiddleware] Security Warning: Detected sensitive information, blocking request.")
            # Simply don't call next() to prevent execution
            return

    print("[SecurityAgentMiddleware] Security check passed.")
    await next(context)

async def logging_function_middleware(
    context: FunctionInvocationContext,
    next: Callable[[FunctionInvocationContext], Awaitable[None]],
) -> None:
    """Function middleware that logs function calls."""
    function_name = context.function.name
    print(f"[LoggingFunctionMiddleware] About to call function: {function_name}.")

    start_time = time.time()

    await next(context)

    end_time = time.time()
    duration = end_time - start_time

    print(f"[LoggingFunctionMiddleware] Function {function_name} completed in {duration:.5f}s.")

research_agent = OpenAIResponsesClient(
        model_id="o4-mini-deep-research-2025-06-26",
    ).create_agent(
    name="Research Agent",
    tools=[HostedWebSearchTool()], # TODO add local search tool
    middleware=[logging_function_middleware, security_agent_middleware],
    instructions="You perform deep empirical research based on the user's question."
)

instruction_agent  = OpenAIResponsesClient(
        model_id="gpt-4o-mini",
    ).create_agent(
    name="Research Instruction Agent",
    middleware=[logging_function_middleware, security_agent_middleware],
    instructions=RESEARCH_INSTRUCTION_AGENT_PROMPT
)

clarifying_agent  = OpenAIResponsesClient(
        model_id="gpt-4o-mini",
    ).create_agent(
    name="Clarification Agent",
    instructions=CLARIFYING_AGENT_PROMPT,
    middleware=[logging_function_middleware, security_agent_middleware],
    response_format=Clarifications,
)

triage_agent   = OpenAIResponsesClient(
        model_id="gpt-4o-mini",
    ).create_agent(
    name="Triage Agent",
    instructions=(
        "Decide whether clarifications are required.\n"
    ),
    middleware=[logging_function_middleware, security_agent_middleware],
    response_format=NeedClarifications,
    # response_format=bool, # TODO I'd like to be able to write this
)

workflow = (
    WorkflowBuilder()
    .set_start_executor(triage_agent)
    .add_switch_case_edge_group(
        triage_agent,
        [
            Case(condition=lambda x: NeedClarifications.model_validate_json(x.agent_run_response.messages[0].text).agent_response == true, target=clarifying_agent),
            # Case(condition=lambda x: x.agent_run_response.value.agent_response == true, target=clarifying_agent),
            Default(target=instruction_agent),
        ],
    )
    .add_edge(clarifying_agent, instruction_agent)
    .add_edge(instruction_agent, research_agent)
    .build()
)

async def main() -> None:
    input = "Research the economic impact of semaglutide on global healthcare systems."
    print("Input:", input)

    events = await workflow.run(input)
    print(events.get_outputs())
    print("Final state:", events.get_final_state())
    
    with open("af_results.md", "w", encoding="utf-8") as f:
        f.write(f"# Research: {input}\n\n")
        f.write(events[-1].data)

if __name__ == "__main__":
    asyncio.run(main())

# Launch debug UI - that's it!
#serve(entities=[workflow], auto_open=True)
# → Opens browser to http://localhost:8080