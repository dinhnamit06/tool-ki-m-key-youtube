from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Sequence

from core.rpm_data import ChannelRecord


@dataclass(slots=True)
class RPMPredictionResult:
    query: str
    matched_channel: str
    predicted_rpm: float
    confidence_label: str
    confidence_score: float
    total_revenue_generated: int
    avg_monthly_revenue: int
    avg_monthly_views: int
    avg_views_per_video: int
    monetized: bool
    note: str


class RPMPredictorService:
    def __init__(self, channels: Sequence[ChannelRecord]):
        self._channels = list(channels)

    def suggest(self, query: str, limit: int = 5) -> list[str]:
        text = str(query or "").strip().lower()
        if not text:
            return [item.title for item in self._channels[:limit]]
        ranked = sorted(
            self._channels,
            key=lambda item: self._similarity(text, item.title.lower()),
            reverse=True,
        )
        return [item.title for item in ranked[:limit]]

    def predict_channel_rpm(self, query: str) -> RPMPredictionResult | None:
        text = str(query or "").strip()
        if not text:
            return None
        matched = self._find_best_channel(text)
        if matched is None:
            return None
        channel, confidence = matched
        confidence_label = self._confidence_label(confidence)
        note = (
            "Direct title match from local sample data."
            if confidence >= 0.99
            else "Approximate title match from local sample data. Verify against the full channel page before using it as a hard decision."
        )
        return RPMPredictionResult(
            query=text,
            matched_channel=channel.title,
            predicted_rpm=channel.rpm,
            confidence_label=confidence_label,
            confidence_score=confidence,
            total_revenue_generated=channel.total_revenue_generated,
            avg_monthly_revenue=channel.avg_monthly_revenue,
            avg_monthly_views=channel.avg_monthly_views,
            avg_views_per_video=channel.avg_views_per_video,
            monetized=channel.monetized,
            note=note,
        )

    def _find_best_channel(self, query: str) -> tuple[ChannelRecord, float] | None:
        query_text = query.strip().lower()
        exact = next((item for item in self._channels if item.title.lower() == query_text), None)
        if exact is not None:
            return exact, 1.0

        contains = [item for item in self._channels if query_text in item.title.lower()]
        if contains:
            best = max(contains, key=lambda item: self._similarity(query_text, item.title.lower()))
            return best, max(0.88, self._similarity(query_text, best.title.lower()))

        ranked = sorted(
            ((item, self._similarity(query_text, item.title.lower())) for item in self._channels),
            key=lambda entry: entry[1],
            reverse=True,
        )
        if not ranked or ranked[0][1] < 0.45:
            return None
        return ranked[0]

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        return SequenceMatcher(None, left, right).ratio()

    @staticmethod
    def _confidence_label(score: float) -> str:
        if score >= 0.99:
            return "Exact"
        if score >= 0.80:
            return "High"
        if score >= 0.60:
            return "Medium"
        return "Low"
