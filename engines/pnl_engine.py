import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Standard side values after normalization
BUY_ALIASES  = {"buy", "b", "long", "bl", "purchase", "bo", "entry"}
SELL_ALIASES = {"sell", "s", "short", "sl", "sale", "so", "exit", "se"}


# ─── 1. Side Normalizer ───────────────────────────────────────────────────────

def _normalize_side(val) -> str | None:
    """Map any broker's buy/sell label to 'BUY' or 'SELL'."""
    if pd.isna(val):
        return None
    clean = str(val).strip().lower()
    if clean in BUY_ALIASES:
        return "BUY"
    if clean in SELL_ALIASES:
        return "SELL"
    return None


# ─── 2. Normalize Tradebook ───────────────────────────────────────────────────

def normalize_tradebook(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """
    Rename detected columns to TradeFlow standard names,
    coerce types, compute P&L where missing, drop bad rows.
    """
    df = df.copy()

    # --- Rename ---
    rename_map = {v: k for k, v in schema.items() if v}
    df = df.rename(columns=rename_map)
    logger.info(f"Columns after rename: {df.columns.tolist()}")

    # --- Coerce numerics ---
    for col in ["entry_price", "exit_price", "qty", "pnl"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "qty" in df.columns:
        df = df[df["qty"] > 0]

    # --- Parse dates ---
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")

    # --- Normalize side ---
    if "side" in df.columns:
        df["side"] = df["side"].apply(_normalize_side)
    else:
        # If no side column, assume all rows are closed trades
        df["side"] = "UNKNOWN"

    # --- Compute P&L if missing ---
    if "pnl" not in df.columns or df["pnl"].isna().all():
        has_prices = "entry_price" in df.columns and "exit_price" in df.columns
        has_qty    = "qty" in df.columns
        if has_prices and has_qty:
            df["pnl"] = (df["exit_price"] - df["entry_price"]) * df["qty"]
            logger.info("P&L computed from entry/exit prices and qty")
        else:
            logger.warning("Cannot compute P&L — missing price/qty columns")
            df["pnl"] = 0.0

    # --- Trade result: win / loss / breakeven ---
    df["trade_result"] = df["pnl"].apply(
        lambda x: "win" if x > 0 else ("loss" if x < 0 else "breakeven")
    )

    # --- Holding time (minutes) ---
    # Requires an 'exit_time' or we infer same-day
    if "exit_time" in df.columns and "date" in df.columns:
        try:
            df["holding_minutes"] = (
                pd.to_datetime(df["exit_time"]) - df["date"]
            ).dt.total_seconds() / 60
        except Exception:
            df["holding_minutes"] = None
    else:
        df["holding_minutes"] = None

    # --- Drop rows where critical fields are NaN ---
    critical = ["pnl", "date"]
    before = len(df)
    df.dropna(subset=[c for c in critical if c in df.columns], inplace=True)
    dropped = before - len(df)
    if dropped:
        logger.warning(f"Dropped {dropped} rows with missing critical fields")

    # --- Sort by date ascending ---
    if "date" in df.columns:
        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)

    return df


# ─── 3. Equity Curve + Drawdown ───────────────────────────────────────────────

def build_equity_curve(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cum_pnl"] = df["pnl"].cumsum()

    # Anchor peak at 0 — drawdown is always relative to starting capital
    df["peak"] = df["cum_pnl"].cummax().clip(lower=0)

    df["drawdown"] = df["cum_pnl"] - df["peak"]

    df["drawdown_pct"] = df.apply(
        lambda r: (r["drawdown"] / r["peak"] * 100) if r["peak"] > 0 else 0,
        axis=1
    )
    return df