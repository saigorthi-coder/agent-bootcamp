from typing import Dict

from google.auth import default as google_auth_default
from google.cloud import bigquery

from orchestrator.contracts import TableSchema


def _get_bigquery_client(project_id: str) -> bigquery.Client:
    """
    Create a BigQuery client using the active service account.

    This supports cross-project access as long as IAM is granted.
    """
    credentials, _ = google_auth_default()

    return bigquery.Client(
        project=project_id,
        credentials=credentials,
    )


def load_table_schema(table_name: str) -> TableSchema:
    """
    Load BigQuery table schema.

    Args:
        table_name: Fully-qualified table name
                    (e.g. project.dataset.table)

    Returns:
        TableSchema object
    """

    # Expect fully-qualified table name
    # project.dataset.table
    try:
        project_id, dataset_id, table_id = table_name.split(".")
    except ValueError:
        raise ValueError(
            "table_name must be fully-qualified: project.dataset.table"
        )

    client = _get_bigquery_client(project_id)

    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    table = client.get_table(table_ref)

    columns: Dict[str, str] = {}

    for field in table.schema:
        columns[field.name] = field.field_type

    return TableSchema(
        table_name=table_ref,
        columns=columns,
    )
