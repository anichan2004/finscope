"""FinScope -- a personal FP&A platform.

Modules:
    config         central assumptions, categories, budgets
    data_generator synthetic transaction generator
    categorize     rule-based categorization from descriptions
    database       SQLite persistence + SQL aggregation
    variance       budget vs. actual variance analysis
    forecast       rolling cash-flow forecast + MAPE backtest
    market_data    LIVE market returns + inflation (real data)
    montecarlo     net-worth simulation + goal probability
    statements     personal 3-statement view + KPIs
    excel_report   formatted Excel variance export
"""
__version__ = "0.1.0"
