from dotenv import load_dotenv
import os


def load_env() -> None:
    load_dotenv(override=False)

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Check your .env file."
        )
