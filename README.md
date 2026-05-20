# TradeFlow — Trader Performance & Behavioral Analytics Engine

TradeFlow is a production-grade fintech web application that transforms raw broker tradebook exports into actionable trading intelligence.

Most retail traders only track basic P&L. TradeFlow helps traders understand *how they trade* — not just *what they made*.

It analyzes trading performance, detects behavioral patterns, and generates AI-driven coaching insights.

---

## Core Features

### Tradebook Upload
Supports:
- Zerodha
- Groww
- Upstox
- Angel One
- Generic CSV/XLSX exports

### Smart Schema Detection
Automatically maps:
- symbol
- side
- quantity
- entry price
- exit price
- P&L
- trade date
- strategy tags

### Performance Analytics
- Total P&L
- Win rate
- Average gain/loss
- Profit factor
- Risk-reward ratio
- Expectancy
- Maximum drawdown
- Sharpe ratio

### Behavioral Analytics
- Best/worst weekday
- Overtrading detection
- Revenge trading detection
- Win/loss streak analysis
- Holding time analysis

### Interactive Dashboard
- Equity curve
- Drawdown chart
- Win/loss distribution
- Monthly P&L
- Symbol-wise performance
- Clean fintech-style UI

### AI Coaching Insights
Examples:
- "You lose most on Fridays."
- "Possible revenge trading detected."
- "Pause after multiple losses."

### Export
- PDF performance report
- Excel analytics report

---

## Tech Stack

- Python
- Flask
- Pandas
- Plotly
- HTML/CSS/JavaScript
- OpenPyXL
- ReportLab
- Render

---

## Architecture

Built using modular engines:

- upload_engine
- schema_engine
- pnl_engine
- analytics_engine
- behavior_engine
- recommendation_engine
- chart_engine
- export_engine

---

## Why I Built This

Most traders focus only on profits.

TradeFlow helps traders improve decision-making by understanding:
- where they lose
- when they overtrade
- what setups actually work
- what habits hurt performance

This project was built as a production-grade fintech portfolio app.