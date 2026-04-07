from __future__ import annotations

from dataclasses import asdict, dataclass

from core.rpm_service import RPMFilterState


@dataclass(slots=True)
class RPMFilterTemplate:
    name: str
    description: str
    state: RPMFilterState
    built_in: bool = True


def build_builtin_templates() -> list[RPMFilterTemplate]:
    return [
        RPMFilterTemplate(
            name="Default",
            description="Balanced baseline template with no aggressive narrowing.",
            state=RPMFilterState(),
        ),
        RPMFilterTemplate(
            name="High RPM",
            description="Focus on channels with stronger RPM and higher monthly revenue potential.",
            state=RPMFilterState(
                rpm_min=4.0,
                revenue_per_month_min=5_000,
                average_views_min=100_000,
                monetized="Yes",
            ),
        ),
        RPMFilterTemplate(
            name="Evergreen",
            description="Bias toward durable educational and documentary-style channels with longer videos.",
            state=RPMFilterState(
                category="History",
                avg_video_length_min=8.0,
                avg_video_length_max=20.0,
                uploads_min=40,
                monetized="Yes",
            ),
        ),
        RPMFilterTemplate(
            name="Low Competition",
            description="Target smaller channels that still show decent views and reasonable traction.",
            state=RPMFilterState(
                subscriber_max=180_000,
                average_views_min=70_000,
                uploads_max=600,
            ),
        ),
        RPMFilterTemplate(
            name="Shorts Heavy",
            description="Surface channels leaning on frequent uploads and YouTube Shorts.",
            state=RPMFilterState(
                shorts="Yes",
                uploads_per_week_min=2.0,
                uploads_min=100,
                avg_video_length_max=10.0,
            ),
        ),
    ]


def summarize_template(template: RPMFilterTemplate) -> str:
    state = template.state
    parts: list[str] = []
    if state.category != "All Categories":
        parts.append(f"Category: {state.category}")
    if state.rpm_min > 0:
        parts.append(f"RPM >= {state.rpm_min:.1f}")
    if state.revenue_per_month_min > 0:
        parts.append(f"Revenue/mo >= ${state.revenue_per_month_min:,}")
    if state.subscriber_max < 5_000_000:
        parts.append(f"Subscribers <= {state.subscriber_max:,}")
    if state.average_views_min > 0:
        parts.append(f"Avg views >= {state.average_views_min:,}")
    if state.uploads_per_week_min > 0:
        parts.append(f"Uploads/week >= {state.uploads_per_week_min:.1f}")
    if state.monetized != "All":
        parts.append(f"Monetized: {state.monetized}")
    if state.shorts != "All":
        parts.append(f"Shorts: {state.shorts}")
    if not parts:
        return "No extra constraints. Good starting point."
    return " | ".join(parts[:4])


def clone_state(state: RPMFilterState) -> RPMFilterState:
    return RPMFilterState(**asdict(state))
