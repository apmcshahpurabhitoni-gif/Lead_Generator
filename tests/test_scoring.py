from scoring import score_lead

def test_missing_directory_links_do_not_create_bonus():
    research={"industry":"dental","website":{"exists":True},"seo":{"score":100},
              "local":{"phone_found":True,"email_found":True},"google":{},
              "profiles":{},"problems":[]}
    result=score_lead(research)
    assert result["score"] == 25
    assert result["confidence"] >= 0

def test_real_website_gap_is_scored():
    research={"industry":"dental","website":{"exists":False},"seo":{"score":0},
              "local":{"phone_found":False,"email_found":False},"google":{},
              "profiles":{},"problems":[]}
    result=score_lead(research)
    assert result["score"] >= 54
    assert "Websites" in result["recommended_services"]
