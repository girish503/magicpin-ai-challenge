from __future__ import annotations

import json
from pathlib import Path

from vera.context.store import ContextStore
from vera.domain.enums import ContextScope


def load_expanded_dataset(store: ContextStore, root: Path) -> None:
    """Load generated JSON into the typed store at version one for local tests."""
    for directory, scope, identity_key in (
        ("categories", ContextScope.CATEGORY, "slug"),
        ("merchants", ContextScope.MERCHANT, "merchant_id"),
        ("customers", ContextScope.CUSTOMER, "customer_id"),
        ("triggers", ContextScope.TRIGGER, "id"),
    ):
        for path in sorted((root / directory).glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            store.put(scope, str(payload[identity_key]), 1, payload, delivered_at="2026-04-26T09:45:00Z")
