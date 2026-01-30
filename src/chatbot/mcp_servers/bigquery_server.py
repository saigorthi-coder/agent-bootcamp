from typing import Dict, Any, List

from google.cloud import bigquery
from mcp.server.fastmcp import FastMCP

print("Starting BigQuery MCP server...")

mcp = FastMCP("bigquery-executor")


@mcp.tool()
def run_query(sql: str) -> Dict[str, Any]:
    """
    Execute a BigQuery SQL query.
    SQL must already be validated.
    """
    client = bigquery.Client()

    job = client.query(sql)
    result = job.result()

    rows: List[Dict[str, Any]] = [dict(row) for row in result]

    return {
        "rows": rows,
        "row_count": len(rows),
    }
