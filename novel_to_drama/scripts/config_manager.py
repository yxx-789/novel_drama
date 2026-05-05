"""
配置管理模块
"""

import os
import yaml
from pathlib import Path


class Config:
    """配置管理器"""
    
    def __init__(self, config_file: str = None):
        """
        初始化
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file or "config/settings.yaml"
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """加载配置"""
        config_path = Path(__file__).parent.parent / self.config_file
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        else:
            config = {}
        
        return config
    
    def get_llm_config(self) -> dict:
        """获取 LLM 配置"""
        llm_config = self.config.get('llm', {})
        
        # 从环境变量读取 API Key
        api_key = os.getenv("QIANFAN_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        return {
            "api_key": api_key,
            "api_url": llm_config.get('baidu_qianfan', {}).get('api_url', 
                       "https://qianfan.baidubce.com/v2/chat/completions"),
            "model": llm_config.get('model', "glm-5.1")
        }
    
    def get_drama_config(self) -> dict:
        """获取短剧配置"""
        return self.config.get('drama', {
            "episode_duration": 90,
            "max_scenes_per_episode": 8,
            "max_shots_per_scene": 5
        })
    
    def get_output_config(self) -> dict:
        """获取输出配置"""
        return self.config.get('output', {
            "formats": ["json", "markdown", "csv"],
            "output_dir": "./output"
        })


# 全局配置实例
config = Config()
