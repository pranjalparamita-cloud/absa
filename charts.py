"""
charts.py — All Plotly dashboard figures (transparent backgrounds
so they blend into the glass cards).
---------------------------------------------------------------
fig_donut()    overall sentiment split
fig_bar()      per-aspect positive/neutral/negative breakdown
fig_sunburst() aspects -> sentiment hierarchy
fig_radar()    aspect positivity scores (0-100)
fig_timeline() line chart: monthly positivity trend (needs dates)
fig_rolling()  line chart: rolling sentiment over review order (fallback)
fig_ratings()  bar chart: star-rating distribution (needs ratings)
"""
import pandas as pd
import plotly.graph_objects as go

from config import POS_COLOR, NEG_COLOR, NEU_COLOR


def style_fig(fig, height=380):
    """Apply the glass-friendly transparent style to any figure."""
    fig.update_layout(
        height=height, margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Poppins, sans-serif", color="#2b2350", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def fig_donut(overall):
    fig = go.Figure(go.Pie(
        labels=["Positive", "Neutral", "Negative"],
        values=[overall["positive"], overall["neutral"], overall["negative"]],
        hole=0.58, marker=dict(colors=[POS_COLOR, NEU_COLOR, NEG_COLOR],
                               line=dict(color="white", width=3)),
        textinfo="percent", hoverinfo="label+value",
    ))
    fig.update_layout(title="Overall Sentiment Split", title_font=dict(size=14, color="#4c1d95"))
    return style_fig(fig, 340)


def fig_bar(aspect_data):
    aspects = list(aspect_data.keys())
    fig = go.Figure()
    fig.add_bar(name="Positive", x=aspects, y=[aspect_data[a]["positive"] for a in aspects], marker_color=POS_COLOR)
    fig.add_bar(name="Neutral", x=aspects, y=[aspect_data[a]["neutral"] for a in aspects], marker_color=NEU_COLOR)
    fig.add_bar(name="Negative", x=aspects, y=[aspect_data[a]["negative"] for a in aspects], marker_color=NEG_COLOR)
    fig.update_layout(barmode="group", title="Aspect-Level Sentiment Breakdown",
                      title_font=dict(size=14, color="#4c1d95"), xaxis_tickangle=-25)
    return style_fig(fig, 420)


def fig_sunburst(aspect_data, total):
    labels, parents, values, colors = ["All Reviews"], [""], [total], ["#c4b5fd"]
    for a, d in aspect_data.items():
        a_total = max(1, d["positive"] + d["neutral"] + d["negative"])
        labels.append(a); parents.append("All Reviews"); values.append(a_total); colors.append("#ddd6fe")
        for s, c in (("positive", POS_COLOR), ("neutral", NEU_COLOR), ("negative", NEG_COLOR)):
            labels.append(f"{a} • {s.capitalize()}"); parents.append(a)
            values.append(max(0, d[s])); colors.append(c)
    fig = go.Figure(go.Sunburst(labels=labels, parents=parents, values=values,
                                marker=dict(colors=colors, line=dict(color="white", width=2)),
                                branchvalues="total", hoverinfo="label+value"))
    fig.update_layout(title="Sunburst: Aspects → Sentiment", title_font=dict(size=14, color="#4c1d95"))
    return style_fig(fig, 460)


def fig_radar(aspect_data):
    aspects = list(aspect_data.keys())
    scores = []
    for a in aspects:
        d = aspect_data[a]
        t = max(1, d["positive"] + d["neutral"] + d["negative"])
        scores.append(round((d["positive"] + 0.5 * d["neutral"]) / t * 100, 1))
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=scores + scores[:1], theta=aspects + aspects[:1],
                                  fill="toself", name="Positivity score",
                                  line=dict(color="#9333ea", width=3),
                                  fillcolor="rgba(147,51,234,0.18)",
                                  marker=dict(color="#ec4899", size=7)))
    fig.update_layout(title="Radar: Aspect Positivity Score (0–100)",
                      title_font=dict(size=14, color="#4c1d95"),
                      polar=dict(radialaxis=dict(visible=True, range=[0, 100]),
                                 bgcolor="rgba(0,0,0,0)"))
    return style_fig(fig, 440)


def _line_trace(fig, x, y, name):
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name=name,
                             line=dict(color="#7c3aed", width=3),
                             marker=dict(size=8, color="#ec4899",
                                         line=dict(color="white", width=2)),
                             fill="tozeroy", fillcolor="rgba(168,85,247,0.12)"))
    return fig


def fig_timeline(dates, sentiments, title="Monthly Positivity Trend (% positive)"):
    """Line chart of % positive reviews per month. Returns None if <2 months."""
    df = pd.DataFrame({"date": pd.to_datetime(dates, errors="coerce"),
                       "pos": [1 if s == "positive" else 0 for s in sentiments]})
    df = df.dropna(subset=["date"])
    if df.empty:
        return None
    df["month"] = df["date"].dt.to_period("M").astype(str)
    g = df.groupby("month")["pos"].mean().mul(100).round(1)
    if len(g) < 2:
        return None
    fig = go.Figure()
    _line_trace(fig, list(g.index), list(g.values), "Positive %")
    fig.update_layout(title=title, title_font=dict(size=13, color="#4c1d95"),
                      yaxis_title="Positive %", yaxis_range=[0, 100])
    return style_fig(fig, 380)


def fig_rolling(sentiments, title="Sentiment Trend Across Reviews (rolling average)"):
    """Fallback line chart when no dates exist: rolling positivity over review order."""
    scores = [{"positive": 1.0, "neutral": 0.5, "negative": 0.0}[s] for s in sentiments]
    s = pd.Series(scores)
    window = max(3, min(20, len(s) // 10 or 3))
    rolled = (s.rolling(window, min_periods=1).mean() * 100).round(1)
    fig = go.Figure()
    _line_trace(fig, list(range(1, len(rolled) + 1)), list(rolled.values), "Positive %")
    fig.update_layout(title=title, title_font=dict(size=13, color="#4c1d95"),
                      xaxis_title="Review #", yaxis_title="Positive %", yaxis_range=[0, 100])
    return style_fig(fig, 380)


def fig_ratings(ratings):
    """Bar chart of star-rating distribution."""
    vc = pd.Series(ratings).dropna().value_counts().sort_index()
    fig = go.Figure()
    fig.add_bar(x=[str(v) for v in vc.index], y=list(vc.values), name="Reviews",
                marker_color=["#f43f5e", "#fb923c", "#a78bfa", "#34d399", "#10b981"][-len(vc):] or "#9333ea")
    fig.update_layout(title="Rating Distribution", title_font=dict(size=14, color="#4c1d95"),
                      xaxis_title="Stars", yaxis_title="Reviews")
    return style_fig(fig, 340)
