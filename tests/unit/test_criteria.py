# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for repolint.criteria."""

from repolint.criteria import get_criterion_by_name, list_criteria, list_criteria_names


class TestListCriteria:
    def test_returns_list(self):
        result = list_criteria()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_each_criterion_has_name_and_description(self):
        for criterion in list_criteria():
            assert "name" in criterion, f"Criterion missing 'name': {criterion}"
            assert "description" in criterion, (
                f"Criterion {criterion['name']!r} missing 'description'"
            )

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


class TestGetCriterionByName:
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
