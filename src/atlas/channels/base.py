"""Pluggable evidence-channel contract (PLAN: T05)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from atlas.ranking import register_mechanism_channel
from atlas.schemas import ChannelComparison


class EvidenceChannel(ABC):
    channel_id: str
    version: str
    required_fields: tuple[str, ...] = ()
    # How the channel may contribute to an evidence category. "mechanism": its supporting claims can make a
    # mechanistic or literature-supported lead; "phenotype": symptom-level only; "context": reported, never
    # a category on its own. A new channel declares this; no edit to ranking.py is needed.
    kind: Literal["mechanism", "phenotype", "context"] = "context"

    @abstractmethod
    def retrieve_candidates(self, query_id: str, context: dict[str, Any]) -> list[str]:
        """Return candidate IDs. Provenance is recorded by the caller's coverage manifest."""

    @abstractmethod
    def compare(
        self, query_id: str, candidate_id: str, context: dict[str, Any]
    ) -> ChannelComparison:
        """Return a ChannelComparison. Preserve missingness: never emit 0 for missing data."""


class ChannelRegistry:
    def __init__(self) -> None:
        self._channels: dict[str, EvidenceChannel] = {}

    def register(self, channel: EvidenceChannel) -> None:
        if channel.channel_id in self._channels:
            raise ValueError(f"channel already registered: {channel.channel_id}")
        self._channels[channel.channel_id] = channel
        if channel.kind == "mechanism":
            register_mechanism_channel(channel.channel_id)

    def channels(self) -> list[EvidenceChannel]:
        return list(self._channels.values())

    def candidate_union(self, query_id: str, context: dict[str, Any]) -> list[str]:
        seen: dict[str, None] = {}
        for ch in self._channels.values():
            for cid in ch.retrieve_candidates(query_id, context):
                seen.setdefault(cid)
        return list(seen)

    def compare_all(
        self, query_id: str, candidate_id: str, context: dict[str, Any]
    ) -> list[ChannelComparison]:
        out = []
        for ch in self._channels.values():
            try:
                out.append(ch.compare(query_id, candidate_id, context))
            except Exception as exc:  # noqa: BLE001 - a failing channel must be reported, not hide the others
                out.append(
                    ChannelComparison(
                        channel_id=ch.channel_id,
                        channel_version=ch.version,
                        query_id=query_id,
                        candidate_id=candidate_id,
                        availability="failed",
                        limitations=[f"channel raised {type(exc).__name__}"],
                    )
                )
        return out
