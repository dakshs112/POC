import pandas as pd
import plotly.graph_objects as go

# F1-inspired palette
RED = "#E10600"
INK = "#15151E"
GRAY = "#38383F"
WHITE = "#F5F5F5"
ACCENT = "#00D2BE"

FONT = dict(family="Inter, 'Segoe UI', sans-serif", color=WHITE)

LAYOUT_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=FONT,
    margin=dict(l=10, r=10, t=40, b=10),
    hoverlabel=dict(bgcolor=INK, font_color=WHITE, bordercolor=RED),
)


def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """
    Match a column flexibly: exact match first, then case-insensitive,
    then substring match (e.g. 'author_name' matches candidate 'author').
    """
    cols = list(df.columns)

    for name in candidates:
        if name in cols:
            return name

    lower_map = {c.lower(): c for c in cols}
    for name in candidates:
        if name.lower() in lower_map:
            return lower_map[name.lower()]

    for name in candidates:
        for c in cols:
            if name.lower() in c.lower():
                return c

    return None


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=15, color=GRAY),
        align="center",
    )
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=380,
    )
    return fig


def _shape_debug_message(df: pd.DataFrame, expected: dict[str, list[str]]) -> str:
    """Build a helpful message showing what we got vs what we looked for."""
    cols = ", ".join(df.columns) if len(df.columns) else "(no columns — empty response)"
    lines = [f"Columns received: {cols}"]
    for role, candidates in expected.items():
        lines.append(f"Looking for {role} in: {', '.join(candidates)}")
    return "<br>".join(lines)


def authors_chart(authors: list[dict]) -> go.Figure:
    df = pd.DataFrame(authors)
    if df.empty:
        return _empty_figure("No author data yet — hit '🔄 Sync RSS Feed'")

    # name_candidates = ["author", "name", "username", "user"]
    # count_candidates = ["post_count", "count", "posts", "total", "num_posts", "value"]
    name_candidates = ["author", "name", "username", "user", "_id"]
    count_candidates = ["posts", "post_count", "count", "total", "num_posts", "value"]

    name_col = _pick_col(df, name_candidates)
    count_col = _pick_col(df, count_candidates)

    if not name_col or not count_col:
        expected = {"author name": name_candidates, "post count": count_candidates}
        return _empty_figure(_shape_debug_message(df, expected))

    plot_df = df[[name_col, count_col]].copy()
    plot_df[count_col] = pd.to_numeric(plot_df[count_col], errors="coerce").fillna(0)
    plot_df = plot_df.sort_values(count_col, ascending=True).tail(10)

    max_val = plot_df[count_col].max()
    colors = [RED if v == max_val else ACCENT for v in plot_df[count_col]]

    fig = go.Figure(
        go.Bar(
            x=plot_df[count_col],
            y=plot_df[name_col].astype(str),
            orientation="h",
            marker=dict(color=colors, line=dict(width=0)),
            text=plot_df[count_col],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x} posts<extra></extra>",
        )
    )
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title=dict(text="🏆 Top Authors by Post Count", x=0.02, font=dict(size=18)),
        xaxis=dict(showgrid=True, gridcolor=GRAY, zeroline=False, title="Posts"),
        yaxis=dict(showgrid=False, title=""),
        height=420,
        bargap=0.25,
    )
    return fig


def timeline_chart(timeline: list[dict]) -> go.Figure:
    df = pd.DataFrame(timeline)
    print("Timeline Response:")
    print(timeline)
    if df.empty:
        return _empty_figure("No timeline data yet — hit '🔄 Sync RSS Feed'")

    # date_candidates = ["date", "day", "timestamp", "created_at", "datetime"]
    # count_candidates = ["post_count", "count", "posts", "total", "num_posts", "value"]
    date_candidates = ["_id", "date", "day", "timestamp", "created_at", "datetime"]
    count_candidates = ["count", "post_count", "posts", "total", "num_posts", "value"]

    date_col = _pick_col(df, date_candidates)
    count_col = _pick_col(df, count_candidates)

    if not date_col or not count_col:
        expected = {"date": date_candidates, "post count": count_candidates}
        return _empty_figure(_shape_debug_message(df, expected))

    plot_df = df[[date_col, count_col]].copy()
    plot_df[date_col] = pd.to_datetime(plot_df[date_col], errors="coerce")
    plot_df[count_col] = pd.to_numeric(plot_df[count_col], errors="coerce").fillna(0)
    plot_df = plot_df.dropna(subset=[date_col]).sort_values(date_col)

    if plot_df.empty:
        return _empty_figure(f"Found columns '{date_col}' / '{count_col}' but couldn't parse any valid rows")

    plot_df["rolling_avg"] = plot_df[count_col].rolling(window=3, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plot_df[date_col],
            y=plot_df[count_col],
            mode="lines+markers",
            name="Daily posts",
            line=dict(color=RED, width=2),
            marker=dict(size=6, color=RED, line=dict(width=1, color=WHITE)),
            fill="tozeroy",
            fillcolor="rgba(225, 6, 0, 0.12)",
            hovertemplate="%{x|%b %d, %Y}<br><b>%{y} posts</b><extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=plot_df[date_col],
            y=plot_df["rolling_avg"],
            mode="lines",
            name="3-day avg",
            line=dict(color=ACCENT, width=2, dash="dot"),
            hovertemplate="%{x|%b %d, %Y}<br>avg %{y:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title=dict(text="📈 Posts Over Time", x=0.02, font=dict(size=18)),
        xaxis=dict(showgrid=False, title=""),
        yaxis=dict(showgrid=True, gridcolor=GRAY, zeroline=False, title="Posts"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=420,
        hovermode="x unified",
    )
    return fig