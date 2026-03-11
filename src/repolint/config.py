# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Configuration and constants for repolint."""

import tempfile
from enum import StrEnum
from pathlib import Path

DEFAULT_CONFIG_FILE = Path("repolint.yaml")
REPORTS_PATH = Path("reports/")
TMP_DIR = Path(tempfile.gettempdir()) / "repo_clones"


class CheckStatus(StrEnum):
    """Compliance status values for a check result."""

    COMPLIANT = "✅"
    NOT_COMPLIANT = "❌"
    NOT_ELIGIBLE = "n/a"
