from orchestrator.contracts import (
    OrchestratorState,
    OrchestratorStep,
    UserQuery,
)

from agents.intent_planner_agent import run_intent_planner_agent
from agents.schema_agent import load_table_schema
from agents.sql_planner_agent import generate_sql
from agents.execution_agent import ExecutionAgent
from agents.post_processing_agent import post_process_results
from agents.visualization_agent import prepare_visualization


class OrchestratorAgent:
    """
    Central workflow controller.

    - Deterministic (no LLM usage here)
    - Owns OrchestratorState
    - Enforces step ordering
    - Routes execution based on planner output
    """

    def __init__(self, table_name: str):
        self.table_name = table_name
        self.execution_agent = ExecutionAgent()


    # -----------------------------
    # Public API
    # -----------------------------

    def run(self, user_input: str) -> OrchestratorState:
        """
        Run the full workflow for a single user query.
        """

        state = OrchestratorState(
            user_query=UserQuery(text=user_input),
            step=OrchestratorStep.RECEIVED_QUERY,
        )

        try:
            # 1. Load schema first (planner + SQL depend on it)
            self._run_schema_agent(state)

            # 2. Planner decides WHAT to do &  Intent agent extracts structured intent
            self._run_intent_planner_agent(state)

            # 3. SQL generation
            self._run_sql_planner(state)

            # 4. Execute SQL
            self._run_execution_agent(state)

            # 5. Post-process (row limits, formatting)
            self._run_post_processing_agent(state)

            # 6. Visualization (optional)
            self._run_visualization_agent(state)

            state.step = OrchestratorStep.COMPLETED
            return state

        except ValueError:
            # Expected control flow (clarification needed)
            return state

        except Exception as exc:
            # Unexpected failure
            state.step = OrchestratorStep.ERROR
            state.error_message = str(exc)
            return state

    # -----------------------------
    # Internal workflow steps
    # -----------------------------

    def _run_schema_agent(self, state: OrchestratorState) -> None:
        state.table_schema = load_table_schema(self.table_name)
        state.step = OrchestratorStep.SCHEMA_VALIDATED

    def _run_intent_planner_agent(self, state: OrchestratorState) -> None:
        plan, intent = run_intent_planner_agent(
            user_query=state.user_query.text,
            schema=state.table_schema,
        )

        state.execution_plan = plan
        state.parsed_intent = intent

        # Clarification handling
        if plan.needs_clarification or not plan.is_valid or not intent.is_valid:
            state.step = OrchestratorStep.NEEDS_CLARIFICATION
            state.error_message = (
                plan.clarification_question
                or intent.clarification_question
                or "Please clarify your request."
            )
            raise ValueError(state.error_message)

        state.step = OrchestratorStep.PLAN_CREATED
        # (optional) keep INTENT_PARSED step if you want:
        state.step = OrchestratorStep.INTENT_PARSED


    def _run_sql_planner(self, state: OrchestratorState) -> None:
        state.sql_query = generate_sql(
            intent=state.parsed_intent,
            schema=state.table_schema,
            table_name=self.table_name,
        )

        state.require(
            state.sql_query.is_safe,
            "Generated SQL is invalid or unsafe: " + "; ".join(state.sql_query.validation_errors),
        )

        state.step = OrchestratorStep.SQL_GENERATED

    def _run_execution_agent(self, state: OrchestratorState) -> None:
        state.query_result = self.execution_agent.execute(state.sql_query)
        state.step = OrchestratorStep.DATA_FETCHED

    def _run_post_processing_agent(self, state: OrchestratorState) -> None:
        state.query_result = post_process_results(
            result=state.query_result,
            output_format=state.parsed_intent.output_format,
        )
        state.step = OrchestratorStep.POST_PROCESSED

    def _run_visualization_agent(self, state: OrchestratorState) -> None:
        if state.parsed_intent.output_format.value == "plot":
            state.visualization_spec = prepare_visualization(
                intent=state.parsed_intent,
                result=state.query_result,
            )
            state.step = OrchestratorStep.VISUALIZED
