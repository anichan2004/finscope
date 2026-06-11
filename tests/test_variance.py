from finscope import variance


def test_variance_report_columns(actuals):
    report = variance.variance_report(actuals)
    expected = {"month", "category", "budget", "actual",
                "variance", "variance_pct", "status"}
    assert expected.issubset(report.columns)
    assert not report.empty


def test_variance_identity(actuals):
    report = variance.variance_report(actuals)
    # variance must equal budget minus actual for every row
    diff = (report["budget"] - report["actual"] - report["variance"]).abs()
    assert (diff < 1e-6).all()


def test_summary_consistency(actuals):
    report = variance.variance_report(actuals)
    s = variance.variance_summary(report)
    assert abs(s["total_variance"] - (s["total_budget"] - s["total_actual"])) < 1e-2
