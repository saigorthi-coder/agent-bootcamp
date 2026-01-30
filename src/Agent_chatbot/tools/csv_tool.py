import csv
import json
from typing import Dict, Any
from pathlib import Path
import uuid


BASE_TEMP_DIR = Path(__file__).resolve().parents[1] / "temp_files"
BASE_TEMP_DIR.mkdir(parents=True, exist_ok=True)


def rows_to_csv(rows_json: str) -> Dict[str, Any]:
    """
    Convert JSON-encoded rows into a CSV file stored in temp_files/.

    rows_json: JSON string representing List[Dict[str, scalar]]

    Returns:
    {
        "success": bool,
        "csv_path": str | None,
        "row_count": int,
        "error_message": str | None
    }
    """

    try:
        rows = json.loads(rows_json)

        if not rows:
            return {
                "success": False,
                "csv_path": None,
                "row_count": 0,
                "error_message": "No rows provided to convert to CSV.",
            }

        filename = f"query_result_{uuid.uuid4().hex}.csv"
        csv_path = BASE_TEMP_DIR / filename

        with open(csv_path, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        return {
            "success": True,
            "csv_path": str(csv_path),
            "row_count": len(rows),
            "error_message": None,
        }

    except Exception as e:
        return {
            "success": False,
            "csv_path": None,
            "row_count": 0,
            "error_message": str(e),
        }
