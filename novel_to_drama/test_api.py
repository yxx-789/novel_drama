#!/usr/bin/env python3
"""
API 连接测试脚本
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from llm_client import LLMClient


def test_api():
    """测试 API 连接"""
    
    print("🧪 测试百度千帆 API 连接")
    print("=" * 50)
    
    # API 配置
    api_key = "bce-v3/ALTAK-vnASNnJZQkPchN6JShUdi/38e23c1484e3b2ab42e15dd596dc85fd4328caf4"
    api_url = "https://qianfan.baidubce.com/v2/chat/completions"
    model = "glm-5.1"
    
    # 创建客户端
    client = LLMClient(api_key, api_url, model)
    
    # 测试 1: 基础对话
    print("\n📝 测试 1: 基础对话")
    print("-" * 50)
    
    result = client.chat(
        system_prompt="你是一个有帮助的助手。",
        user_prompt="你好，请用一句话介绍自己。"
    )
    
    if result:
        print("✅ 测试成功")
        print(f"响应: {result[:100]}...")
    else:
        print("❌ 测试失败")
        return False
    
    # 测试 2: JSON 输出
    print("\n📝 测试 2: JSON 格式输出")
    print("-" * 50)
    
    result = client.chat(
        system_prompt="你是一个专业的编剧助手。请严格按照 JSON 格式输出。",
        user_prompt="请输出一个简单的角色信息，格式如下：\n{\"name\": \"张三\", \"age\": 25}"
    )
    
    if result:
        print("✅ 测试成功")
        print(f"响应: {result[:200]}...")
    else:
        print("❌ 测试失败")
        return False
    
    # 测试 3: 短剧大纲生成
    print("\n📝 测试 3: 短剧大纲生成（简化版）")
    print("-" * 50)
    
    system_prompt = """你是一位专业的竖屏微短剧编剧。
请严格按照以下 JSON 格式输出，不要添加任何额外文字：

{\"episode_num\": 1, \"title\": \"本集标题\", \"duration\": \"90秒\"}"""
    
    user_prompt = "请为以下内容生成一个简单的短剧大纲：主角林枫在办公室遇到了对手赵明。"
    
    result = client.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.7
    )
    
    if result:
        print("✅ 测试成功")
        print(f"响应: {result}")
        
        # 尝试解析 JSON
        import json
        try:
            data = json.loads(result)
            print(f"✅ JSON 解析成功: {data}")
        except:
            print("⚠️  JSON 解析失败（可能包含额外文字）")
    else:
        print("❌ 测试失败")
        return False
    
    print("\n" + "=" * 50)
    print("✅ 所有测试通过！API 连接正常。")
    return True


if __name__ == "__main__":
    test_api()
