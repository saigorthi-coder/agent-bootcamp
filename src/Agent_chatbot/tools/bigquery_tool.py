from typing import Dict, Any, List, Optional
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPICallError, BadRequest



# Initialize client once (uses GOOGLE_APPLICATION_CREDENTIALS)
# Project here does NOT matter because we always use fully-qualified SQL
BQ_PROJECT = "project-ad8e168b-9904-43b7-b43"

_bq_client = bigquery.Client(project=BQ_PROJECT)


def run_bigquery_query(
    sql: str,
    max_rows: int = 1000,
    ##job_config: Optional[bigquery.QueryJobConfig] = None,
) -> Dict[str, Any]:
    """
    Execute a BigQuery SQL query and return structured results.

    IMPORTANT DESIGN NOTES:
    - This function is intentionally synchronous.
    - This function must accept ONLY JSON-serializable arguments.
    - Fully-qualified SQL controls which project/dataset is queried.
    - This function does NOT retry on failure. Retry logic is handled by the SQLAgent itself.


    Parameters
    ----------
    sql : str
        Fully-qualified BigQuery SQL query.
    max_rows : int
        Maximum number of rows to return.
    job_config : QueryJobConfig, optional
        Optional job configuration (e.g., dry_run, query params).

    Returns
    -------
    Dict[str, Any]
        {
            "success": bool,
            "sql": str,
            "row_count": int,
            "rows": List[Dict],
            "error_message": Optional[str]
        }
    """

    try:
        # Submit query
        query_job = _bq_client.query(sql)

        # Block until completion and fetch results
        results = query_job.result(max_results=max_rows)

        rows: List[Dict[str, Any]] = [dict(row) for row in results]

        return {
            "success": True,
            "sql": sql,
            "row_count": len(rows),
            "rows": rows,
            "error_message": None,
        }

    except BadRequest as e:
        # SQL syntax / semantic errors
        return {
            "success": False,
            "sql": sql,
            "row_count": 0,
            "rows": [],
            "error_message": _extract_bq_error(e),
        }

    except GoogleAPICallError as e:
        # Network / permission / API-level errors
        return {
            "success": False,
            "sql": sql,
            "row_count": 0,
            "rows": [],
            "error_message": str(e),
        }

    except Exception as e:
        # Catch-all for safety (agent will retry or fail gracefully)
        return {
            "success": False,
            "sql": sql,
            "row_count": 0,
            "rows": [],
            "error_message": str(e),
        }


def _extract_bq_error(error: BadRequest) -> str:
    """
    Extract a concise, readable error message from BigQuery BadRequest.
    """
    if hasattr(error, "errors") and error.errors:
        # Return first BigQuery error message
        return error.errors[0].get("message", str(error))
    return str(error)
