import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator

import agents
import gradio as gr
from dotenv import load_dotenv
from gradio.components.chatbot import ChatMessage
from langfuse import propagate_attributes

# ---- load .env from repo root ----
load_dotenv(dotenv_path=Path("/home/coder/agent-bootcamp") / ".env")

# ---- internal imports (same pattern as efficient_multiple_kbs.py) ----
from src.utils import (
    oai_agent_stream_to_gradio_messages,
    set_up_logging,
    setup_langfuse_tracer,
)
from src.utils.agent_session import get_or_create_session
from src.utils.client_manager import AsyncClientManager
from src.utils.gradio import COMMON_GRADIO_CONFIG
from src.utils.langfuse.shared_client import langfuse_client
from src.utils import CodeInterpreter

# ---- chatbot agents & tools ----
from bot_agents.orchestrator import build_orchestrator_agent
from bot_agents.sql_agent import build_sql_agent
#from bot_agents.viz_agent import build_visualization_agent
from tools.bigquery_tool import run_bigquery_query


# ============================================================
# Async Gradio entrypoint
# ============================================================

async def _main(
    query: str,
    history: list[ChatMessage],
    session_state: dict[str, Any],
) -> AsyncGenerator[list[ChatMessage], Any]:

    turn_messages: list[ChatMessage] = []

    # Maintain conversational session
    session = get_or_create_session(history, session_state)

    with (
        langfuse_client.start_as_current_observation(
            name="Clinical-AI-Agentic-Chatbot",
            as_type="agent",
            input=query,
        ) as obs,
        propagate_attributes(session_id=session.session_id),
    ):
        result_stream = agents.Runner.run_streamed(
            orchestrator_agent,
            input=query,
            session=session,
            max_turns=30,
        )

        async for event in result_stream.stream_events():
            turn_messages += oai_agent_stream_to_gradio_messages(event)
            if turn_messages:
                yield turn_messages

        obs.update(output=result_stream.final_output)


# ============================================================
# App bootstrap
# ============================================================

if __name__ == "__main__":

    # ---- logging & tracing ----
    set_up_logging()
    setup_langfuse_tracer()

    # ---- initialize shared client manager ----
    client_manager = AsyncClientManager()

    # ---- model selection ----
    planner_model = client_manager.configs.default_planner_model
    worker_model = client_manager.configs.default_worker_model

    # ---- SQL agent ----
    sql_agent = build_sql_agent(
        run_bigquery_query=run_bigquery_query,
        model=agents.OpenAIChatCompletionsModel(
            model=worker_model,
            openai_client=client_manager.openai_client,
        ),
    )

    # # ---- Visualization agent (Code Interpreter / E2B) ----
    #    visualization_agent = build_visualization_agent(
    #     code_interpreter=code_interpreter,
    #     model=agents.OpenAIChatCompletionsModel(
    #         model=worker_model,
    #         openai_client=client_manager.openai_client,
    #     ),
    # )

    # ---- Orchestrator agent ----
    orchestrator_agent = build_orchestrator_agent(
        sql_agent=sql_agent,
        code_interpreter=CodeInterpreter(),
        #visualization_agent=visualization_agent,
        model=agents.OpenAIChatCompletionsModel(
            model=planner_model,
            openai_client=client_manager.openai_client,
        ),
    )

    # ========================================================
    # Gradio UI (logos on both extremes)
    # ========================================================

    with gr.Blocks(title="Agentic BigQuery Chatbot") as demo:
        with gr.Row():
            with gr.Column(scale=1):
                gr.Image(
                    value="assets/Shoppers-Drug-Mart-Logo-Vector-Image.jpg",
                    show_label=False,
                    height=60,
                )

            with gr.Column(scale=3):
                gr.Markdown(
                    """
                    <div style="text-align: center;">
                        <h2>Agentic BigQuery Chatbot</h2>
                        <p style="margin-top: -10px;">
                            Query • Analyze • Visualize
                        </p>
                    </div>
                    """
                )

            with gr.Column(scale=1):
                gr.Image(
                    value="assets/loblaw logo.jpg",
                    show_label=False,
                    height=60,
                )

        # ---- Chat UI ----
        gr.ChatInterface(
            _main,
            **COMMON_GRADIO_CONFIG,
            examples=[
            ["How many records are in the table?"],
            ["Show the average age by sex"],
            ["Plot the number of records by region"],
            ['How many records have hba1c greater than 6.5']
        ],
        )

    try:
        demo.launch(share=True)
    finally:
        asyncio.run(client_manager.close())
