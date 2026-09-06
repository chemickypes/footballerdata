import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.valuation.audit_engine import compute_audit

POOL = pd.DataFrame([
    {"player": "Malen", "role": "A", "giorni_infortunio_3y": 10, "surplus_value_cr": 5.0, "predicted_pts_p50": 8.0},
    {"player": "Krstovic", "role": "A", "giorni_infortunio_3y": 90, "surplus_value_cr": -3.0, "predicted_pts_p50": 6.0},
])


def test_compute_audit_calculates_expected_points_and_risk_capital():
    teams = [{
        "id": 1, "name": "Squadra 1", "budget": 500,
        "roster": [
            {"player": "Malen", "role": "A", "price": 50},
            {"player": "Krstovic", "role": "A", "price": 30},
        ],
    }]

    result = compute_audit(teams, POOL, tracking_history=[])

    assert len(result) == 1
    entry = result[0]
    assert entry["team_id"] == 1
    assert entry["expected_points"] == pytest.approx(14.0)
    assert entry["risk_capital_cr"] == 30
    assert entry["risk_capital_pct"] == pytest.approx(6.0)


def test_compute_audit_reweights_with_recent_form_when_history_available():
    teams = [{
        "id": 1, "name": "Squadra 1", "budget": 500,
        "roster": [{"player": "Malen", "role": "A", "price": 50}],
    }]
    tracking_history = [
        {"player": "Malen", "ewma_form_at_that_point": 4.0},
        {"player": "Malen", "ewma_form_at_that_point": 4.0},
        {"player": "Malen", "ewma_form_at_that_point": 4.0},
    ]

    result = compute_audit(teams, POOL, tracking_history)

    assert result[0]["expected_points"] == pytest.approx(6.0)


def test_compute_audit_no_reweighting_without_enough_history():
    teams = [{
        "id": 1, "name": "Squadra 1", "budget": 500,
        "roster": [{"player": "Malen", "role": "A", "price": 50}],
    }]
    tracking_history = [{"player": "Malen", "ewma_form_at_that_point": 4.0}]

    result = compute_audit(teams, POOL, tracking_history)

    assert result[0]["expected_points"] == pytest.approx(8.0)


def test_compute_audit_assigns_badges_across_teams():
    teams = [
        {"id": 1, "name": "Squadra 1", "budget": 500,
         "roster": [{"player": "Malen", "role": "A", "price": 50}]},
        {"id": 2, "name": "Squadra 2", "budget": 500,
         "roster": [{"player": "Krstovic", "role": "A", "price": 30}]},
    ]

    result = compute_audit(teams, POOL, tracking_history=[])

    by_id = {e["team_id"]: e for e in result}
    assert any("Miglior Colpo VORP" in b for b in by_id[1]["badges"])
    assert any("Peggior Overpay" in b for b in by_id[2]["badges"])


def test_compute_audit_handles_empty_roster_without_crashing():
    teams = [{"id": 1, "name": "Squadra 1", "budget": 500, "roster": []}]
    result = compute_audit(teams, POOL, tracking_history=[])
    assert result[0]["expected_points"] == 0.0
    assert result[0]["risk_capital_cr"] == 0
