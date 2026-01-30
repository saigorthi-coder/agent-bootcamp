from utils.observability import init_observability

# Initialize Langfuse + tracing once at startup
init_observability(service_name="bq_chatbot_mvp")
from utils.env import load_env

load_env()

# rest of imports AFTER env is loaded
from orchestrator.orchestrator_agent import OrchestratorAgent
