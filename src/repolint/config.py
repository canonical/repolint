# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Configuration and constants for repolint."""

import tempfile
from pathlib import Path

DEFAULT_CONFIG_FILE = Path("repolint.yaml")
REPORTS_PATH = Path("reports/")
SQUAD_TOPICS = {"squad-apac", "squad-amer", "squad-emea"}
TMP_DIR = Path(tempfile.gettempdir()) / "repo_clones"

CHECK_COMPLIANT = "✅"
CHECK_NOT_COMPLIANT = "❌"
CHECK_NOT_ELIGIBLE = "n/a"
