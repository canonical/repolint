# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.criteria."""

from repolint.criteria import (
    configure_checks,
    get_criterion_by_name,
    list_criteria,
    list_criteria_names,
)


class TestListCriteria:
    def test_returns_list(self):
        result = list_criteria()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_each_criterion_has_name(self):
        for criterion in list_criteria():
            assert "name" in criterion, f"Criterion missing 'name': {criterion}"

    def test_all_depends_on_reference_earlier_criteria(self):
        """Each depends_on entry must refer to a criterion that appears earlier."""
        seen: set[str] = set()
        for criterion in list_criteria():
            for dep in criterion.get("depends_on", []):
                assert dep in seen, (
                    f"Criterion {criterion['name']!r} depends on {dep!r} "
                    f"which has not appeared yet"
                )
            seen.add(criterion["name"])

    def test_all_aggregates_reference_earlier_criteria(self):
        """Each aggregates entry must refer to a criterion that appears earlier."""
        seen: set[str] = set()
        for criterion in list_criteria():
            for agg in criterion.get("aggregates", []):
                assert agg in seen, (
                    f"Criterion {criterion['name']!r} aggregates {agg!r} "
                    f"which has not appeared yet"
                )
            seen.add(criterion["name"])

    def test_no_duplicate_names(self):
        names = [c["name"] for c in list_criteria()]
        assert len(names) == len(set(names)), "Duplicate criterion names found"


class TestConfigureChecks:
    def setup_method(self):
        """Reset overrides before each test."""
        configure_checks({})

    def teardown_method(self):
        """Reset overrides after each test."""
        configure_checks({})

    def test_no_override_returns_hardcoded_exclusions(self):
        pfe = get_criterion_by_name("pfe_topic")
        assert pfe is not None
        # hardcoded exclusions are present without any config
        assert "canonical/cbartz-runner-testing" in pfe.get("excluded", [])

    def test_configure_adds_extra_exclusions(self):
        configure_checks({"pfe_topic": {"excluded": ["canonical/extra-repo"]}})
        pfe = get_criterion_by_name("pfe_topic")
        assert pfe is not None
        excluded = pfe.get("excluded", [])
        assert "canonical/cbartz-runner-testing" in excluded
        assert "canonical/extra-repo" in excluded

    def test_configure_deduplicates_exclusions(self):
        # Configuring an already-hardcoded exclusion should not duplicate it
        configure_checks({"pfe_topic": {"excluded": ["canonical/cbartz-runner-testing"]}})
        pfe = get_criterion_by_name("pfe_topic")
        assert pfe is not None
        excluded = pfe.get("excluded", [])
        assert excluded.count("canonical/cbartz-runner-testing") == 1

    def test_configure_adds_exclusions_for_criterion_without_hardcoded(self):
        configure_checks({"charmlibs": {"excluded": ["canonical/no-libs-repo"]}})
        charmlibs = get_criterion_by_name("charmlibs")
        assert charmlibs is not None
        assert "canonical/no-libs-repo" in charmlibs.get("excluded", [])

    def test_unknown_check_in_config_is_ignored(self):
        # Should not raise; unknown check names are harmless
        configure_checks({"nonexistent_check": {"excluded": ["canonical/repo"]}})
        assert list_criteria()  # still returns normal criteria

    def test_configure_replaces_previous_overrides(self):
        configure_checks({"pfe_topic": {"excluded": ["canonical/first-repo"]}})
        configure_checks({"pfe_topic": {"excluded": ["canonical/second-repo"]}})
        pfe = get_criterion_by_name("pfe_topic")
        assert pfe is not None
        excluded = pfe.get("excluded", [])
        assert "canonical/second-repo" in excluded
        assert "canonical/first-repo" not in excluded

    def test_empty_config_uses_hardcoded_only(self):
        configure_checks({})
        pfe = get_criterion_by_name("pfe_topic")
        assert pfe is not None
        assert pfe.get("excluded") == ["canonical/cbartz-runner-testing", "wazuh-dev"]

    def test_returns_known_criterion(self):
        result = get_criterion_by_name("pfe_topic")
        assert result is not None
        assert result["name"] == "pfe_topic"

    def test_returns_none_for_unknown(self):
        result = get_criterion_by_name("nonexistent_criterion")
        assert result is None


class TestListCriteriaNames:
    def test_returns_list_of_strings(self):
        names = list_criteria_names()
        assert all(isinstance(n, str) for n in names)

    def test_matches_list_criteria(self):
        expected = [c["name"] for c in list_criteria()]
        assert list_criteria_names() == expected
