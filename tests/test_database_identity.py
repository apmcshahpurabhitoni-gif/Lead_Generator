from identity import identity_key

def test_identity_prefers_provider_id():
    assert identity_key("Same Name","Jabalpur","https://example.com",source_place_id="google:abc") == "place:google:abc"

def test_identity_uses_domain_before_phone():
    assert identity_key("Same Name","Jabalpur","https://www.Example.com",phone="+91 99999 99999") == "domain:example.com"

def test_identity_uses_phone_before_name():
    assert identity_key("Same Name","Jabalpur",None,phone="+91 99999 99999") == "phone:919999999999|jabalpur"
