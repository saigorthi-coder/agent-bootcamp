import json
import os
import re
from typing import Any, Dict, List, Tuple

from openai import OpenAI

from orchestrator.contracts import (
    ExecutionPlan,
    OutputFormat,
    ParsedIntent,
    TableSchema,
)


# -----------------------------
# Client
# -----------------------------
def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Did you call load_env()?")

    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL"),  # optional
    )


# Choose model via env so you can swap if gateway doesn't support a name.
# You can keep gemini-2.5-pro as default if your endpoint supports it.
DEFAULT_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-pro")


# -----------------------------
# Robust JSON extraction
# -----------------------------
def _extract_first_json_object(text: str) -> Dict[str, Any]:
    """
    Extract the first JSON object from a text blob.
    Handles cases where the model wraps JSON in markdown or adds stray text.
    """
    if not text or not text.strip():
        raise ValueError("Empty model output")

    text = text.strip()

    # Common: ```json { ... } ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return json.loads(fenced.group(1))

    # Otherwise: find first {...} block
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start == -1 or brace_end == -1 or brace_end <= brace_start:
        raise ValueError(f"No JSON object found in model output: {text[:200]}")

    candidate = text[brace_start:brace_end + 1]
    return json.loads(candidate)


# -----------------------------
# Combined Agent
# -----------------------------
SYSTEM_PROMPT = """
You are an Intent+Planning Agent for an analytics chatbot over ONE BigQuery table.

You MUST return ONLY JSON (no markdown, no commentary).

You will produce:
1) plan: what steps are needed
2) intent: what data is requested

Rules:
- Use ONLY the provided column names (never invent columns).
- Do NOT generate SQL.
- If user intent is ambiguous, set needs_clarification=true and ask a clarification_question.
- If user asks for a plot, output_format must be "plot".
- For count/avg/sum/min/max questions, requires_aggregation must be true.
"""

def run_intent_planner_agent(
    user_query: str,
    schema: TableSchema,
) -> Tuple[ExecutionPlan, ParsedIntent]:
    """
    Single LLM call that returns both:
    - ExecutionPlan
    - ParsedIntent
    """
    client = _get_openai_client()

    available_columns = list(schema.columns.keys())

    user_prompt = f"""
User question:
{user_query}

Available columns (ONLY these may be referenced):
{available_columns}

Return JSON in EXACTLY this schema:

{{
  "needs_clarification": false,
  "clarification_question": null,

  "plan": {{
    "steps": ["aggregate", "group_by", "visualize"],
    "output_format": "value|table|plot",
    "chart_type": "bar|line|scatter|null"
  }},

  "intent": {{
    "metrics": ["column_name"],
    "filters": {{"column": "value"}},
    "group_by": "column_name or null",
    "output_format": "value|table|plot",
    "requires_aggregation": true|false
  }}
}}
"""

    resp = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )

    raw = (resp.choices[0].message.content or "").strip()
    data = _extract_first_json_object(raw)

    # Clarification gate
    needs_clarification = bool(data.get("needs_clarification", False))
    clarification_question = data.get("clarification_question")

    # Plan
    plan_data = data.get("plan", {}) or {}
    plan_output_format = plan_data.get("output_format", "unknown")
    plan = ExecutionPlan(
        steps=plan_data.get("steps", []),
        output_format=OutputFormat(plan_output_format) if plan_output_format in OutputFormat._value2member_map_ else OutputFormat.UNKNOWN,
        chart_type=plan_data.get("chart_type"),
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
        is_valid=not needs_clarification,
    )

    # Intent
    intent_data = data.get("intent", {}) or {}
    intent_output_format = intent_data.get("output_format", "unknown")
    intent = ParsedIntent(
        metrics=intent_data.get("metrics", []),
        filters=intent_data.get("filters", {}),
        group_by=intent_data.get("group_by"),
        output_format=OutputFormat(intent_output_format) if intent_output_format in OutputFormat._value2member_map_ else OutputFormat.UNKNOWN,
        requires_aggregation=bool(intent_data.get("requires_aggregation", False)),
        is_valid=not needs_clarification,
        clarification_question=clarification_question if needs_clarification else None,
    )

    # Safety: enforce schema grounding (hard fail to clarification if hallucinated columns)
    bad_cols: List[str] = []
    for m in intent.metrics:
        if m not in schema.columns:
            bad_cols.append(m)
    if intent.group_by and intent.group_by not in schema.columns:
        bad_cols.append(intent.group_by)
    for fcol in (intent.filters or {}).keys():
        if fcol not in schema.columns:
            bad_cols.append(fcol)

    if bad_cols:
        plan.needs_clarification = True
        plan.is_valid = False
        plan.clarification_question = (
            "I can't find these fields in the table schema: "
            + ", ".join(sorted(set(bad_cols)))
            + ". Please rephrase using available columns."
        )
        intent.is_valid = False
        intent.clarification_question = plan.clarification_question

    return plan, intent
