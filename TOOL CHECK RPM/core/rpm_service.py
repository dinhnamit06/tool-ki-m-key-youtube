from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence

from core.rpm_data import ChannelRecord


@dataclass(slots=True)
class RPMFilterState:
    category: str = "All Categories"
    subscriber_min: int = 0
    subscriber_max: int = 5_000_000
    first_upload_after: date | None = None
    first_upload_before: date | None = None
    last_upload_after: date | None = None
    last_upload_before: date | None = None
    rpm_min: float = 0.0
    rpm_max: float = 25.0
    revenue_generated_min: int = 0
    revenue_generated_max: int = 1_000_000
    revenue_per_month_min: int = 0
    revenue_per_month_max: int = 100_000
    total_views_min: int = 0
    total_views_max: int = 1_000_000_000
    views_per_month_min: int = 0
    views_per_month_max: int = 100_000_000
    average_views_min: int = 0
    average_views_max: int = 2_000_000
    median_views_min: int = 0
    median_views_max: int = 2_000_000
    uploads_min: int = 0
    uploads_max: int = 2_000
    uploads_per_week_min: float = 0.0
    uploads_per_week_max: float = 21.0
    avg_video_length_min: float = 0.0
    avg_video_length_max: float = 45.0
    monetized: str = "All"
    shorts: str = "All"
    hide_revealed_channels: bool = False


SORT_OPTIONS: list[tuple[str, str]] = [
    ("AI Rank", "ai_rank"),
    ("RPM", "rpm"),
    ("Revenue / Month", "avg_monthly_revenue"),
    ("Revenue / Lifetime", "total_revenue_generated"),
    ("Views / Month", "avg_monthly_views"),
    ("Avg Views / Video", "avg_views_per_video"),
    ("Subscribers", "subscribers"),
    ("Total Views", "total_views"),
    ("Upload Count", "upload_count"),
    ("Last Upload Date", "last_upload_date"),
    ("First Upload Date", "first_upload_date"),
]


class RPMFinderService:
    def __init__(self, channels: Sequence[ChannelRecord]):
        self._channels = list(channels)

    def all_channels(self) -> list[ChannelRecord]:
        return list(self._channels)

    def filter_channels(self, search_mode: str, query: str, filters: RPMFilterState) -> list[ChannelRecord]:
        query_text = str(query or "").strip().lower()
        search_mode_text = str(search_mode or "Keyword").strip().lower()

        results: list[ChannelRecord] = []
        for item in self._channels:
            if filters.hide_revealed_channels and item.revealed:
                continue
            if filters.category != "All Categories" and item.category != filters.category:
                continue
            if not self._match_range(item.subscribers, filters.subscriber_min, filters.subscriber_max):
                continue
            if not self._match_range(item.rpm, filters.rpm_min, filters.rpm_max):
                continue
            if not self._match_range(item.total_revenue_generated, filters.revenue_generated_min, filters.revenue_generated_max):
                continue
            if not self._match_range(item.avg_monthly_revenue, filters.revenue_per_month_min, filters.revenue_per_month_max):
                continue
            if not self._match_range(item.total_views, filters.total_views_min, filters.total_views_max):
                continue
            if not self._match_range(item.avg_monthly_views, filters.views_per_month_min, filters.views_per_month_max):
                continue
            if not self._match_range(item.avg_views_per_video, filters.average_views_min, filters.average_views_max):
                continue
            if not self._match_range(item.median_views_per_video, filters.median_views_min, filters.median_views_max):
                continue
            if not self._match_range(item.upload_count, filters.uploads_min, filters.uploads_max):
                continue
            if not self._match_range(item.uploads_per_week, filters.uploads_per_week_min, filters.uploads_per_week_max):
                continue
            if not self._match_range(item.avg_video_length_minutes, filters.avg_video_length_min, filters.avg_video_length_max):
                continue
            if not self._match_date(item.first_upload_date, filters.first_upload_after, filters.first_upload_before):
                continue
            if not self._match_date(item.last_upload_date, filters.last_upload_after, filters.last_upload_before):
                continue
            if filters.monetized == "Yes" and not item.monetized:
                continue
            if filters.monetized == "No" and item.monetized:
                continue
            if filters.shorts == "Yes" and not item.has_shorts:
                continue
            if filters.shorts == "No" and item.has_shorts:
                continue
            if query_text and not self._match_query(item, query_text, search_mode_text):
                continue
            results.append(item)
        return results

    def sort_channels(self, channels: Sequence[ChannelRecord], sort_key: str, descending: bool = True) -> list[ChannelRecord]:
        sort_name = str(sort_key or "ai_rank").strip().lower()
        if sort_name == "ai_rank":
            return sorted(
                channels,
                key=lambda item: (
                    1 if item.picked_by_ai else 0,
                    item.rpm,
                    item.avg_monthly_revenue,
                    item.avg_monthly_views,
                    item.avg_views_per_video,
                ),
                reverse=descending,
            )
        return sorted(channels, key=lambda item: self._sort_value(item, sort_name), reverse=descending)

    @staticmethod
    def _match_range(value: float, min_value: float, max_value: float) -> bool:
        return min_value <= value <= max_value

    @staticmethod
    def _match_date(value: date, after_value: date | None, before_value: date | None) -> bool:
        if after_value and value < after_value:
            return False
        if before_value and value > before_value:
            return False
        return True

    @staticmethod
    def _match_query(item: ChannelRecord, query_text: str, search_mode_text: str) -> bool:
        searchable_keywords = " ".join(item.keywords).lower()
        haystack = f"{item.title.lower()} {item.category.lower()} {searchable_keywords}"
        if search_mode_text == "channel":
            return query_text in item.title.lower()
        return query_text in haystack

    @staticmethod
    def _sort_value(item: ChannelRecord, sort_name: str):
        mapping = {
            "rpm": item.rpm,
            "avg_monthly_revenue": item.avg_monthly_revenue,
            "total_revenue_generated": item.total_revenue_generated,
            "avg_monthly_views": item.avg_monthly_views,
            "avg_views_per_video": item.avg_views_per_video,
            "subscribers": item.subscribers,
            "total_views": item.total_views,
            "upload_count": item.upload_count,
            "last_upload_date": item.last_upload_date,
            "first_upload_date": item.first_upload_date,
        }
        return mapping.get(sort_name, item.rpm)


def categories_from_channels(channels: Iterable[ChannelRecord]) -> list[str]:
    values = sorted({item.category for item in channels})
    return ["All Categories", *values]


def sort_labels() -> list[str]:
    return [label for label, _key in SORT_OPTIONS]


def sort_key_from_label(label: str) -> str:
    label_text = str(label or "").strip()
    for option_label, option_key in SORT_OPTIONS:
        if option_label == label_text:
            return option_key
    return "ai_rank"
