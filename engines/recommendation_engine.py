import logging

logger = logging.getLogger(__name__)

# ─── Severity levels ──────────────────────────────────────────────────────────
# Each insight is {"text": str, "level": "info" | "warning" | "danger"}

def _insight(text: str, level: str = "info") -> dict:
    return {"text": text, "level": level}


# ─── Rule Engine ──────────────────────────────────────────────────────────────

def generate_recommendations(metrics: dict, behavior: dict) -> list[dict]:
    """
    Rule-based insight engine.
    Accepts both metrics and behavior dicts for full-picture analysis.
    Returns a list of insight dicts with text + severity level.
    """
    insights = []
    seen = set()  # deduplication

    def add(text: str, level: str = "info"):
        if text not in seen:
            seen.add(text)
            insights.append(_insight(text, level))

    # ── Win Rate ──────────────────────────────────────────────────────────────
    win_rate = metrics.get("win_rate", 0)
    if win_rate < 40:
        add(f"Win rate is {win_rate:.1f}% — review your entry criteria.", "danger")
    elif win_rate < 50:
        add(f"Win rate is below 50% ({win_rate:.1f}%) — focus on setup quality.", "warning")
    elif win_rate >= 65:
        add(f"Strong win rate at {win_rate:.1f}%. Maintain your discipline.", "info")

    # ── Profit Factor ─────────────────────────────────────────────────────────
    pf = metrics.get("profit_factor", 0)
    if pf < 1.0:
        add("Profit factor below 1.0 — you're losing more than you're making.", "danger")
    elif pf < 1.5:
        add(f"Profit factor of {pf:.2f} is marginal. Work on cutting losses earlier.", "warning")
    elif pf >= 2.0:
        add(f"Excellent profit factor of {pf:.2f}.", "info")

    # ── Expectancy ────────────────────────────────────────────────────────────
    expectancy = metrics.get("expectancy", 0)
    if expectancy < 0:
        add("Negative expectancy — this system loses money over time.", "danger")

    # ── Max Drawdown ──────────────────────────────────────────────────────────
    max_dd = metrics.get("max_drawdown", 0)
    total_pnl = metrics.get("total_pnl", 1) or 1
    dd_ratio = abs(max_dd) / abs(total_pnl) if total_pnl else 0
    if abs(max_dd) > 0 and dd_ratio > 0.5:
        add(f"Max drawdown (₹{abs(max_dd):,.0f}) is over 50% of total profit. "
            f"Review position sizing.", "danger")
    elif abs(max_dd) > 0 and dd_ratio > 0.25:
        add(f"Max drawdown is significant (₹{abs(max_dd):,.0f}). "
            f"Consider tighter stop losses.", "warning")

    # ── Avg Loss vs Avg Gain ──────────────────────────────────────────────────
    avg_gain = metrics.get("avg_gain", 0)
    avg_loss = abs(metrics.get("avg_loss", 0))
    if avg_gain > 0 and avg_loss > 0:
        rr = avg_gain / avg_loss
        if rr < 1.0:
            add(f"Average loss (₹{avg_loss:,.0f}) exceeds average gain (₹{avg_gain:,.0f}). "
                f"Your R:R is below 1:1.", "warning")

    # ── Worst Day ─────────────────────────────────────────────────────────────
    worst_day = behavior.get("worst_day")
    if worst_day:
        add(f"You lose most on {worst_day}s. Consider reducing size or skipping {worst_day}s.", "warning")

    # ── Best Day ──────────────────────────────────────────────────────────────
    best_day = behavior.get("best_day")
    if best_day:
        add(f"Your best trading day is {best_day}. Prioritize high-quality setups on {best_day}s.", "info")

    # ── Overtrading ───────────────────────────────────────────────────────────
    if behavior.get("overtrading"):
        avg_trades = behavior.get("avg_trades_per_day", 0)
        add(f"Overtrading detected — averaging {avg_trades:.0f} trades/day. "
            f"More trades ≠ more profit.", "warning")

    # ── Revenge Trading ───────────────────────────────────────────────────────
    if behavior.get("revenge_trading"):
        add("Revenge trading pattern detected — losses followed by rapid re-entries. "
            "Step away after a losing trade.", "danger")

    # ── Loss Streak ───────────────────────────────────────────────────────────
    max_loss_streak = behavior.get("max_loss_streak", 0)
    if max_loss_streak >= 5:
        add(f"Max loss streak of {max_loss_streak} trades. "
            f"Review whether you're forcing trades.", "danger")
    elif max_loss_streak >= 3:
        add(f"Loss streak of {max_loss_streak} trades detected. "
            f"Pause and review your setup criteria.", "warning")

    # ── Win Streak ────────────────────────────────────────────────────────────
    max_win_streak = behavior.get("max_win_streak", 0)
    if max_win_streak >= 5:
        add(f"Win streak of {max_win_streak} — be cautious of overconfidence.", "warning")

    # ── Fallback ──────────────────────────────────────────────────────────────
    if not insights:
        add("Trading behavior looks stable. Keep following your system.", "info")

    logger.info(f"Generated {len(insights)} insights")
    return insights