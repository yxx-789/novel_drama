import asyncio
from types import SimpleNamespace

from app.services.inspiration_service import build_inspiration_guidance


class FakeResult:
    def scalar_one_or_none(self):
        return SimpleNamespace(
            content_json={
                "title": "重生之我在都市当神豪",
                "summary": "主角重生九十年代逆袭",
                "tags": ["重生", "都市", "神豪"],
                "likes": 5200,
            }
        )


class FakeDB:
    async def execute(self, stmt):
        return FakeResult()


def test_build_guidance_formats_asset():
    db = FakeDB()
    result = asyncio.run(build_inspiration_guidance(db, "p1"))
    assert "重生之我在都市当神豪" in result
    assert "5200" in result
    assert "重生、都市、神豪" in result
