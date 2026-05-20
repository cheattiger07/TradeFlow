import logging
from difflib import get_close_matches

logger = logging.getLogger(__name__)

# ─── Broker-aware alias map ────────────────────────────────────────────────────
# Covers: Zerodha, Groww, Upstox, Angel One, generic tradebooks
COLUMN_ALIASES = {
    "symbol": [
        "symbol", "ticker", "stock", "scrip", "instrument",
        "tradingsymbol", "trading_symbol", "contract", "name",
        "stock_name", "security"
    ],
    "side": [
        "side", "buy_sell", "action", "trade_type", "type",
        "order_type", "transaction_type", "b/s", "buysell",
        "direction", "trade_side"
    ],
    "qty": [
        "qty", "quantity", "shares", "units", "volume",
        "trade_quantity", "traded_qty", "no_of_shares",
        "order_quantity", "filled_qty", "executed_qty"
    ],
    "entry_price": [
        "entry", "entry_price", "buy_price", "average_price",
        "avg_price", "purchase_price", "open_price",
        "execution_price", "trade_price", "price",
        "buy_avg", "buying_price"
    ],
    "exit_price": [
        "exit", "exit_price", "sell_price", "close_price",
        "selling_price", "sell_avg", "closing_price"
    ],
    "pnl": [
        "pnl", "p&l", "profit", "net_profit", "profit_loss",
        "net_pnl", "realized_pnl", "realized_pl", "gain_loss",
        "net_gain", "profit_and_loss", "net_amount"
    ],
    "date": [
        "date", "trade_date", "order_date", "execution_date",
        "transaction_date", "entry_date", "created_at",
        "timestamp", "time", "datetime", "trade_time"
    ],
    "strategy": [
        "strategy", "tag", "setup", "notes", "remarks",
        "comment", "strategy_tag", "trade_setup", "category",
        "trade_tag", "label"
    ],
}

# Minimum alias match cutoff for fuzzy matching
FUZZY_CUTOFF = 0.75
# Confidence: fraction of critical columns that were matched
CRITICAL_COLUMNS = {"symbol", "side", "qty", "entry_price", "exit_price", "date"}
CONFIDENCE_THRESHOLD = 0.7

# ─── Normalizer ───────────────────────────────────────────────────────────────

def _normalize(col: str) -> str:
    """Lowercase, strip, replace spaces/dashes with underscores."""
    return col.strip().lower().replace(" ", "_").replace("-", "_")


# ─── Core Detection ───────────────────────────────────────────────────────────

def detect_schema(
    columns,
    fuzzy_cutoff: float = FUZZY_CUTOFF
) -> tuple[dict, float]:
    """
    Map raw column names to TradeFlow standard field names.

    Returns:
        schema      : dict mapping standard_field -> original_column_name (or None)
        confidence  : float 0.0–1.0 based on critical column hit rate
    """
    original_cols = list(columns)
    normalized_cols = [_normalize(c) for c in original_cols]
    norm_to_orig = dict(zip(normalized_cols, original_cols))

    schema = {}
    used_columns = set()  # prevent one raw col mapping to two standard fields

    for std_field, aliases in COLUMN_ALIASES.items():
        matched_col = None

        # Pass 1 — exact match against normalized aliases
        for alias in aliases:
            norm_alias = _normalize(alias)
            if norm_alias in normalized_cols and norm_alias not in used_columns:
                matched_col = norm_to_orig[norm_alias]
                used_columns.add(norm_alias)
                logger.debug(f"Exact match: {std_field} → '{matched_col}'")
                break

        # Pass 2 — fuzzy match if exact failed
        if matched_col is None:
            remaining = [c for c in normalized_cols if c not in used_columns]
            for alias in aliases:
                norm_alias = _normalize(alias)
                fuzzy = get_close_matches(norm_alias, remaining, n=1, cutoff=fuzzy_cutoff)
                if fuzzy:
                    matched_col = norm_to_orig[fuzzy[0]]
                    used_columns.add(fuzzy[0])
                    logger.debug(f"Fuzzy match: {std_field} → '{matched_col}' "
                                 f"(via alias '{alias}')")
                    break

        schema[std_field] = matched_col

    # ─── Confidence Score ─────────────────────────────────────────────────────
    matched_critical = sum(
        1 for col in CRITICAL_COLUMNS if schema.get(col) is not None
    )
    confidence = matched_critical / len(CRITICAL_COLUMNS)

    # Log summary
    missing = [f for f in CRITICAL_COLUMNS if schema.get(f) is None]
    if missing:
        logger.warning(f"Schema detection: missing critical fields: {missing}")
    logger.info(f"Schema confidence: {confidence:.0%} | Mapped: {schema}")
    if len(set(original_cols)) != len(original_cols):
        logger.warning("Duplicate column names detected.")
    return schema, confidence


# ─── Manual Override ──────────────────────────────────────────────────────────

def apply_manual_schema(raw_schema: dict, user_mapping: dict) -> dict:
    """
    Merge user-provided manual column mapping over auto-detected schema.
    Called when confidence < threshold and user submits schema_map form.

    user_mapping: { "symbol": "Stock Name", "pnl": "Net P&L", ... }
    """
    merged = dict(raw_schema)
    for std_field, user_col in user_mapping.items():
        if std_field in merged and user_col and str(user_col).strip():
            merged[std_field] = user_col
            logger.info(f"Manual override: {std_field} → '{user_col}'")
    return merged