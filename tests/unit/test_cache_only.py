"""Unit tests for cache-only reads: ``values/get`` with ``cacheOnly`` (contract section 5.2)."""

from __future__ import annotations

import json

import pytest

from accordionq2 import AccordionQ2ApiError, AccordionQ2NotSupportedError, CachedValues
from accordionq2.capabilities import CapabilitiesDto
from accordionq2.resources import ResourcesGroup

from .conftest import make_session

WITH_FEATURE = {"apiVersion": 1, "features": ["events", "values.cacheOnly"]}
WITHOUT_FEATURE = {"apiVersion": 1, "features": ["events"]}


def _sent(session: object) -> list[tuple[str, str, object]]:
    """(method, path, JSON body or None) of each request made."""
    calls = session.request.call_args_list  # type: ignore[attr-defined]
    return [
        (c.args[0], c.args[1], json.loads(c.kwargs["body"]) if c.kwargs.get("body") else None)
        for c in calls
    ]


class TestReadCached:
    def test_sends_cache_only_and_returns_values_ages_and_names_not_cached(self):
        session = make_session(
            [
                (200, WITH_FEATURE),
                (
                    200,
                    {
                        "resources": {"VMON1": "10.962"},
                        "ageMs": {"VMON1": 320},
                        "notCached": ["PEAK1", "UART"],
                    },
                ),
            ]
        )
        result = ResourcesGroup(session).read_cached(["VMON1", "PEAK1", "UART"], max_age_ms=5000)

        assert result == CachedValues(
            values={"VMON1": "10.962"}, ages_ms={"VMON1": 320.0}, not_cached=("PEAK1", "UART")
        )
        assert _sent(session) == [
            ("GET", "api/capabilities", None),
            (
                "POST",
                "api/resources/values/get",
                {"Names": ["VMON1", "PEAK1", "UART"], "MaxAgeMs": 5000, "CacheOnly": True},
            ),
        ]

    def test_capabilities_are_asked_once(self):
        answer = {"resources": {}, "ageMs": {}, "notCached": ["A"]}
        session = make_session([(200, WITH_FEATURE), (200, answer), (200, answer)])
        group = ResourcesGroup(session)
        group.read_cached(["A"])
        group.read_cached(["A"])
        assert [path for _, path, _ in _sent(session)] == [
            "api/capabilities",
            "api/resources/values/get",
            "api/resources/values/get",
        ]

    def test_max_age_defaults_to_zero_any_age(self):
        session = make_session([(200, WITH_FEATURE), (200, {"resources": {}, "notCached": []})])
        result = ResourcesGroup(session).read_cached(["A"])
        assert _sent(session)[1][2] == {"Names": ["A"], "MaxAgeMs": 0, "CacheOnly": True}
        assert result.not_cached == ()

    def test_a_station_without_the_feature_is_never_asked_for_values(self):
        session = make_session([(200, WITHOUT_FEATURE)])
        with pytest.raises(AccordionQ2NotSupportedError) as raised:
            ResourcesGroup(session).read_cached(["A"])
        assert raised.value.feature == CapabilitiesDto.VALUES_CACHE_ONLY
        assert [path for _, path, _ in _sent(session)] == ["api/capabilities"]

    def test_a_station_older_than_capabilities_is_never_asked_for_values(self):
        session = make_session([(404, b"")])
        with pytest.raises(AccordionQ2NotSupportedError):
            ResourcesGroup(session).read_cached(["A"])
        assert len(_sent(session)) == 1

    def test_an_answer_without_not_cached_means_cache_only_was_ignored(self):
        session = make_session(
            [(200, WITH_FEATURE), (200, {"resources": {"A": "1"}, "ageMs": {"A": 0}})]
        )
        with pytest.raises(AccordionQ2NotSupportedError, match="ignored cacheOnly"):
            ResourcesGroup(session).read_cached(["A"])

    def test_an_unknown_name_is_a_400(self):
        session = make_session([(200, WITH_FEATURE), (400, {"error": "No such channel: X"})])
        with pytest.raises(AccordionQ2ApiError) as raised:
            ResourcesGroup(session).read_cached(["X"])
        assert raised.value.status_code == 400
        assert not isinstance(raised.value, AccordionQ2NotSupportedError)

    def test_read_values_is_unchanged(self):
        session = make_session([(200, {"resources": {"A": "1"}, "ageMs": {"A": 0}})])
        values, ages = ResourcesGroup(session).read_values(["A"], max_age_ms=1000)
        assert (values, ages) == ({"A": "1"}, {"A": 0.0})
        assert _sent(session) == [
            ("POST", "api/resources/values/get", {"Names": ["A"], "MaxAgeMs": 1000})
        ]
