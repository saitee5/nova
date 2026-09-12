"""
backend/tests/intelligence/test_providers.py — Provider Implementation Test Suite.

Tests:
  - Provider interface contract compliance
  - Default PlantState-backed provider implementations
  - InMemoryHistoricalEpisodeProvider similarity search
  - StubKnowledgeProvider returns empty (not fabricated) results
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from backend.services.providers.interfaces import (
    AlarmProvider,
    AssetProvider,
    HistoricalEpisodeProvider,
    KnowledgeProvider,
    MaintenanceProvider,
    OperationsProvider,
    PermitProvider,
    TelemetryProvider,
)
from backend.services.providers.default_providers import (
    InMemoryHistoricalEpisodeProvider,
    PlantStateAssetProvider,
    StubKnowledgeProvider,
)


class TestInterfaceAbstractness:
    """All provider ABCs must not be directly instantiable."""

    def test_telemetry_provider_is_abstract(self):
        with pytest.raises(TypeError):
            TelemetryProvider()  # type: ignore

    def test_alarm_provider_is_abstract(self):
        with pytest.raises(TypeError):
            AlarmProvider()  # type: ignore

    def test_asset_provider_is_abstract(self):
        with pytest.raises(TypeError):
            AssetProvider()  # type: ignore

    def test_knowledge_provider_is_abstract(self):
        with pytest.raises(TypeError):
            KnowledgeProvider()  # type: ignore


class TestPlantStateAssetProvider:

    def test_get_asset_returns_none_for_unknown(self):
        provider = PlantStateAssetProvider()
        result = provider.get_asset("NONEXISTENT-ASSET")
        assert result is None

    def test_get_asset_returns_metadata_for_known(self):
        provider = PlantStateAssetProvider()
        result = provider.get_asset("F-201A")
        assert result is not None
        assert result["asset_id"] == "F-201A"

    def test_get_asset_criticality_known(self):
        provider = PlantStateAssetProvider()
        crit = provider.get_asset_criticality("F-201A")
        assert crit in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_get_asset_criticality_unknown_defaults_medium(self):
        provider = PlantStateAssetProvider()
        crit = provider.get_asset_criticality("UNKNOWN-ASSET-XYZ")
        assert crit == "MEDIUM"

    def test_get_assets_for_unit(self):
        provider = PlantStateAssetProvider()
        assets = provider.get_assets_for_unit("UNIT-CRACK-01")
        assert isinstance(assets, list)
        # Reference plant has several assets in this unit
        assert any(a["asset_id"] == "F-201A" for a in assets)


class TestInMemoryHistoricalEpisodeProvider:

    def _sample_episodes(self):
        return [
            {
                "episode_id": "EP-001",
                "title": "Furnace tube overtemperature event",
                "asset_id": "F-201A",
                "summary": "Elevated tube skin temperature caused by coking",
                "root_causes": ["coking", "high firing rate"],
                "outcome": "decoking run completed",
                "similarity_score": 0.0,
            },
            {
                "episode_id": "EP-002",
                "title": "Compressor surge and vibration alert",
                "asset_id": "K-201",
                "summary": "Surge detected during startup ramp",
                "root_causes": ["surge", "low suction pressure"],
                "outcome": "throughput reduced, normal restored",
                "similarity_score": 0.0,
            },
        ]

    def test_search_returns_empty_when_no_episodes(self):
        provider = InMemoryHistoricalEpisodeProvider()
        results = provider.search_similar_episodes("anomaly detected", top_k=5)
        assert results == []

    def test_search_with_keyword_match(self):
        provider = InMemoryHistoricalEpisodeProvider(episodes=self._sample_episodes())
        results = provider.search_similar_episodes("coking tube temperature", top_k=5)
        assert len(results) >= 1
        assert results[0]["episode_id"] == "EP-001"  # Should be top match

    def test_search_filtered_by_asset(self):
        provider = InMemoryHistoricalEpisodeProvider(episodes=self._sample_episodes())
        results = provider.search_similar_episodes("surge compressor", asset_id="K-201", top_k=5)
        assert all(r["asset_id"] == "K-201" for r in results)

    def test_get_episode_by_id(self):
        provider = InMemoryHistoricalEpisodeProvider(episodes=self._sample_episodes())
        ep = provider.get_episode_by_id("EP-001")
        assert ep is not None
        assert ep["title"] == "Furnace tube overtemperature event"

    def test_get_episode_by_id_missing(self):
        provider = InMemoryHistoricalEpisodeProvider(episodes=self._sample_episodes())
        ep = provider.get_episode_by_id("EP-NONEXISTENT")
        assert ep is None

    def test_seed_method(self):
        provider = InMemoryHistoricalEpisodeProvider()
        assert provider.search_similar_episodes("test") == []
        provider.seed(self._sample_episodes())
        results = provider.search_similar_episodes("tube", top_k=5)
        assert len(results) > 0

    def test_similarity_scores_are_in_range(self):
        provider = InMemoryHistoricalEpisodeProvider(episodes=self._sample_episodes())
        results = provider.search_similar_episodes("furnace anomaly", top_k=5)
        for r in results:
            assert 0.0 <= r["similarity_score"] <= 1.0


class TestStubKnowledgeProvider:

    def test_search_returns_empty_list(self):
        provider = StubKnowledgeProvider()
        results = provider.search_knowledge("tube overtemperature procedures")
        assert results == []

    def test_get_operating_limits_returns_empty_dict(self):
        """
        CRITICAL: StubKnowledgeProvider must return {} not fake limits.
        The Risk Engine handles empty dict explicitly.
        """
        provider = StubKnowledgeProvider()
        limits = provider.get_operating_limits("F-201A")
        assert limits == {}

    def test_get_operating_limits_with_parameter(self):
        provider = StubKnowledgeProvider()
        limits = provider.get_operating_limits("F-201A", parameter="TI-20101")
        assert limits == {}
