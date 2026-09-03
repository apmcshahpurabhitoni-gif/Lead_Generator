from constants import BUSINESS_TYPES, CITIES, PIPELINE_STATUSES

def test_canonical_lists_are_shared():
    assert ("🦷 Dental / Dentist","dental") in BUSINESS_TYPES
    assert "Jabalpur" in CITIES
    assert "MESSAGE_GENERATED" not in PIPELINE_STATUSES
    assert PIPELINE_STATUSES[-1] == "DO_NOT_CONTACT"
