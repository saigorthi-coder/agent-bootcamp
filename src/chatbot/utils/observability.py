"""
Central observability initialization.

This file wires:
- Langfuse
- OpenTelemetry (OTLP)
- OpenAI Agents SDK tracing

It must be imported ONCE at application startup.
"""
import os
from dotenv import load_dotenv
from utils.otlp_env_setup import set_up_langfuse_otlp_env_vars
from utils.oai_sdk_setup import setup_langfuse_tracer


def init_observability(service_name: str = "bq_chatbot_mvp") -> None:
    load_dotenv()
    """
    Initialize observability for the application.

    This function:
    1. Sets OTLP environment variables for Langfuse
    2. Registers Langfuse as the tracer for OpenAI Agents SDK

    Safe to call multiple times, but should be called once.
    """

    # 1. Configure OTLP exporter env vars (Langfuse)
    set_up_langfuse_otlp_env_vars()

    # 2. Register tracer with OpenAI Agents SDK
    setup_langfuse_tracer(service_name=service_name)
