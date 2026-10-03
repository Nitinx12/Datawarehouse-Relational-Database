import math
from typing import Any

import plotly.express as px

PALETTE = ["#0E6E6E", "#2A9D8F", "#E9C46A", "#E76F51", "#5D6B8C", "#9AA5C4"]
SEQUENTIAL = ["#E6F2F0", "#BFE0DB", "#8FC9C2", "#5DAFA6", "#2A9D8F", "#0E6E6E"]


# applies the shared professional layout to any figure
def style_fig(fig: Any, height: int = 380) -> Any:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin={"l": 16, "r": 16, "t": 48, "b": 16},
        font={"family": "Inter, Segoe UI, sans-serif", "size": 12, "color": "#1A2233"},
        legend={"orientation": "h", "y": -0.18, "x": 0},
        hoverlabel={"font_size": 12},
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#E8EBF0")
    return fig


# reports whether a kpi value is missing
def _missing(value: float | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


# formats a large number as compact currency
def fmt_money(value: float | None) -> str:
    if _missing(value):
        return "-"
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if magnitude >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


# formats a large count compactly
def fmt_num(value: float | None) -> str:
    if _missing(value):
        return "-"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


# builds an area trend figure for a monthly metric
def area_trend(frame: Any, x: str, y: str, title: str, color: str = PALETTE[0]) -> Any:
    fig = px.area(frame, x=x, y=y, title=title, color_discrete_sequence=[color])
    fig.update_traces(line={"width": 2.5})
    return style_fig(fig)


# builds a horizontal bar figure sorted by value
def hbar(frame: Any, x: str, y: str, title: str, color_col: str | None = None) -> Any:
    fig = px.bar(
        frame,
        x=x,
        y=y,
        title=title,
        orientation="h",
        color=color_col,
        color_discrete_sequence=PALETTE,
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return style_fig(fig)


# builds a donut figure for segment mix
def donut(frame: Any, names: str, values: str, title: str) -> Any:
    fig = px.pie(
        frame,
        names=names,
        values=values,
        title=title,
        hole=0.55,
        color_discrete_sequence=PALETTE,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return style_fig(fig, height=360)


# builds a treemap for category to subcategory revenue
def treemap(frame: Any, path: list[str], values: str, title: str) -> Any:
    fig = px.treemap(
        frame,
        path=path,
        values=values,
        title=title,
        color=values,
        color_continuous_scale=["#E6F2F0", "#0E6E6E"],
    )
    return style_fig(fig, height=460)


# renders a kpi card row value with month-over-month delta text
def kpi_delta(current: float, previous: float) -> tuple[str, str]:
    if previous is None or _missing(previous) or previous == 0:
        return "n/a", "off"
    pct = (current - previous) / abs(previous) * 100
    direction = "normal" if pct >= 0 else "inverse"
    return f"{pct:+.1f}% MoM", direction
