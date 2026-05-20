import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252


def compute_metrics(df: pd.DataFrame) -> dict:
    """
    Compute full performance metrics from a normalized trade DataFrame.
    All dict keys are snake_case to match recommendation_engine and templates.
    """
    pnl = df["pnl"].dropna()

    if pnl.empty:
        logger.warning("Empty P&L series — returning zero metrics")
        return _empty_metrics()

    wins   = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    total  = len(pnl)

    # ── Core counts ──────────────────────────────────────────────────────────
    total_trades  = total
    win_count     = len(wins)
    loss_count    = len(losses)
    breakeven_count = total - win_count - loss_count

    # ── P&L ──────────────────────────────────────────────────────────────────
    total_pnl  = round(pnl.sum(), 2)
    avg_gain   = round(wins.mean(), 2)   if win_count  else 0.0
    avg_loss   = round(losses.mean(), 2) if loss_count else 0.0  # negative value

    largest_win  = round(wins.max(), 2)  if win_count  else 0.0
    largest_loss = round(losses.min(), 2) if loss_count else 0.0  # most negative

    # ── Rates ─────────────────────────────────────────────────────────────────
    win_rate = round(win_count / total * 100, 2) if total else 0.0

    # ── Profit Factor ─────────────────────────────────────────────────────────
    gross_profit = wins.sum()
    gross_loss   = abs(losses.sum())
    if gross_loss == 0:
        profit_factor = float("inf") if gross_profit > 0 else 0.0
    else:
        profit_factor = round(gross_profit / gross_loss, 2)

    # ── R:R Ratio ─────────────────────────────────────────────────────────────
    rr_ratio = round(avg_gain / abs(avg_loss), 2) if avg_loss != 0 else 0.0

    # ── Expectancy ────────────────────────────────────────────────────────────
    # Expectancy = (WinRate × AvgGain) + (LossRate × AvgLoss)
    # avg_loss is already negative so we add it
    win_rate_dec  = win_rate / 100
    loss_rate_dec = 1 - win_rate_dec
    expectancy    = round((win_rate_dec * avg_gain) + (loss_rate_dec * avg_loss), 2)

    # ── Max Drawdown ─────────────────────────────────────────────────────────
    if "drawdown" in df.columns:
        max_drawdown = round(df["drawdown"].min(), 2)
    else:
        cum = pnl.cumsum()
        max_drawdown = round((cum - cum.cummax()).min(), 2)

    # ── Sharpe Ratio (annualized, daily P&L as proxy) ────────────────────────
    if "date" in df.columns:
        df = df.sort_values("date")
        daily_pnl = df.groupby(df["date"].dt.date)["pnl"].sum()
    else:
        daily_pnl = pnl

    sharpe = 0.0
    if daily_pnl.std(ddof=0) != 0:
        sharpe = round(
            (daily_pnl.mean() / daily_pnl.std(ddof=0)) * np.sqrt(TRADING_DAYS_PER_YEAR),
            2
        )

    metrics = {
        # Counts
        "total_trades":     total_trades,
        "win_count":        win_count,
        "loss_count":       loss_count,
        "breakeven_count":  breakeven_count,
        # P&L
        "total_pnl":        total_pnl,
        "avg_gain":         avg_gain,
        "avg_loss":         avg_loss,          # negative
        "largest_win":      largest_win,
        "largest_loss":     largest_loss,      # negative
        # Ratios
        "win_rate":         win_rate,
        "profit_factor":    profit_factor,
        "rr_ratio":         rr_ratio,
        "expectancy":       expectancy,
        # Risk
        "max_drawdown":     max_drawdown,      # negative
        "sharpe_ratio":     sharpe,
    }

    logger.info(f"Metrics computed: {total_trades} trades | "
                f"P&L={total_pnl} | WR={win_rate}% | PF={profit_factor}")
    return metrics


def _empty_metrics() -> dict:
    keys = [
        "total_trades", "win_count", "loss_count", "breakeven_count",
        "total_pnl", "avg_gain", "avg_loss", "largest_win", "largest_loss",
        "win_rate", "profit_factor", "rr_ratio", "expectancy",
        "max_drawdown", "sharpe_ratio"
    ]
    return {k: 0 for k in keys}