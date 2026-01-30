import json
import os
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

from orchestrator.contracts import ParsedIntent, SQLQuery, TableSchema


# -----------------------------
# Client
# ----------------------------- no API kets to the indiviodual agent only the main agent
# def _get_openai_client() -> OpenAI:
#     api_key = os.getenv("OPENAI_API_KEY")
#     if not api_key:
#         raise RuntimeError("OPENAI_API_KEY is not set. Did you call load_env()?")

#     return OpenAI(
#         api_key=api_key,
#         base_url=os.getenv("OPENAI_BASE_URL"),  # optional
#     )

## Which LLm Model - workers use teh lite model and the pros is main agent. USe flash for the wrokers with retries

DEFAULT_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-pro")


# -----------------------------
# Robust JSON extraction
# -----------------------------
def _extract_first_json_object(text: str) -> Dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("Empty model output")

    text = text.strip()

    fenced = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        return json.loads(fenced.group(1))

    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start == -1 or brace_end == -1 or brace_end <= brace_start:
        raise ValueError(f"No JSON object found in model output: {text[:200]}")

    candidate = text[brace_start : brace_end + 1]
    return json.loads(candidate)


# -----------------------------
# Safety validation
# -----------------------------
_PROHIBITED = re.compile(
    r"\b("
    r"insert|update|delete|merge|truncate|drop|create|alter|grant|revoke|call|execute|"
    r"begin|commit|rollback"
    r")\b",
    re.IGNORECASE,
)

def _is_single_statement(sql: str) -> bool:
    # allow trailing semicolon only
    s = sql.strip()
    if s.endswith(";"):
        s = s[:-1].strip()
    return ";" not in s

def _starts_with_select_or_with(sql: str) -> bool:
    s = sql.strip().lower()
    return s.startswith("select") or s.startswith("with")

def _contains_prohibited(sql: str) -> Optional[str]:
    m = _PROHIBITED.search(sql)
    return m.group(0) if m else None

def _validate_referenced_columns(referenced: List[str], schema: TableSchema) -> List[str]:
    bad = []
    for c in referenced:
        if c not in schema.columns:
            bad.append(c)
    return bad

def _validate_table_reference(sql: str, table_name: str) -> Optional[str]:
    """
    Enforce single-table MVP:
    - query must reference ONLY the provided table (allow backticks or not)
    - must not reference other tables
    """
    # Normalize possible quoting
    # Allow: `proj.dataset.table` or proj.dataset.table
    tn = table_name.strip()
    tn_quoted = f"`{tn}`"

    sql_l = sql.lower()
    tn_l = tn.lower()
    tnq_l = tn_quoted.lower()

    # Must reference the table at least once
    if tn_l not in sql_l and tnq_l not in sql_l:
        return f"SQL must reference the target table only: {table_name}"

    # Detect other FROM/JOIN table tokens (best-effort)
    # This is a heuristic, but effective for MVP.
    table_tokens = re.findall(r"\b(from|join)\s+(`[^`]+`|[a-zA-Z0-9_.-]+)", sql_l)
    others = []
    for _, tok in table_tokens:
        tok_clean = tok.strip()
        if tok_clean.startswith("`") and tok_clean.endswith("`"):
            tok_clean = tok_clean[1:-1]
        if tok_clean != tn_l:
            others.append(tok_clean)

    if others:
        return f"Only one table is allowed for MVP. Found other tables: {sorted(set(others))}"

    return None


# -----------------------------
# LLM prompt
# -----------------------------
SYSTEM_PROMPT = """
You are a SQL Planner Agent for a BigQuery analytics chatbot.

You MUST output ONLY JSON (no markdown, no commentary).

Rules:
- BigQuery Standard SQL only.
- Single table only: use ONLY the provided fully-qualified table name.
- Use ONLY provided column names (never invent columns).
- SELECT/CTE only (SELECT or WITH). No DDL/DML.
- Do NOT add LIMIT (row limiting happens after execution for display).
- If something is ambiguous, return a clarification_question and an empty sql.
"""


def generate_sql(
    intent: ParsedIntent,
    schema: TableSchema,
    table_name: str,
) -> SQLQuery:
    client = _get_openai_client()

    cols = list(schema.columns.keys())

    user_prompt = f"""
Target table (must be used, and only this table):
{table_name}

Available columns (ONLY these may be referenced):
{cols}

User intent object:
{{
  "metrics": {intent.metrics},
  "filters": {intent.filters},
  "group_by": {intent.group_by!r},
  "output_format": "{intent.output_format.value}",
  "requires_aggregation": {intent.requires_aggregation}
}}

Return JSON in EXACT schema:
{{
  "sql": "string (BigQuery SQL) or empty string",
  "referenced_columns": ["col1","col2"],
  "clarification_needed": false,
  "clarification_question": null
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
    errors: List[str] = []

    try:
        data = _extract_first_json_object(raw)
    except Exception as e:
        return SQLQuery(query="", is_safe=False, validation_errors=[f"LLM output not parseable as JSON: {e}"])

    sql = (data.get("sql") or "").strip()
    referenced_columns = data.get("referenced_columns") or []
    clarification_needed = bool(data.get("clarification_needed", False))
    clarification_question = data.get("clarification_question")

    if clarification_needed:
        return SQLQuery(
            query="",
            is_safe=False,
            validation_errors=[clarification_question or "Clarification required."],
        )

    if not sql:
        return SQLQuery(
            query="",
            is_safe=False,
            validation_errors=["SQL Planner returned empty SQL."],
        )

    # --- Safety validations ---
    if not _starts_with_select_or_with(sql):
        errors.append("Only SELECT/CTE queries are allowed (must start with SELECT or WITH).")

    bad_kw = _contains_prohibited(sql)
    if bad_kw:
        errors.append(f"Prohibited keyword detected: {bad_kw}")

    if not _is_single_statement(sql):
        errors.append("Multiple SQL statements detected; only one statement is allowed.")

    other_table_err = _validate_table_reference(sql, table_name)
    if other_table_err:
        errors.append(other_table_err)

    bad_cols = _validate_referenced_columns(referenced_columns, schema)
    if bad_cols:
        errors.append(f"Unknown columns referenced: {sorted(set(bad_cols))}")

    is_safe = len(errors) == 0
    return SQLQuery(query=sql, is_safe=is_safe, validation_errors=errors)
