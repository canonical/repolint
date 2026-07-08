# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# Repolint Justfile

# Install all dependencies
install-requirements:
    uv sync --all-groups

# Run formatting checks
lint:
    tox -e lint

# Run static analysis
static:
    tox -e static

# Run unit tests
test:
    tox -e unit

# Run integration tests (requires gh CLI authenticated + network)
test-integ:
    tox -e integration
