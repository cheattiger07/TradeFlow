import os
import logging
import uuid
from flask import Blueprint, render_template, request, session, current_app
from engines.upload_engine import allowed_file, save_file, load_file
from engines.schema_engine import detect_schema, apply_manual_schema, CONFIDENCE_THRESHOLD
from engines.pnl_engine import normalize_tradebook, build_equity_curve
from engines.analytics_engine import compute_metrics
from engines.behavior_engine import behavior_summary
from engines.recommendation_engine import generate_recommendations
from engines.chart_engine import (
    equity_curve_chart, drawdown_chart,
    win_loss_pie, monthly_pnl_chart, symbol_performance_chart
)

logger = logging.getLogger(__name__)
upload_bp = Blueprint("upload", __name__)

SESSION_KEY = "trade_session"


# ─── Session Helpers ──────────────────────────────────────────────────────────

def get_session_data():
    return session.get(SESSION_KEY)


def clear_session_data():
    old = session.get("trades_path")
    if old and os.path.exists(old):
        try:
            os.remove(old)
        except OSError:
            pass
    session.pop(SESSION_KEY, None)
    session.pop("trades_path", None)
    session.pop("raw_df_path", None)   # used by schema_confirm


# ─── Shared pipeline (used by both routes) ────────────────────────────────────

def _run_pipeline(df, schema, confidence):
    """
    Normalize → equity curve → analytics → charts.
    Returns the render_template response directly.
    """
    df = normalize_tradebook(df, schema)
    df = build_equity_curve(df)

    metrics  = compute_metrics(df)
    behavior = behavior_summary(df)
    insights = generate_recommendations(metrics, behavior)

    equity_chart = equity_curve_chart(df)
    drawdown     = drawdown_chart(df)
    pie          = win_loss_pie(df)
    monthly      = monthly_pnl_chart(df)
    symbols      = symbol_performance_chart(df)

    # Store analytics in session
    session[SESSION_KEY] = {
        "metrics":   metrics,
        "behavior":  behavior,
        "insights":  insights,
        "row_count": len(df),
    }

    # Store df as parquet for export routes
    export_folder = current_app.config["EXPORT_FOLDER"]
    parquet_path  = os.path.join(export_folder, f"trades_{uuid.uuid4().hex[:8]}.parquet")
    df.to_parquet(parquet_path, index=False)
    session["trades_path"] = parquet_path

    preview = df.head(50).to_html(
        classes="table",
        index=False,
        border=0
    )

    return render_template(
        "preview.html",
        preview=preview,
        metrics=metrics,
        behavior=behavior,
        insights=insights,
        equity_chart=equity_chart,
        drawdown=drawdown,
        pie=pie,
        monthly=monthly,
        symbols=symbols,
        schema_confidence=round(confidence * 100),
        total_rows=len(df),
    )


# ─── Upload Route ─────────────────────────────────────────────────────────────

@upload_bp.route("/", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        try:
            # 1. File presence
            file = request.files.get("file")
            if not file or file.filename == "":
                return render_template("index.html", error="No file selected.")

            # 2. Extension check
            allowed = current_app.config["ALLOWED_EXTENSIONS"]
            if not allowed_file(file.filename, allowed):
                return render_template(
                    "index.html",
                    error=f"Unsupported file type. Allowed: {', '.join(allowed)}"
                )

            # 3. Clear previous session only after validation passes
            clear_session_data()

            # 4. Save
            path = save_file(file, current_app.config["UPLOAD_FOLDER"])
            logger.info(f"File saved: {path}")

            # 5. Load
            df, error = load_file(path)
            if error:
                return render_template("index.html", error=f"File error: {error}")
            if df.empty:
                return render_template("index.html", error="Uploaded file has no data rows.")

            # 6. Schema detection
            schema, confidence = detect_schema(df.columns)

            if confidence < CONFIDENCE_THRESHOLD:
                # Save raw df so schema_confirm can pick it up
                export_folder = current_app.config["EXPORT_FOLDER"]
                raw_path = os.path.join(export_folder, f"raw_{uuid.uuid4().hex[:8]}.parquet")
                df.to_parquet(raw_path, index=False)
                session["raw_df_path"] = raw_path
                session["raw_schema"]  = schema

                return render_template(
                    "schema_map.html",
                    columns=df.columns.tolist(),
                    schema=schema,
                    confidence=round(confidence, 2)
                )

            # 7. Run pipeline
            return _run_pipeline(df, schema, confidence)

        except Exception:
            logger.exception("Upload pipeline failed")
            return render_template("errors/500.html"), 500

    # GET
    clear_session_data()
    return render_template("index.html")


# ─── Schema Confirm Route ─────────────────────────────────────────────────────

@upload_bp.route("/schema-confirm", methods=["POST"])
def schema_confirm():
    try:
        # 1. Retrieve saved raw df
        raw_path = session.get("raw_df_path")
        if not raw_path or not os.path.exists(raw_path):
            return render_template(
                "index.html",
                error="Session expired during column mapping. Please re-upload."
            )

        import pandas as pd
        df = pd.read_parquet(raw_path)

        # 2. Build merged schema from auto-detected + user overrides
        raw_schema  = session.get("raw_schema", {})
        user_mapping = {k: v for k, v in request.form.items() if v and k != "csrf_token"}
        schema = apply_manual_schema(raw_schema, user_mapping)

        # 3. Validate at least the critical fields are mapped
        critical = {"symbol", "date", "pnl"}
        has_prices = schema.get("entry_price") and schema.get("exit_price") and schema.get("qty")
        has_pnl    = bool(schema.get("pnl"))
        if not has_pnl and not has_prices:
            return render_template(
                "schema_map.html",
                columns=df.columns.tolist(),
                schema=schema,
                confidence=0.0,
                error="Map either 'PNL' or both 'Entry Price' + 'Exit Price' + 'Qty' to continue."
            )

        # 4. Clean up raw parquet
        try:
            os.remove(raw_path)
        except OSError:
            pass
        session.pop("raw_df_path", None)
        session.pop("raw_schema", None)

        # 5. Run full pipeline with manual schema (confidence=1.0 since user confirmed)
        return _run_pipeline(df, schema, confidence=1.0)

    except Exception:
        logger.exception("Schema confirm failed")
        return render_template("errors/500.html"), 500