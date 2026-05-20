import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Trades/day threshold for overtrading flag
OVERTRADING_THRESHOLD = 6

# Minimum consecutive loss→bigger_qty occurrences for revenge flag
REVENGE_THRESHOLD = 2


def _require_date(df: pd.DataFrame):
    if "date" not in df.columns:
        raise ValueError("DataFrame missing 'date' column")


# ─── Weekday Analysis ─────────────────────────────────────────────────────────

def best_worst_weekday(df: pd.DataFrame) -> tuple:
    _require_date(df)
    temp = df.copy()

    # Create weekday column FIRST, then categorize
    temp["weekday"] = temp["date"].dt.day_name()

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    temp["weekday"] = pd.Categorical(temp["weekday"], categories=order, ordered=True)

    weekday_pnl = temp.groupby("weekday", observed=False)["pnl"].sum()

    # Drop days with zero trades entirely
    weekday_pnl = weekday_pnl[weekday_pnl != 0]

    if len(weekday_pnl) < 2:
        only = weekday_pnl.index[0] if len(weekday_pnl) == 1 else None
        return only, only, weekday_pnl.round(2).to_dict()

    return (
        weekday_pnl.idxmax(),
        weekday_pnl.idxmin(),
        weekday_pnl.round(2).to_dict()
    )


# ─── Streak Analysis ──────────────────────────────────────────────────────────

def streak_analysis(df: pd.DataFrame) -> dict:
    """
    Returns max win streak, max loss streak, and current streak.
    Breakeven trades are treated as neutral (reset neither counter).
    """
    pnl = df["pnl"].tolist()
    max_win = max_loss = cur_win = cur_loss = 0
    current_streak = 0
    current_type   = None

    for x in pnl:
        if x > 0:
            cur_win  += 1
            cur_loss  = 0
            current_streak = cur_win
            current_type   = "win"
        elif x < 0:
            cur_loss += 1
            cur_win   = 0
            current_streak = cur_loss
            current_type   = "loss"
        # breakeven: don't reset either counter

        max_win  = max(max_win,  cur_win)
        max_loss = max(max_loss, cur_loss)

    return {
        "max_win_streak":  max_win,
        "max_loss_streak": max_loss,
        "current_streak":  current_streak,
        "current_type":    current_type,   # "win" | "loss" | None
    }


# ─── Overtrading Detection ────────────────────────────────────────────────────

def overtrading_detection(df: pd.DataFrame, threshold: int = OVERTRADING_THRESHOLD) -> dict:
    """
    Group by calendar date (not datetime) to correctly count intraday trades.
    Returns flag + avg trades/day + worst day count.
    """
    _require_date(df)
    trade_date = df["date"].dt.date
    trades_per_day = df.groupby(trade_date).size()

    avg_per_day  = round(trades_per_day.mean(), 1)
    max_per_day  = int(trades_per_day.max())
    flag         = bool((trades_per_day > threshold).any())

    return {
        "overtrading":        flag,
        "avg_trades_per_day": avg_per_day,
        "max_trades_per_day": max_per_day,
        "overtrading_days":   int((trades_per_day > threshold).sum()),
    }


# ─── Revenge Trading Detection ────────────────────────────────────────────────

def revenge_trading_detection(df: pd.DataFrame, threshold: int = REVENGE_THRESHOLD) -> dict:
    """
    Revenge trading: loss followed by a LARGER qty trade within the same day.
    Requires `threshold` consecutive occurrences to reduce false positives.
    """
    _require_date(df)
    df  = df.reset_index(drop=True)
    qty = df["qty"].tolist() if "qty" in df.columns else []
    pnl = df["pnl"].tolist()
    dates = df["date"].dt.date.tolist()

    if not qty:
        return {"revenge_trading": False, "revenge_count": 0}

    count = 0
    for i in range(len(df) - 1):
        same_day   = dates[i] == dates[i + 1]
        is_loss    = pnl[i] < 0
        larger_qty = qty[i + 1] > qty[i] * 1.2   # >20% bigger position
        if is_loss and larger_qty and same_day:
            count += 1
    if count >= threshold:
        logger.warning(f"Possible revenge trading detected ({count})")
    return {
        "revenge_trading": count >= threshold,
        "revenge_count":   count,
    }


# ─── Holding Time Analysis ────────────────────────────────────────────────────

def holding_time_summary(df: pd.DataFrame) -> dict:
    """Summarize holding times if available."""
    if "holding_minutes" not in df.columns or df["holding_minutes"].isna().all():
        return {"avg_holding_minutes": None, "median_holding_minutes": None}

    hm = df["holding_minutes"].dropna()
    return {
        "avg_holding_minutes":    round(hm.mean(), 1),
        "median_holding_minutes": round(hm.median(), 1),
    }


# ─── Master Summary ───────────────────────────────────────────────────────────

def behavior_summary(df: pd.DataFrame) -> dict:
    """
    Aggregate all behavioral signals into a single flat dict.
    All keys are snake_case for consistency with recommendation_engine.
    """
    df = df.sort_values("date").reset_index(drop=True)
    best_day, worst_day, weekday_pnl = best_worst_weekday(df)
    streaks   = streak_analysis(df)
    overtrade = overtrading_detection(df)
    revenge   = revenge_trading_detection(df)
    holding   = holding_time_summary(df)

    summary = {
        "best_day":    best_day,
        "worst_day":   worst_day,
        "weekday_pnl": weekday_pnl,
        **streaks,
        **overtrade,
        **revenge,
        **holding,
    }

    logger.info(f"Behavior summary: {summary}")
    return summary