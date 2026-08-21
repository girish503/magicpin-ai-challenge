from pathlib import Path

from vera.context.store import ContextStore
from vera.dataset import load_expanded_dataset
from vera.diagnostics import build_domain_core_report


def test_expanded_dataset_loads_expected_context_counts():
    root = Path(__file__).parents[1] / "dataset" / "expanded"
    store = ContextStore()

    load_expanded_dataset(store, root)

    assert store.counts() == {
        "category": 5,
        "merchant": 50,
        "customer": 200,
        "trigger": 100,
    }


def test_domain_core_report_accounts_for_every_expanded_trigger():
    root = Path(__file__).parents[1] / "dataset" / "expanded"

    report = build_domain_core_report(root, __import__("datetime").datetime.fromisoformat("2026-04-26T10:00:00+00:00"))

    assert report["total_triggers"] == 100
    assert report["actionable_triggers"] + report["no_action_triggers"] == 100
    assert report["context_counts"] == {
        "category": 5,
        "merchant": 50,
        "customer": 200,
        "trigger": 100,
    }
    assert report["placeholder_triggers"] > 0
