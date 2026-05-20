import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# ─── Theme ────────────────────────────────────────────────────────────────────
THEME = "plotly_dark"
WIN_COLOR  = "#26a69a"   # teal
LOSS_COLOR = "#ef5350"   # red
LINE_COLOR = "#5c6bc0"   # indigo


def _to_html(fig) -> str:
    """Consistent export: no full HTML, no duplicate Plotly.js."""
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"responsive": True})


# ─── 1. Equity Curve ─────────────────────────────────────────────────────────

def equity_curve_chart(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    fig = px.line(
        df, x="date", y="cum_pnl",
        title="Equity Curve",
        labels={"cum_pnl": "Cumulative P&L (₹)", "date": "Date"},
        template=THEME,
        color_discrete_sequence=[LINE_COLOR],
    )
    fig.update_traces(line_width=2)
    fig.update_layout(margin=dict(l=40, r=20, t=50, b=40))
    return _to_html(fig)


# ─── 2. Drawdown Chart ────────────────────────────────────────────────────────

def drawdown_chart(df: pd.DataFrame) -> str:
    # Use pre-computed drawdown from pnl_engine — don't recompute
    if df.empty:
        return ""
    col = "drawdown" if "drawdown" in df.columns else None
    if col is None:
        logger.warning("Drawdown column missing — skipping chart")
        return ""

    fig = px.area(
        df, x="date", y=col,
        title="Drawdown",
        labels={col: "Drawdown (₹)", "date": "Date"},
        template=THEME,
        color_discrete_sequence=[LOSS_COLOR],
    )
    fig.update_layout(margin=dict(l=40, r=20, t=50, b=40))
    return _to_html(fig)


# ─── 3. Win / Loss Pie ───────────────────────────────────────────────────────

def win_loss_pie(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    wins      = (df["pnl"] > 0).sum()
    losses    = (df["pnl"] < 0).sum()
    breakeven = (df["pnl"] == 0).sum()

    labels = ["Wins", "Losses"]
    values = [wins, losses]
    colors = [WIN_COLOR, LOSS_COLOR]

    if breakeven > 0:
        labels.append("Breakeven")
        values.append(breakeven)
        colors.append("#9e9e9e")

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker_colors=colors,
        hole=0.4,
        textinfo="label+percent"
    ))
    fig.update_layout(
        title="Win / Loss Distribution",
        template=THEME,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return _to_html(fig)


# ─── 4. Monthly P&L Bar Chart ─────────────────────────────────────────────────

def monthly_pnl_chart(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    temp = df.copy()
    if "date" not in df.columns:
        return ""
    temp["month"] = temp["date"].dt.to_period("M").astype(str)
    monthly = temp.groupby("month")["pnl"].sum().reset_index()
    monthly["color"] = monthly["pnl"].apply(
        lambda x: WIN_COLOR if x >= 0 else LOSS_COLOR
    )

    fig = go.Figure(go.Bar(
        x=monthly["month"],
        y=monthly["pnl"],
        marker_color=monthly["color"],
        text=monthly["pnl"].apply(lambda x: f"₹{x:,.0f}"),
        textposition="outside",
    ))
    fig.update_layout(
        title="Monthly P&L",
        xaxis_title="Month",
        yaxis_title="P&L (₹)",
        template=THEME,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return _to_html(fig)


# ─── 5. Symbol Performance ───────────────────────────────────────────────────

def symbol_performance_chart(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    if "symbol" not in df.columns:
        logger.warning("No 'symbol' column — skipping symbol chart")
        return ""

    sym = (
        df.groupby("symbol")["pnl"]
        .sum()
        .reset_index()
        .assign(abs_pnl=lambda x: x["pnl"].abs())
        .sort_values("abs_pnl")   # biggest movers first
    )
    sym["color"] = sym["pnl"].apply(lambda x: WIN_COLOR if x >= 0 else LOSS_COLOR)

    fig = go.Figure(go.Bar(
        x=sym["pnl"],
        y=sym["symbol"],
        orientation="h",
        marker_color=sym["color"],
        text=sym["pnl"].apply(lambda x: f"₹{x:,.0f}"),
        textposition="outside",
    ))
    fig.update_layout(
        title="Symbol Performance",
        xaxis_title="Total P&L (₹)",
        template=THEME,
        margin=dict(l=100, r=40, t=50, b=40),
        height=max(300, len(sym) * 35),
    )
    return _to_html(fig)


# ─── 6. Calendar Heatmap ─────────────────────────────────────────────────────

def calendar_heatmap(df: pd.DataFrame) -> str:
    """Daily P&L heatmap — shows which calendar days were profitable."""
    if df.empty:
        return ""
    if "date" not in df.columns:
        return ""
    temp = df.copy()
    temp["day"] = temp["date"].dt.date
    daily = temp.groupby("day")["pnl"].sum().reset_index()
    daily["day"] = pd.to_datetime(daily["day"])

    fig = go.Figure(go.Scatter(
        x=daily["day"],
        y=["P&L"] * len(daily),
        mode="markers",
        marker=dict(
            size=14,
            color=daily["pnl"],
            colorscale=[[0, LOSS_COLOR], [0.5, "#333"], [1, WIN_COLOR]],
            showscale=True,
            colorbar=dict(title="P&L (₹)"),
            symbol="square",
        ),
        text=daily.apply(
            lambda r: f"{r['day'].strftime('%b %d')}: ₹{r['pnl']:,.0f}", axis=1
        ),
        hoverinfo="text",
    ))
    fig.update_layout(
        title="Daily P&L Calendar",
        template=THEME,
        xaxis_title="Date",
        yaxis=dict(showticklabels=False),
        margin=dict(l=20, r=20, t=50, b=40),
        height=180,
    )
    return _to_html(fig)