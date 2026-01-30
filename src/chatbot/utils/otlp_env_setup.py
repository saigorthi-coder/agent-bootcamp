"""Set up environment variables for LangFuse integration."""

import base64
import logging
import os


def set_up_langfuse_otlp_env_vars() -> None:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST")

    if not all([public_key, secret_key, host]):
        raise RuntimeError(
            "Missing Langfuse environment variables. "
            "Check your .env file."
        )

    auth_header = base64.b64encode(
        f"{public_key}:{secret_key}".encode()
    ).decode()

    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = host.rstrip("/") + "/api/public/otel"
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth_header}"

    logging.info("Langfuse OTLP configured")
