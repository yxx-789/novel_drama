# 🚀 快速开始指南

## 第一步：安装依赖

```bash
pip install pyyaml pandas requests
```

## 第二步：配置 API

### 方式一：环境变量（推荐）

```bash
# 百度千帆 API
export QIANFAN_API_KEY="bce-v3/ALTAK-..."

# OpenAI API（可选）
export OPENAI_API_KEY="sk-..."
```

### 方式二：命令行参数

```bash
python main.py --api-key "bce-v3/ALTAK-..." --novel-dir ./examples/sample_novel --chapters 1-3
```

### 方式三：配置文件

编辑 `config/settings.yaml`，直接填入 API Key。

### 测试 API 连接

```bash
python test_api.py
```

## 第三步：准备数据

### 目录结构

```
your_novel/
├── characters.json      # 角色设定
├── toc.json            # 目录
└── chapters/           # 章节文本
    ├── chapter_1.txt
    ├── chapter_2.txt
    └── ...
```

### characters.txt 格式（推荐）

支持两种格式：

**格式一：分段式（推荐）**
```
【林枫】
姓名：林枫
年龄：25
身份：商业天才
性格：冷静、果断
外貌：身材高大，眼神锐利
说话风格：简短有力，喜欢反问句
口头禅：有意思

【苏晴】
姓名：苏晴
年龄：23
身份：公司职员
...
```

**格式二：键值式**
```
林枫：
  姓名：林枫
  年龄：25
  ...

苏晴：
  姓名：苏晴
  ...
```

也支持其他文件名：`角色设定.txt`、`人设.txt`、`人物设定.txt`

### characters.json 格式（兼容）

```json
{
  "林枫": {
    "姓名": "林枫",
    "年龄": 25,
    "身份": "商业天才",
    ...
  }
}
```

### toc.txt 格式（推荐）

支持多种格式：

**格式一：第N章 标题**
```
第1章 危机降临
第2章 暗流涌动
第3章 正面交锋
```

**格式二：中文数字**
```
第一章 危机降临
第二章 暗流涌动
```

**格式三：数字. 标题**
```
1. 危机降临
2. 暗流涌动
```

**格式四：纯标题（自动编号）**
```
危机降临
暗流涌动
```

也支持其他文件名：`目录.txt`、`章节目录.txt`

### toc.json 格式（兼容）

```json
[
  {"chapter": 1, "title": "危机降临"},
  {"chapter": 2, "title": "暗流涌动"}
]
```

## 第四步：运行

### 单集处理

```bash
# 将第1-3章合并为第1集
python main.py --novel-dir ./your_novel --chapters 1-3 --episode 1
```

### 批量处理

```bash
# 自动每3章一集
python main.py --novel-dir ./your_novel --batch
```

### 指定输出格式

```bash
# 只导出 Markdown
python main.py --novel-dir ./your_novel --chapters 1-3 --format markdown

# 只导出 CSV
python main.py --novel-dir ./your_novel --chapters 1-3 --format csv

# 导出所有格式（默认）
python main.py --novel-dir ./your_novel --chapters 1-3 --format json markdown csv
```

## 第五步：查看输出

```bash
ls output/
# episode_001.json
# episode_001.md
# episode_001.csv
```

---

## 📖 使用示例

### 示例 1：处理示例数据

```bash
cd /home/gem/.openclaw/workspace/novel_to_drama
python main.py --novel-dir ./examples/sample_novel --chapters 1-3 --episode 1
```

预期输出：
```
🎬 Novel to Drama - 网文转短剧脚本生成器
==================================================

📖 第一步：加载数据...
   ✅ 加载完成：6 章
   ✅ 角色数量：3

📺 处理第 1 集（第 1-3 章）...

📝 第二步：生成短剧大纲...
   ✅ 大纲生成完成
      标题：危机降临
      时长：90 秒
      反转：2 次

🎬 第三步：生成分镜头剧本...
   ✅ 剧本生成完成
      场景数：5
      总镜头：18

💾 第四步：导出剧本...
✅ JSON 导出成功: output/episode_001.json
✅ Markdown 导出成功: output/episode_001.md
✅ CSV 导出成功: output/episode_001.csv

==================================================
✅ 处理完成！
   输出文件：
      - output/episode_001.json
      - output/episode_001.md
      - output/episode_001.csv
```

### 示例 2：无 API 测试（降级模式）

如果未配置 API Key，系统会自动使用降级方案，返回示例剧本。

```bash
# 不设置 API Key
unset OPENAI_API_KEY

python main.py --novel-dir ./examples/sample_novel --chapters 1-3
# 会使用降级示例数据
```

---

## ⚠️ 常见问题

### Q1: API 调用失败？

检查：
1. API Key 是否正确
2. 网络是否通畅
3. 模型名称是否正确

### Q2: 输出内容不理想？

调整：
1. 修改 `episode_mapper.py` 中的 System Prompt
2. 调整压缩比参数
3. 增加角色设定的详细程度

### Q3: 如何使用百度千帆？

```bash
# 配置 API Key
export QIANFAN_API_KEY="bce-v3/ALTAK-..."

# 运行
python main.py --novel-dir ./examples/sample_novel --chapters 1-3 --model deepseek-v3.1-250821
```

### Q4: 如何使用 OpenAI？

```bash
# 配置 API Key
export OPENAI_API_KEY="sk-..."

# 运行
python main.py --novel-dir ./examples/sample_novel --chapters 1-3 --model gpt-4
```

---

## 🎯 下一步

- 查看 `output/episode_001.md` 了解输出格式
- 根据需要调整 `config/settings.yaml` 参数
- 准备自己的小说数据，开始创作！

**祝你创作愉快！** 🎬
