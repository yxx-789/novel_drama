from xhs_hot_collector import normalize_feeds

# 真实结构：note_id 在顶层 `id`，标题/点赞/作者嵌在 noteCard（字符串）
REAL_FEEDS = [
    {
        "id": "68c0032c000000001d004bb8",
        "xsecToken": "token1",
        "noteCard": "{'type': 'normal', 'displayTitle': '拆解甜宠文短剧的写作方法', "
                    "'user': {'userId': 'u1', 'nickname': '芹菜小姐'}, "
                    "'interactInfo': {'likedCount': '223', 'sharedCount': '27', 'collectedCount': '310'}}",
    },
    {
        "id": "",
        "xsecToken": "token2",
        "noteCard": "{'displayTitle': '无id应被跳过'}",
    },
    {
        "id": "note-3",
        "xsecToken": "token3",
        "noteCard": "{'displayTitle': '', 'user': {}, 'interactInfo': {}}",
    },
]

# 兼容：老结构（noteId 在顶层 + dict 形式 noteCard）
LEGACY_FEEDS = [
    {"noteId": "legacy-1", "title": "旧结构标题", "noteCard": {"displayTitle": "noteCard 标题"}},
]


def test_normalize_real_structure():
    rows = normalize_feeds(REAL_FEEDS, "甜宠")
    # 无 id 的一条、标题为空的一条被过滤
    assert len(rows) == 1
    row = rows[0]
    assert row["note_id"] == "68c0032c000000001d004bb8"
    assert row["title"] == "拆解甜宠文短剧的写作方法"
    assert row["likes"] == 223
    assert row["collects"] == 310
    assert row["shares"] == 27
    assert row["author"] == "芹菜小姐"
    assert row["category"] == "甜宠"
    assert row["source"] == "xiaohongshu"
    assert "68c0032c000000001d004bb8" in row["url"]


def test_normalize_legacy_structure():
    rows = normalize_feeds(LEGACY_FEEDS, "甜宠")
    assert len(rows) == 1
    assert rows[0]["note_id"] == "legacy-1"
    assert rows[0]["title"] == "noteCard 标题"


def test_normalize_filters_empty_title_and_id():
    feeds = [{"id": "a1", "noteCard": "{'displayTitle': ''}"}, {"id": "", "noteCard": "{'displayTitle': 'x'}"}]
    assert normalize_feeds(feeds, "甜宠") == []
