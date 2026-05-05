# 🔑 API 配置指南

## 百度千帆 API 配置

### 1. 获取 API Key

从百度千帆平台获取 API Key，格式如：
```
bce-v3/ALTAK-vnASNnJZQkPchN6JShUdi/38e23c1484e3b2ab42e15dd596dc85fd4328caf4
```

### 2. 配置方式

#### 方式一：环境变量（推荐）

```bash
# Linux/Mac
export QIANFAN_API_KEY="bce-v3/ALTAK-..."

# Windows (PowerShell)
$env:QIANFAN_API_KEY="bce-v3/ALTAK-..."

# Windows (CMD)
set QIANFAN_API_KEY=bce-v3/ALTAK-...
```

#### 方式二：命令行参数

```bash
python main.py --api-key "bce-v3/ALTAK-..." --novel-dir ./examples/sample_novel --chapters 1-3
```

#### 方式三：配置文件

编辑 `config/settings.yaml`：

```yaml
llm:
  provider: "baidu_qianfan"
  model: "deepseek-v3.1-250821"
  
  baidu_qianfan:
    api_key: "bce-v3/ALTAK-..."  # 直接填入
    api_url: "https://qianfan.baidubce.com/v2/chat/completions"
```

### 3. API 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `api_url` | API 地址 | `https://qianfan.baidubce.com/v2/chat/completions` |
| `model` | 模型名称 | `deepseek-v3.1-250821` |
| `temperature` | 温度参数（0-1） | 0.7 |
| `max_tokens` | 最大 token 数 | 2000-4000 |

---

## OpenAI API 配置（备用）

### 1. 获取 API Key

从 OpenAI 平台获取 API Key，格式如：
```
sk-...
```

### 2. 配置方式

#### 环境变量

```bash
export OPENAI_API_KEY="sk-..."
```

#### 配置文件

编辑 `config/settings.yaml`：

```yaml
llm:
  provider: "openai"
  model: "gpt-4"
  
  openai:
    api_key: "sk-..."
    base_url: "https://api.openai.com/v1"
```

---

## 测试 API 连接

### 运行测试脚本

```bash
python test_api.py
```

### 预期输出

```
🧪 测试百度千帆 API 连接
==================================================

📝 测试 1: 基础对话
--------------------------------------------------
✅ 测试成功
响应: 你好，我是DeepSeek，一个由深度求索公司创造的AI助手...

📝 测试 2: JSON 格式输出
--------------------------------------------------
✅ 测试成功
响应: {"name": "张三", "age": 25}

📝 测试 3: 短剧大纲生成
--------------------------------------------------
✅ 测试成功
响应: {"episode_num": 1, "title": "办公室的较量", "duration": "90秒"}

==================================================
✅ 所有测试通过！API 连接正常。
```

---

## 常见问题

### Q1: API 调用失败？

检查：
1. API Key 是否正确
2. 网络是否通畅
3. 模型名称是否正确

### Q2: JSON 解析失败？

可能原因：
- LLM 返回了额外文字（如 markdown 代码块）
- JSON 格式不正确

解决方案：
- 调整 Prompt，强调"只输出 JSON"
- 使用 `_parse_json_response` 自动提取 JSON

### Q3: 如何切换模型？

```bash
# 使用 DeepSeek 模型
python main.py --model deepseek-v3.1-250821 ...

# 使用 GPT-4 模型
python main.py --model gpt-4 ...
```

---

## 降级模式

如果未配置 API Key 或 API 调用失败，系统会自动使用降级模式：

```bash
# 不配置 API Key
unset QIANFAN_API_KEY

# 运行时会自动使用降级方案
python main.py --novel-dir ./examples/sample_novel --chapters 1-3
```

降级模式会返回示例数据，方便测试流程。

---

## 依赖安装

```bash
pip install pyyaml pandas requests
```

**注意**：不再需要 `openai` 库，项目已完全适配百度千帆 API。
