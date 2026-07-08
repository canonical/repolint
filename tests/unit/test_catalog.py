# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.catalog."""

import json

from repolint.catalog import load_catalog


class TestLoadCatalog:
    def test_returns_empty_dict_when_file_missing(self, tmp_path, capsys):
        result = load_catalog(tmp_path / "catalog.json")
        assert result == {}
        assert "not found" in capsys.readouterr().out

    def test_loads_service_levels(self, tmp_path):
        catalog = {
            "generated_at": "2026-01-01T00:00:00",
            "source": "https://github.com/canonical/platform-engineering-docs",
            "service_levels": {
                "canonical/gold-charm": "gold",
                "canonical/silver-charm": "silver",
                "canonical/bronze-charm": "bronze",
            },
        }
        path = tmp_path / "catalog.json"
        path.write_text(json.dumps(catalog))

        result = load_catalog(path)
        assert result == {
            "canonical/gold-charm": "gold",
            "canonical/silver-charm": "silver",
            "canonical/bronze-charm": "bronze",
        }

    def test_filters_unknown_service_levels(self, tmp_path, capsys):
        catalog = {
            "service_levels": {
                "canonical/good": "gold",
                "canonical/bad": "platinum",
            }
        }
        path = tmp_path / "catalog.json"
        path.write_text(json.dumps(catalog))

        result = load_catalog(path)
        assert "canonical/good" in result
        assert "canonical/bad" not in result
        assert "Warning" in capsys.readouterr().out

    def test_returns_empty_dict_on_empty_service_levels(self, tmp_path):
        path = tmp_path / "catalog.json"
        path.write_text(json.dumps({"service_levels": {}}))
        assert load_catalog(path) == {}
