import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from finscope import data_generator, database


@pytest.fixture
def actuals():
    df = data_generator.generate_transactions(n_months=18, seed=1)
    conn = database.connect(":memory:")
    database.init_db(conn)
    database.load_transactions(conn, df)
    database.load_budgets(conn)
    return database.monthly_actuals(conn)
