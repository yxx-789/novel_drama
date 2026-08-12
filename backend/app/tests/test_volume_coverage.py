"""卷目覆盖校验：情节架构必须铺排到全书目标章数 M（V3 P2 形态闭环补充）。

背景：open 形态要求"全书卷目划分总和 = M"，但 LLM 常只详写当前卷、
省略后续卷。这里校验卷目区间是否覆盖到 M，未覆盖则强化指令重试一次。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from app.generator.prompts import plot_architecture_prompt
from app.services.generation_service import (
    _architecture_shape_instruction,
    _volume_coverage_check,
    generate_architecture,
)


def _run(coro):
    return asyncio.run(coro)


class SequenceAdapter:
    """按序返回响应，记录每次 prompt。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    async def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0)


def _project(**overrides):
    base = dict(
        topic="测试主题",
        genre="玄幻",
        num_chapters=5,
        word_number=1500,
        writing_config={"structure": "日常流", "core_genre": "玄幻"},
        story_shape="open",
        total_chapters_target=30,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


_LLM = {"api_key": "test-key"}

FULL_COVERAGE = "## 卷一：第1-5章\n## 卷二：第6-15章\n## 卷三：第16-30章"
PARTIAL = "## 卷一·夜市针王（第1-5章）"  # 只到第 5 章 < M=30


def _architecture_responses(plot_text):
    """generate_architecture 5 步 pipeline 的响应序列。"""
    return ["核心种子", "角色动力学", "世界观", plot_text, "角色状态"]


# ---------- _volume_coverage_check 单元测试 ----------

def test_coverage_true_when_full_ranges():
    assert _volume_coverage_check(FULL_COVERAGE, 30) is True


def test_coverage_false_when_partial_only():
    assert _volume_coverage_check(PARTIAL, 30) is False


def test_coverage_true_on_end_chapter_mention():
    # 兜底：无区间但出现"第 M 章"字样（如复述"第 30 章为全书终点"）
    assert _volume_coverage_check("第 30 章为全书终点（结局章写法）", 30) is True
    assert _volume_coverage_check("第30章为全书终点", 30) is True


def test_coverage_false_on_earlier_chapter_mention():
    assert _volume_coverage_check("第 20 章为阶段收束点", 30) is False


def test_coverage_true_when_no_target():
    # final 形态 / 存量 open 无 M → 不做约束
    assert _volume_coverage_check("只有当前卷", None) is True


def test_coverage_supports_separators():
    for text in [
        "第21至40章",
        "第21~40章",
        "第21—40章",  # 全角 em dash
        "第21–40章",  # en dash
        "第 21 - 40 章",  # 带空格
    ]:
        assert _volume_coverage_check(text, 40) is True, text


def test_coverage_false_on_empty_text():
    assert _volume_coverage_check("", 30) is False


def test_coverage_max_uses_largest_range_end():
    text = "卷一：第1-5章\n卷二：第6-15章\n卷三：第16-29章"
    assert _volume_coverage_check(text, 30) is False  # 29 < 30
    assert _volume_coverage_check(text, 29) is True


# ---------- generate_architecture 重试逻辑 ----------

@patch("app.services.generation_service._make_adapter")
def test_architecture_retries_when_partial(mock_adapter):
    # 第一次 plot 只到第 5 章（未覆盖 M=30）→ 强化重试，第二次覆盖
    adapter = SequenceAdapter(
        ["核心种子", "角色动力学", "世界观", PARTIAL, FULL_COVERAGE, "角色状态"]
    )
    mock_adapter.return_value = adapter
    architecture_text, _ = _run(generate_architecture(_project(), llm_config=_LLM))
    # 5 步 + 1 次重试 = 6 次调用；第 5 个 prompt 是强化重试
    assert len(adapter.prompts) == 6
    assert "上次卷目划分未覆盖到第 30 章" in adapter.prompts[4]
    assert FULL_COVERAGE in architecture_text


@patch("app.services.generation_service._make_adapter")
def test_architecture_no_retry_when_full(mock_adapter):
    adapter = SequenceAdapter(_architecture_responses(FULL_COVERAGE))
    mock_adapter.return_value = adapter
    _run(generate_architecture(_project(), llm_config=_LLM))
    assert len(adapter.prompts) == 5  # 无重试


@patch("app.services.generation_service._make_adapter")
def test_architecture_accepts_after_two_failures(mock_adapter):
    # 两次都不覆盖 → 不抛错，按第二次输出继续（架构内容可用性优先）
    adapter = SequenceAdapter(
        ["核心种子", "角色动力学", "世界观", PARTIAL, PARTIAL, "角色状态"]
    )
    mock_adapter.return_value = adapter
    architecture_text, _ = _run(generate_architecture(_project(), llm_config=_LLM))
    assert len(adapter.prompts) == 6
    assert PARTIAL in architecture_text


@patch("app.services.generation_service._make_adapter")
def test_architecture_final_no_retry_without_m(mock_adapter):
    # final 形态无 M → 不做卷目覆盖校验
    project = _project(story_shape="final", total_chapters_target=None)
    adapter = SequenceAdapter(_architecture_responses(PARTIAL))
    mock_adapter.return_value = adapter
    _run(generate_architecture(project, llm_config=_LLM))
    assert len(adapter.prompts) == 5


# ---------- prompt / 指令文本约束 ----------

def test_plot_prompt_requires_volume_section():
    assert "全书卷目划分" in plot_architecture_prompt
    assert "不得省略或只写当前卷" in plot_architecture_prompt


def test_shape_instruction_requires_coverage_open_with_m():
    inst = _architecture_shape_instruction(_project())
    assert "卷目区间首尾衔接" in inst
    assert "第 1 章至第 30 章" in inst


def test_shape_instruction_graceful_without_m():
    inst = _architecture_shape_instruction(
        _project(story_shape="open", total_chapters_target=None)
    )
    assert "全书卷目划分" in inst
    assert "第 1 章至第" not in inst  # 无 M 时不强求具体终点


def test_shape_instruction_emphasize_coverage():
    inst = _architecture_shape_instruction(_project(), emphasize_coverage=True)
    assert "上次卷目划分未覆盖到第 30 章" in inst
    assert "逐卷补全" in inst
