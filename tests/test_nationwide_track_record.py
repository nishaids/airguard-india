"""The public track record shows error figures only for cells with enough verified forecasts."""
from src.nationwide import store


def cell(region="Delhi", lead="<12h", category="Poor", n=40, forecasts=30, days=7, mae=12.5):
    return {"region": region, "lead": lead, "predicted_category": category, "n": n, "forecasts": forecasts, "days": days,
            "mae": mae, "rmse": 15.0, "bias": -3.0, "category_accuracy": 0.6, "within_one_category": 0.9}


def test_a_cell_with_enough_forecasts_and_days_is_scored():
    [row] = store.publishable([cell()])
    assert row["eligible"] is True and row["mae"] == 12.5 and row["bias"] == -3.0
    assert (row["min_forecasts"], row["min_days"]) == (store.TRACK_RECORD_MIN_FORECASTS, store.TRACK_RECORD_MIN_DAYS)


def test_too_few_forecasts_or_days_publishes_counts_only():
    few = store.publishable([cell(forecasts=29), cell(days=6), cell(n=500, forecasts=2, days=1, mae=249.5)])
    assert [r["eligible"] for r in few] == [False, False, False]
    for row in few:
        assert all(row[k] is None for k in ("mae", "rmse", "bias", "category_accuracy", "within_one_category"))
        assert row["n"] > 0 and row["forecasts"] > 0 and row["days"] > 0


def test_many_station_pairs_from_few_forecasts_do_not_qualify():
    # one forecast checked against many nearby stations is still one forecast
    [row] = store.publishable([cell(n=300, forecasts=3, days=3)])
    assert row["eligible"] is False and row["mae"] is None


def test_pooled_rows_come_first_then_scored_cells():
    rows = store.publishable([
        cell(region="Kerala", forecasts=1, days=1),
        cell(region="Delhi", forecasts=40, days=9),
        cell(region="All regions", lead="<12h", category="All categories", forecasts=50, days=10),
        cell(region="All regions", lead="All leads", category="All categories", forecasts=90, days=14),
    ])
    assert [(r["region"], r["lead"]) for r in rows] == [
        ("All regions", "All leads"), ("All regions", "<12h"), ("Delhi", "<12h"), ("Kerala", "<12h")]
