"""
JSON 解析器
使用 json-repair 解析 LLM 返回的 JSON，自动修复常见语法错误
"""

from json_repair import repair_json
from typing import Dict, Optional


def parse_llm_json(content: str, debug: bool = True) -> Optional[Dict]:
    """
    使用 json-repair 解析 LLM 返回的 JSON

    json-repair 会自动处理：
    - 从文本中提取 JSON 块
    - 修复未转义的引号
    - 修复多余的逗号
    - 修复缺失的括号
    - 修复其他 LLM 常见语法错误

    Args:
        content: LLM 返回的原始内容
        debug: 是否打印调试信息

    Returns:
        解析后的字典，失败返回 None
    """
    if not content or not isinstance(content, str):
        if debug:
            print("   ❌ 输入为空或不是字符串")
        return None

    try:
        # repair_json 会自动寻找字符串中的 JSON 块并修复
        # return_objects=True 直接返回 Python 字典
        result = repair_json(content, return_objects=True)

        if isinstance(result, dict):
            if debug:
                print("   ✅ json-repair 成功解析并提取了结构")
            return result
        else:
            if debug:
                print(f"   ❌ 解析结果不是字典类型: {type(result)}")
            return None

    except Exception as e:
        if debug:
            print(f"   ❌ json-repair 解析失败: {e}")
            print(f"   返回内容前 200 字符: {content[:200]}")
        return None