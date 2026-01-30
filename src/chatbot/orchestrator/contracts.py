from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# -----------------------------
# Enumerations (system control)
# -----------------------------

class OutputFormat(str, Enum):
    VALUE = "value"
    TABLE = "table"
    PLOT = "plot"
    UNKNOWN = "unknown"


class OrchestratorStep(str, Enum):
    RECEIVED_QUERY = "received_query"
    PLAN_CREATED = "plan_created"
    INTENT_PARSED = "intent_parsed"
    SCHEMA_VALIDATED = "schema_validated"
    SQL_GENERATED = "sql_generated"
    DATA_FETCHED = "data_fetched"
    POST_PROCESSED = "post_processed"
    VISUALIZED = "visualized"
    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    ERROR = "error"


# -----------------------------
# Core Data Contracts
# -----------------------------

@dataclass
class UserQuery:
    """Raw user input."""
    text: str


@dataclass
class ParsedIntent:
    """
    Structured representation of user intent.

    This MUST be produced by the Intent Agent.
    """
    metrics: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    group_by: Optional[str] = None
    output_format: OutputFormat = OutputFormat.UNKNOWN
    requires_aggregation: bool = False
    is_valid: bool = False
    clarification_question: Optional[str] = None

@dataclass
class ExecutionPlan:
    """
    Planner agent output.
    Describes WHAT should be done, not HOW.
    """
    steps: List[str] = field(default_factory=list)
    output_format: OutputFormat = OutputFormat.UNKNOWN
    chart_type: Optional[str] = None

    needs_clarification: bool = False
    clarification_question: Optional[str] = None

    is_valid: bool = False


@dataclass
class TableSchema:
    """
    Authoritative BigQuery table schema.

    No agent may assume columns outside this object.
    """
    table_name: str
    columns: Dict[str, str]  # column_name -> data_type


@dataclass
class SQLQuery:
    """
    Generated SQL statement.

    Must be validated against TableSchema before execution.
    """
    query: str
    is_safe: bool = False
    validation_errors: List[str] = field(default_factory=list)


@dataclass
class QueryResult:
    """
    Raw query result returned from BigQuery.
    """
    rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False


@dataclass
class VisualizationSpec:
    """
    Specification for visualization agent.
    """
    chart_type: Optional[str] = None
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    hue: Optional[str] = None
    title: Optional[str] = None


# -----------------------------
# Orchestrator State
# -----------------------------

@dataclass
class OrchestratorState:
    """
    Single source of truth for the entire workflow.
    """

    step: OrchestratorStep = OrchestratorStep.RECEIVED_QUERY

    user_query: Optional[UserQuery] = None
    parsed_intent: Optional[ParsedIntent] = None
    execution_plan: Optional[ExecutionPlan] = None
    table_schema: Optional[TableSchema] = None
    sql_query: Optional[SQLQuery] = None
    query_result: Optional[QueryResult] = None
    visualization_spec: Optional[VisualizationSpec] = None

    error_message: Optional[str] = None

    def require(self, condition: bool, message: str):
        """
        Guardrail helper.

        If condition fails, move to NEEDS_CLARIFICATION.
        """
        if not condition:
            self.step = OrchestratorStep.NEEDS_CLARIFICATION
            self.error_message = message
            raise ValueError(message)
