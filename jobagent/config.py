"""Paths and profile loading. Everything lives under JOBAGENT_HOME (default ./data)."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("JOBAGENT_HOME", ROOT / "data"))

STATUSES = [
    "New", "Review Required", "Ready to Apply", "Applied", "Assessment",
    "Interview", "Follow-up Required", "Rejected", "Offer", "Closed",
]


def db_path() -> Path:
    return HOME / "jobs.db"


def output_dir() -> Path:
    return HOME / "output"


def load_profile() -> dict:
    return json.loads((HOME / "profile.json").read_text(encoding="utf-8"))


def master_cv_path() -> Path:
    return HOME / "master_cv.md"
