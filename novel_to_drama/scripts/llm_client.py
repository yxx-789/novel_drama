"""
LLM API 客户端
适配百度千帆 API
"""

import json
import requests
from typing import Dict, Optional


class LLMClient:
    """LLM API 客户端"""
    
    def __init__(
        self,
        api_key: str,
        api_url: str = "https://qianfan.baidubce.com/v2/chat/completions",
        model: str = "glm-5.1"
    ):
        """
        初始化
        
        Args:
            api_key: API Key
            api_url: API URL
            model: 模型名称
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
    
    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        timeout: int = 180
    ) -> Optional[str]:
        """
        发送聊天请求
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            timeout: 超时时间（秒），默认 180 秒
        
        Returns:
            模型响应文本，失败返回 None
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=timeout  # 使用参数化的超时时间
            )
            response.raise_for_status()
            
            result = response.json()
            
            # 提取响应内容
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            
            # 处理错误响应
            if "error" in result:
                print(f"❌ API 错误: {result['error']}")
                return None
            
            print(f"❌ 未知的响应格式: {result}")
            return None
        
        except requests.exceptions.Timeout:
            print(f"❌ 请求超时（当前超时设置: {timeout} 秒）")
            print("   建议：尝试减少输入文本长度或增加超时时间")
            return None
        
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP 错误: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   响应内容: {e.response.text}")
            return None
        
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return None
    
    def chat_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[str]:
        """
        带重试的聊天请求
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            max_retries: 最大重试次数
            **kwargs: 其他参数传递给 chat()
        
        Returns:
            模型响应文本，失败返回 None
        """
        for attempt in range(max_retries):
            result = self.chat(system_prompt, user_prompt, **kwargs)
            
            if result:
                return result
            
            if attempt < max_retries - 1:
                print(f"⚠️  重试 {attempt + 1}/{max_retries}...")
        
        print(f"❌ 重试 {max_retries} 次后仍失败")
        return None


# 测试代码
if __name__ == "__main__":
    import os
    
    # 从环境变量或配置文件读取
    api_key = os.getenv("QIANFAN_API_KEY", "bce-v3/ALTAK-vnASNnJZQkPchN6JShUdi/38e23c1484e3b2ab42e15dd596dc85fd4328caf4")
    
    client = LLMClient(api_key)
    
    print("🧪 测试 API 连接...")
    result = client.chat(
        system_prompt="你是一个有帮助的助手。",
        user_prompt="你好，请用一句话介绍自己。"
    )
    
    if result:
        print("✅ API 连接成功")
        print(f"响应: {result}")
    else:
        print("❌ API 连接失败")
