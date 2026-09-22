from research_schema import normalize_research, AVAILABLE, NOT_FOUND, NOT_CONFIGURED


def test_missing_website_is_not_found():
    r = normalize_research({"name": "ABC", "city": "Jabalpur", "industry": "dental"}, {})
    assert r["website"]["status"] == NOT_FOUND and r["website"]["exists"] is False


def test_future_modules_are_not_configured():
    r = normalize_research({"name": "ABC", "city": "Jabalpur"}, {})
    assert r["maps"]["status"] == NOT_CONFIGURED
    assert r["organic_ranking"]["status"] == NOT_CONFIGURED


def test_worker_serp_is_available():
    r = normalize_research(
        {"name": "ABC", "city": "Jabalpur"},
        {"worker_version": "x", "serp": [{"title": "ABC"}], "worker_response": {"results": [{"title": "ABC"}]}},
    )
    assert r["search"]["status"] == AVAILABLE and r["search"]["result_count"] == 1
