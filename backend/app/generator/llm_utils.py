# llm_utils.py
# -*- coding: utf-8 -*-
"""
LLM 输出清洗工具（纯函数，零依赖，供各 service 复用）。

背景：DeepSeek 等模型在生成中文对话/台词 JSON 时，经常在字符串内部嵌入
英文双引号（例如把内心独白写成 `"（OS 咪咪心声）"今天必须吃到那条鱼。"`），
导致 json.loads 直接失败。repair_stray_quotes 只针对这种「两侧都是中文字符的
ASCII 双引号」做定点修复，不影响正常 JSON 结构引号（结构引号一侧必是
JSON 语法字符，不满足规则）。
"""

import re

# 匹配两侧都是中文（汉字 U+4E00-U+9FFF / 中文标点 U+3000-U+303F /
# 全角字符 U+FF00-U+FFEF）的 ASCII 双引号。
# 这类引号几乎不可能是 JSON 结构引号（结构引号前必是 : , { [ 或空格换行）。
_STRAY_QUOTE_RE = re.compile(
    r'(?<=[一-鿿　-〿＀-￯])"'
    r'(?=[一-鿿　-〿＀-￯])'
)


def repair_stray_quotes(text: str) -> str:
    """把 JSON 字符串内部、两侧都是中文字符的 ASCII 双引号替换为全角引号。

    交替替换为「“ / ”」以保持成对可读；替换后仍是合法 JSON 字符串内容。
    若无命中则原样返回（保持幂等，便于调用方做 `repaired != text` 判断）。
    """
    if not text:
        return text

    counter = {"n": 0}

    def _replace(match: re.Match) -> str:
        counter["n"] += 1
        return "“" if counter["n"] % 2 == 1 else "”"  # “ / ”

    return _STRAY_QUOTE_RE.sub(_replace, text)
