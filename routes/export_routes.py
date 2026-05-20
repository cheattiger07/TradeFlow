import os
import logging
import pandas as pd
from flask import Blueprint, send_file, render_template, session
from engines.export_engine import export_excel, export_pdf

logger = logging.getLogger(__name__)
export_bp = Blueprint("export", __name__)


def _load_trade_df():
    """Load the parquet trades file for the current session."""
    path = session.get("trades_path")
    if not path or not os.path.exists(path):
        return None, "No trade data found. Please upload a file first."
    try:
        return pd.read_parquet(path), None
    except Exception as e:
        logger.exception("Failed to load trade parquet")
        return None, "Trade data could not be loaded."


def _load_session_data():
    """Load analytics summary from session."""
    data = session.get("trade_session")
    if not data:
        return None, "Session expired. Please re-upload your file."
    return data, None


@export_bp.route("/download/excel")
def download_excel():
    df, err = _load_trade_df()
    if err:
        return render_template("errors/session_expired.html", error=err), 400

    session_data, err = _load_session_data()
    if err:
        return render_template("errors/session_expired.html", error=err), 400

    try:
        path = export_excel(df, session_data["metrics"], session_data["behavior"])
        return send_file(
            path,
            as_attachment=True,
            download_name="tradeflow_report.xlsx",          # ← explicit name
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception:
        logger.exception("Excel export failed")
        return render_template("errors/500.html"), 500


@export_bp.route("/download/pdf")
def download_pdf():
    session_data, err = _load_session_data()
    if err:
        return render_template("errors/session_expired.html", error=err), 400

    try:
        path = export_pdf(
            session_data["metrics"],
            session_data["behavior"],
            session_data["insights"]
        )
        return send_file(
            path,
            as_attachment=True,
            download_name="tradeflow_report.pdf",           # ← explicit name
            mimetype="application/pdf"
        )
    except Exception:
        logger.exception("PDF export failed")
        return render_template("errors/500.html"), 500

