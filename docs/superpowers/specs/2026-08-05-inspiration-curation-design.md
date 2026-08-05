# 创作灵感：LLM 策展 + 正文丰富 + 加权排序 设计（V2）

- 日期：2026-08-05
- 状态：设计已批准
- 目标项目：`/Users/yxx/Desktop/novel_drama_v2`

## 背景

当前灵感功能把小红书热点"原样搬运 + 按点赞排序"，质量不足：
1. 很多热点**没有叙事性**，难当小说/短剧创作种子
2. 卡片只有标题，**信息太薄**，创作者不知道"这能怎么用"
3. **只靠点赞排序**不准（爆款营销帖点赞高但无创作价值）

目标：采集时用 LLM 策展（过滤 + 生成灵感点 + 质量分），入库含正文信息，加权排序，前端卡片展示灵感点。

## 核心设计

### 采集流水线（修订）

```
search_feeds(关键词) → 候选（标题/点赞/收藏/分享/评论 + id/xsecToken）
    ↓ 初选：按互动分取每分类 Top N（默认 8）
get_feed_detail(id, xsecToken) → 拿正文（正文只用于策展，不入库）
    ↓ LLM 策展（批量，一次 prompt 带多篇，输入 = 标题 + 正文前 500 字）
      · usable: 能否作为小说/短剧创作种子（过滤）
      · inspiration_hint: 创作角度/怎么变成故事
      · quality_score: 1-5 创作价值
    ↓ 计算 rank_score（加权公式，见下）
    ↓ 入库：title/summary/comment_count/inspiration_hint/quality_score/rank_score
前端卡片：标题 + 摘要 + 💡灵感点 + 👍点赞
```

### 加权排序公式

```
rank_score = likes*1.0 + collects*1.2 + shares*1.5 + comments*2.0 + quality_score*300
```
（quality_score 1-5，乘 300 使创作价值在排序中有权重但不淹没互动数据）

### 数据库变更（hot_topics 表新增 4 列）

| 列 | 类型 | 说明 |
|----|------|------|
| `comment_count` | Integer | 评论数（互动信号，来自 get_feed_detail 或搜索的 interactInfo） |
| `inspiration_hint` | Text | AI 生成的创作角度（如何变成故事） |
| `quality_score` | Integer | LLM 评分 1-5（创作价值） |
| `rank_score` | Float | 加权综合分（排序依据） |

### 组件变更

**采集器 `scripts/xhs_hot_collector.py`**
- 初选：`search_feeds` 结果按互动分取每分类 Top N（`CURATE_TOP_PER_CATEGORY`，默认 8）
- 正文：对初选候选调 `get_feed_detail(id, xsecToken)` 拿正文
- LLM 策展：新增 `curate_notes()`，用 requests 调 DeepSeek API（OpenAI 兼容，env: `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL`，默认 deepseek-chat），批量判断 + 生成灵感点 + 打分
- 入库：含新 4 列；`rank_score` 按公式计算
- 已存在 `close()` 等方法不动；新增 `curate_notes`、`fetch_detail` 函数

**后端 `inspiration_service.py`**
- `get_hot_notes`：改为按 `rank_score` DESC 排序；返回 dict 增加 `comment_count`/`inspiration_hint`/`quality_score`
- 响应不含平台字段（不变）

**前端 `InspirationTab.tsx`**
- `HotNote` 接口加 `inspiration_hint`/`quality_score`
- 卡片：标题 + 摘要 + **💡 灵感点**（inspiration_hint）+ 点赞
- 无灵感点时隐藏灵感点行

## 全局约束

- 文案中性，**不出现「小红书」字样**
- 不破坏既有功能：项目内 Tab、用它创建项目流程、AI 助手、主页
- 采集器控制 MCP 负载（只策展初选高分候选，正文不入库）
- 前端 `npm run build` 零错误
- 更新 `docs/CHANGELOG.md`

## 涉及文件

- `scripts/xhs_hot_collector.py`（+ 新测试 `scripts/test_collector.py` 扩展）
- `backend/app/services/inspiration_service.py`
- `backend/app/models/inspiration.py` + Alembic 迁移（新增 4 列）
- `frontend/src/pages/ProjectDetail/InspirationTab.tsx` + `api/inspiration.ts`
- `docs/CHANGELOG.md`

## 不在范围

- 采集器运行时优化（超时/分批）——现状已知 MCP 偶发超时，本次不专门优化
- 用户手动触发策展
- 前端灵感点的展示样式精细打磨
