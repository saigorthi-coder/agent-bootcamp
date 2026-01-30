from google.cloud import bigquery
from google.auth import default

from orchestrator.contracts import SQLQuery, QueryResult


# 🔒 THIS MUST BE YOUR PERSONAL PROJECT
BQ_JOB_PROJECT =  "project-ad8e168b-9904-43b7-b43"


class ExecutionAgent:
    """
    Deterministic execution agent.
    Executes BigQuery queries in the PERSONAL project,
    even though credentials belong to another account.
    """

    def __init__(self):
        credentials, _ = default()

        # 🔑 Force quota + billing project
        credentials = credentials.with_quota_project(BQ_JOB_PROJECT)

        self.client = bigquery.Client(
            project=BQ_JOB_PROJECT,      # 👈 THIS IS CRITICAL
            credentials=credentials,
        )

    def execute(self, sql_query: SQLQuery) -> QueryResult:
        if not sql_query.is_safe:
            raise ValueError(
                f"Unsafe SQL cannot be executed: {sql_query.validation_errors}"
            )

        job = self.client.query(sql_query.query)
        result = job.result()

        rows = [dict(row) for row in result]

        return QueryResult(
            rows=rows,
            row_count=len(rows),
            truncated=False,
        )
