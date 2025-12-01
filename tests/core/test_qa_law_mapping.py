from app.core.qa.law_mapping import LawMapping, all_law_mappings
from app.core.qa.rules import QA_RULE_IDS, QaRuleDefinition, get_rule_definitions


def test_all_rules_have_law_mapping() -> None:
    mappings = all_law_mappings()
    assert set(mappings) == set(QA_RULE_IDS)
    for rule_id, mapping in mappings.items():
        assert isinstance(mapping, LawMapping)
        assert mapping.rule_id == rule_id
        assert mapping.law_refs and all(ref.strip() for ref in mapping.law_refs)
        assert mapping.description.strip()


def test_rule_definitions_attach_mappings() -> None:
    definitions = get_rule_definitions()
    assert set(definitions) == set(QA_RULE_IDS)
    for rule_id, definition in definitions.items():
        assert isinstance(definition, QaRuleDefinition)
        assert definition.rule_id == rule_id
        assert isinstance(definition.law_mapping, LawMapping)
        assert definition.debug_context is not None
