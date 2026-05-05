# 🎬 Novel to Drama - 网文转竖屏微短剧脚本生成器

> 将网络小说自动解构、转换为"竖屏微短剧脚本"的专业工具

---

## 📋 项目简介

**核心功能**：将网文小说（人物设定 + 章节文本）转换为符合当前爆款"微短剧"逻辑的分镜头脚本

**核心挑战**：解决**压缩比**问题
- 小说 3 章打斗 → 短剧 10 秒特效 + 1 句狠话
- 小说 1 句心理描写 → 短剧 30 秒回忆闪回

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install pyyaml pandas requests
```

### 2. 配置 API

```bash
# 百度千帆 API（推荐）
export QIANFAN_API_KEY="bce-v3/ALTAK-..."

# 或 OpenAI API
export OPENAI_API_KEY="sk-..."
```

### 3. 测试 API 连接

```bash
python test_api.py
```

### 3. 运行示例

```bash
# 处理第1-3章，生成第1集
python main.py --novel-dir ./examples/sample_novel --chapters 1-3 --episode 1
```

### 4. 批量处理

```bash
# 自动每3章一集
python main.py --novel-dir ./examples/sample_novel --batch
```

---

## 📁 项目结构

```
novel_to_drama/
├── 📄 main.py                    # 主入口
├── 📄 requirements.txt           # 依赖
├── 📂 config/                    # 配置
│   └── settings.yaml            # 系统配置
├── 📂 scripts/                   # 核心模块
│   ├── data_loader.py           # 数据加载
│   ├── episode_mapper.py        # 大纲映射
│   ├── script_generator.py      # 剧本生成
│   └── exporter.py              # 导出模块
├── 📂 examples/                  # 示例数据
│   └── sample_novel/
│       ├── characters.txt      # 角色设定（TXT格式）
│       ├── toc.txt             # 目录（TXT格式）
│       └── chapters/            # 章节文本
└── 📂 output/                   # 输出目录
```

---

## 🧠 核心工作流

### 第一步：数据加载 (`data_loader.py`)

**输入**：
- `characters.json` - 角色设定
- `toc.json` - 章节目录
- `chapters/chapter_*.txt` - 章节文本

**输出**：统一的数据结构，便于后续处理

### 第二步：短剧大纲映射 (`episode_mapper.py`)

**LLM 核心任务**：将 N 个章节映射为单集大纲

**关键设计**：
- **开局 3 秒钩子**：必须立即抓住观众
- **结尾 5 秒悬念**：必须让观众想看下一集
- **每集至少 2 次反转**：爽点密集
- **压缩比控制**：打斗压缩，情绪扩展

**输出格式**：
```json
{
  "episode_num": 1,
  "title": "本集标题",
  "hook": {"first_3s": {...}},
  "story_beats": [...],
  "cliffhanger": {"last_5s": {...}},
  "reversal_count": 2,
  "爽点_tags": ["打脸", "逆袭"]
}
```

### 第三步：剧本生成 (`script_generator.py`)

**LLM 核心任务**：根据大纲生成分镜头脚本

**核心原则**：
- ❌ **绝对禁止心理描写** → 必须转为视觉动作或台词
- ✅ **格式严格**：【场景】、【人物】、【视觉/动作】、【台词】
- ✅ **台词人设化**：符合角色性格，冲突感强
- ✅ **节奏控制**：镜头时长 1-6 秒，快速切换

**输出格式**：
```json
{
  "scenes": [
    {
      "scene_num": 1,
      "location": "办公室",
      "shots": [
        {
          "shot_num": 1,
          "visual": "画面描述",
          "action": "人物动作",
          "dialogue": {"speaker": "...", "content": "..."}
        }
      ]
    }
  ]
}
```

### 第四步：导出模块 (`exporter.py`)

**支持格式**：
- **Markdown** - 便于阅读和修改
- **CSV** - 便于导入剪辑软件
- **JSON** - 便于程序处理

---

## 🔬 技术亮点

### 1. Prompt 工程

**大纲映射 Prompt**：
- 强调"压缩比"概念
- 强制输出反转次数
- 设计钩子和悬念
- 避免触发安全过滤器

**剧本生成 Prompt**：
- 严格禁止心理描写
- 提供"心理→视觉"转换示例
- 强调"台词冲突感"
- 竖屏适配指导

### 2. 安全设计

- **降级机制**：LLM 失败时返回示例数据
- **内容过滤**：Prompt 设计避免敏感词汇
- **错误处理**：完善的异常捕获和日志

### 3. 竖屏适配

- **构图指导**：纵向构图，突出人物上半身
- **字幕预留**：底部 1/3 空间
- **景别控制**：多用中景、特写，少用远景

---

## 🎯 短剧转化逻辑

### 压缩规则

| 小说内容 | 短剧处理 | 时长比例 |
|---------|---------|---------|
| 打斗场景 | 压缩到 30% | 3章 → 10秒 |
| 对话场景 | 保留 80% | 5段 → 4段 |
| 情绪场景 | 扩展到 150% | 1句 → 30秒 |
| 心理描写 | 转为视觉/台词 | 必须转换 |

### 节奏控制

```
第 1-3 秒：开局钩子（必须抓人）
第 4-85 秒：核心剧情（爽点密集）
第 86-90 秒：结尾悬念（必须留扣子）
```

### 爽点设计

- **打脸爽**：反派嘲讽 → 主角实力碾压
- **逆袭爽**：困境 → 突破 → 翻盘
- **身份爽**：隐藏身份曝光 → 众人震惊
- **情感爽**：误解消除 → 感情升温

---

## 📊 输出示例

### Markdown 格式

```markdown
# 第1集：危机降临

**集数**: 第 1 集
**总时长**: 90 秒
**总镜头数**: 15

## 场景 1
- **地点**: 办公室
- **时间**: 夜
- **内外**: 内
- **人物**: 林枫, 赵明
- **氛围**: 紧张

### 镜头 1 (2秒)
- **类型**: 特写
- **画面**: 林枫眼神锐利，嘴角紧抿
- **动作**: 林枫攥紧拳头
- **运镜**: 固定

**林枫**:
> 你以为我会怕你？
> *坚定*

**音效**:
- BGM: 紧张弦乐
- SFX: 心跳声
```

### CSV 格式（剪辑软件友好）

| 集数 | 场景号 | 镜头号 | 类型 | 时长 | 地点 | ... |
|-----|-------|-------|-----|-----|-----|-----|
| 1 | 1 | 1 | 特写 | 2秒 | 办公室 | ... |

---

## ⚙️ 配置说明

### LLM 配置

```yaml
llm:
  provider: "openai"  # 或 "baidu_qianfan"
  model: "gpt-4"
  
  # OpenAI
  openai:
    api_key: "${OPENAI_API_KEY}"
  
  # 百度千帆
  baidu:
    api_key: "${QIANFAN_API_KEY}"
    model: "deepseek-v3.1-250821"
```

### 短剧参数

```yaml
drama:
  episode_duration: 90  # 每集90秒
  max_scenes_per_episode: 8
  max_shots_per_scene: 5
  
  compression_ratio:
    action: 0.3    # 打斗压缩到30%
    dialogue: 0.8  # 对话保留80%
    emotion: 1.5   # 情绪扩展到150%
```

---

## 🚀 使用场景

### 1. 网文作者
- 将小说快速转为短剧脚本
- 验证故事节奏和爽点
- 为拍摄提供专业剧本

### 2. 短视频团队
- 批量处理网文IP
- 标准化剧本格式
- 提高创作效率

### 3. AI 生成平台
- 作为内容生成流水线
- 结合图像/视频生成
- 自动化短剧生产

---

## 🔧 扩展开发

### 添加新平台

```python
# 在 exporter.py 中添加
def export_to_platform_x(self, script: Dict) -> str:
    # 实现新平台导出逻辑
```

### 自定义压缩规则

```python
# 在 episode_mapper.py 中修改
compression_rules = {
    "action": 0.3,
    "dialogue": 0.8,
    "flashback": 2.0  # 回忆闪回扩展200%
}
```

### 集成其他 LLM

```python
# 支持 Claude/DeepSeek 等
class MultiLLMClient:
    def __init__(self, provider: str):
        if provider == "claude":
            self.client = anthropic.Anthropic()
        elif provider == "deepseek":
            self.client = openai.OpenAI(base_url="...")
```

---

## 📝 开发计划

- [x] 核心模块开发
- [x] Prompt 工程优化
- [x] 示例数据创建
- [ ] 图形界面开发
- [ ] 批量处理优化
- [ ] 多平台适配
- [ ] 实时预览功能

---

## 🎉 开始使用

```bash
# 克隆项目
git clone https://github.com/yourusername/novel_to_drama.git

# 安装依赖
cd novel_to_drama
pip install -r requirements.txt

# 运行示例
python main.py --novel-dir ./examples/sample_novel --chapters 1-3
```

**记住**：好的短剧 = 密集爽点 + 快速节奏 + 强冲突 + 大反转

---

## 📞 支持与贡献

遇到问题？查看 `examples/` 目录中的示例，或提出 Issue。

欢迎提交 Pull Request，共同完善这个工具！
