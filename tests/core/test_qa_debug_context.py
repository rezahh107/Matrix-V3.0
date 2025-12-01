from collections.abc import Mapping

import pytest

from app.core.debug.models import QADebugContext
from app.core.qa.rules import QA_RULE_IDS, get_rule_definitions


def test_debug_context_present_for_all_rules() -> None:
    definitions = get_rule_definitions()
    assert set(definitions) == set(QA_RULE_IDS)
    for definition in definitions.values():
        context = definition.debug_context
        assert isinstance(context, QADebugContext)
        assert isinstance(context.important_columns, tuple)
        assert isinstance(context.source_tables, tuple)
        assert isinstance(context.lineage_keys, tuple)
        assert isinstance(context.diagnosis_hints, tuple)
        assert isinstance(context.canary_thresholds, Mapping)


def test_debug_context_canary_thresholds_are_immutable() -> None:
    context = QADebugContext.from_sequences(canary_thresholds={"over_capacity": 1.0})
    with pytest.raises(TypeError):
        context.canary_thresholds["over_capacity"] = 2.0  # type: ignore[index]
