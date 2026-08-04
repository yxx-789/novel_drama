from xhs_hot_collector import normalize_feeds

FEEDS = [
    {"title": "甜宠文推荐", "noteId": "a1", "interactInfo": {"likedCount": 100}},
    {"title": "", "noteId": "a2", "interactInfo": {"likedCount": 1}},
]

def test_normalize_filters_empty_title():
    rows = normalize_feeds(FEEDS, "甜宠")
    assert len(rows) == 1
    assert rows[0]["title"] == "甜宠文推荐"
    assert rows[0]["likes"] == 100
    assert rows[0]["category"] == "甜宠"
    assert rows[0]["source"] == "xiaohongshu"
