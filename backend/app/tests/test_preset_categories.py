from app.core.preset_categories import get_preset_category_names, get_keywords


def test_has_32_categories():
    assert len(get_preset_category_names()) == 32


def test_each_category_has_keywords():
    for name in get_preset_category_names():
        assert get_keywords(name), f"{name} 缺关键词"


def test_unknown_category_returns_empty():
    assert get_keywords("不存在") == []
