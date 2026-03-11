# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the repolint CLI.

These tests invoke the repolint binary directly via subprocess and make real
calls to the GitHub API (via ``gh``).  They require:

- ``repolint`` installed in the active environment
- ``gh`` CLI authenticated (``gh auth login``)
- Network access to api.github.com
"""
