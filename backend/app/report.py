from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List


def generate_csv_report(roster: List[Dict[str, object]], report_name: str) -> str:
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{report_name}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(roster[0].keys()))
        writer.writeheader()
        writer.writerows(roster)
    return str(path)
