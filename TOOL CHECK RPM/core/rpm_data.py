from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List


@dataclass(slots=True)
class ChannelRecord:
    title: str
    category: str
    subscribers: int
    avg_views_per_video: int
    days_since_start: int
    upload_count: int
    monetized: bool
    total_views: int
    avg_monthly_views: int
    total_revenue_generated: int
    avg_monthly_revenue: int
    rpm: float
    last_upload_days_ago: int
    avg_monthly_upload_freq: int
    avg_video_length_minutes: float
    has_shorts: bool
    first_upload_date: date
    last_upload_date: date
    median_views_per_video: int
    uploads_per_week: float
    keywords: List[str] = field(default_factory=list)
    picked_by_ai: bool = False
    revealed: bool = False
    most_popular_videos: List[str] = field(default_factory=list)


def build_sample_channels() -> list[ChannelRecord]:
    return [
        ChannelRecord(
            title="Culture Spill",
            category="Storytelling",
            subscribers=161_000,
            avg_views_per_video=111_798,
            days_since_start=775,
            upload_count=541,
            monetized=True,
            total_views=91_887_966,
            avg_monthly_views=1_212_975,
            total_revenue_generated=186_790,
            avg_monthly_revenue=4_482,
            rpm=2.1,
            last_upload_days_ago=8,
            avg_monthly_upload_freq=3,
            avg_video_length_minutes=5.68,
            has_shorts=True,
            first_upload_date=date(2021, 2, 12),
            last_upload_date=date(2026, 3, 30),
            median_views_per_video=103_000,
            uploads_per_week=0.9,
            keywords=["culture", "stories", "history", "news"],
            picked_by_ai=True,
            revealed=False,
            most_popular_videos=["How one choice changed history", "The forgotten empire story"],
        ),
        ChannelRecord(
            title="Stories To Remember",
            category="History",
            subscribers=145_000,
            avg_views_per_video=367_744,
            days_since_start=663,
            upload_count=104,
            monetized=True,
            total_views=74_205_502,
            avg_monthly_views=2_108_200,
            total_revenue_generated=222_455,
            avg_monthly_revenue=6_430,
            rpm=3.05,
            last_upload_days_ago=6,
            avg_monthly_upload_freq=4,
            avg_video_length_minutes=12.1,
            has_shorts=False,
            first_upload_date=date(2021, 7, 4),
            last_upload_date=date(2026, 4, 1),
            median_views_per_video=291_000,
            uploads_per_week=1.0,
            keywords=["history", "documentary", "storytelling"],
            picked_by_ai=True,
            revealed=False,
            most_popular_videos=["The battle nobody remembers", "Ancient myths explained"],
        ),
        ChannelRecord(
            title="Space Matters",
            category="Biology",
            subscribers=222_000,
            avg_views_per_video=397_890,
            days_since_start=883,
            upload_count=102,
            monetized=True,
            total_views=40_584_744,
            avg_monthly_views=1_968_679,
            total_revenue_generated=465_195,
            avg_monthly_revenue=13_871,
            rpm=4.8,
            last_upload_days_ago=8,
            avg_monthly_upload_freq=13,
            avg_video_length_minutes=14.48,
            has_shorts=False,
            first_upload_date=date(2020, 12, 21),
            last_upload_date=date(2026, 3, 30),
            median_views_per_video=344_000,
            uploads_per_week=3.2,
            keywords=["biology", "science", "education", "explainer"],
            picked_by_ai=True,
            revealed=True,
            most_popular_videos=["The hidden life of cells", "Why evolution never stops"],
        ),
        ChannelRecord(
            title="Navy Productions",
            category="Documentary",
            subscribers=330_000,
            avg_views_per_video=901_869,
            days_since_start=921,
            upload_count=167,
            monetized=True,
            total_views=128_550_612,
            avg_monthly_views=2_404_000,
            total_revenue_generated=512_400,
            avg_monthly_revenue=11_240,
            rpm=4.1,
            last_upload_days_ago=11,
            avg_monthly_upload_freq=7,
            avg_video_length_minutes=11.2,
            has_shorts=True,
            first_upload_date=date(2020, 11, 13),
            last_upload_date=date(2026, 3, 27),
            median_views_per_video=617_000,
            uploads_per_week=1.6,
            keywords=["navy", "war", "military", "history"],
            picked_by_ai=True,
            revealed=False,
            most_popular_videos=["How submarines disappear", "Why aircraft carriers dominate"],
        ),
        ChannelRecord(
            title="The Urbanoire",
            category="Design",
            subscribers=158_000,
            avg_views_per_video=95_874,
            days_since_start=606,
            upload_count=534,
            monetized=True,
            total_views=100_691_586,
            avg_monthly_views=2_404_000,
            total_revenue_generated=465_195,
            avg_monthly_revenue=13_871,
            rpm=4.8,
            last_upload_days_ago=8,
            avg_monthly_upload_freq=13,
            avg_video_length_minutes=14.48,
            has_shorts=False,
            first_upload_date=date(2022, 8, 1),
            last_upload_date=date(2026, 3, 30),
            median_views_per_video=82_000,
            uploads_per_week=3.0,
            keywords=["design", "architecture", "urban", "visual"],
            picked_by_ai=True,
            revealed=False,
            most_popular_videos=["The city that never made sense", "Why brutalism returned"],
        ),
        ChannelRecord(
            title="Kiki's Tea",
            category="Entertainment",
            subscribers=122_000,
            avg_views_per_video=70_517,
            days_since_start=696,
            upload_count=712,
            monetized=True,
            total_views=36_500_000,
            avg_monthly_views=850_000,
            total_revenue_generated=102_800,
            avg_monthly_revenue=2_410,
            rpm=2.4,
            last_upload_days_ago=5,
            avg_monthly_upload_freq=18,
            avg_video_length_minutes=8.1,
            has_shorts=True,
            first_upload_date=date(2021, 5, 28),
            last_upload_date=date(2026, 4, 2),
            median_views_per_video=55_000,
            uploads_per_week=4.3,
            keywords=["tea", "celebrity", "commentary", "gossip"],
            picked_by_ai=True,
            revealed=False,
            most_popular_videos=["The drama timeline", "Celebrity story recap"],
        ),
        ChannelRecord(
            title="Donald News",
            category="Politics",
            subscribers=250_000,
            avg_views_per_video=937_632,
            days_since_start=881,
            upload_count=98,
            monetized=True,
            total_views=91_887_966,
            avg_monthly_views=1_212_975,
            total_revenue_generated=186_790,
            avg_monthly_revenue=4_482,
            rpm=2.1,
            last_upload_days_ago=8,
            avg_monthly_upload_freq=3,
            avg_video_length_minutes=5.68,
            has_shorts=True,
            first_upload_date=date(2020, 12, 23),
            last_upload_date=date(2026, 3, 30),
            median_views_per_video=810_000,
            uploads_per_week=0.8,
            keywords=["news", "politics", "donald", "america"],
            picked_by_ai=False,
            revealed=False,
            most_popular_videos=["Election recap", "Debate highlights"],
        ),
    ]
