# 架构/目录：基于当前内容优化重新生成 + 版本历史回滚

> 日期：2026-08-11
> 范围：架构（architecture）+ 目录（directory）两个 asset 类型，行为完全对称
> 状态：已批准

## 背景与目标

当前 AI 生成架构/目录后无法在已有结果上迭代：

- 生成接口不接受任何输入（`POST /generate/architecture` 无 body），用户无法让模型"基于现状调整"
- 每次生成/手动保存直接覆盖 `ProjectAsset`，只递增 `version` 数字，无历史快照，无法回滚

目标：

1. 生成时支持传入作者的**优化提示词**（guidance），模型**基于当前全文优化**而非从零重写
2. 每次生成/手动保存保留**历史版本**，可查看、可回滚
3. 前端在架构/目录两个 tab 提供常驻可展开的优化面板 + 版本历史列表

## 决策

- 版本历史用**独立表 `asset_versions`**（方案 A），`ProjectAsset` 表结构不变
- 提示词传递走现有链路：路由 body → `task.params` → worker → `generation_service` prompt
- 生成时后端自己取当前全文快照，前端不上传当前内容

## 数据模型

新表 `asset_versions`（alembic 迁移新增）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID PK | |
| `project_id` | UUID FK → projects | |
| `asset_type` | str | `architecture` / `directory` |
| `version` | int | 该 asset 下序号，从 1 递增 |
| `content_text` | text | 该版本完整内容 |
| `trigger_type` | str | `generate`（AI 生成）/ `manual`（手动保存）/ `rollback`（回滚快照） |
| `guidance` | text, 可空 | 触发本次生成时的优化提示词；manual 为空；rollback 记 `回滚至 v{N}` |
| `created_by` | UUID, 可空 | |
| `created_at` | timestamptz | |

`ProjectAsset` 不变：`version` 继续作为"当前版本号"指针。迁移时把存量 asset 当前内容回填为 version=1（trigger=`manual`）。

## 后端

### 生成链路（架构 + 目录对称）

1. `POST /api/projects/{id}/generate/architecture` 与 `.../directory` 增加可选 body `{"guidance": "..."}`；guidance 超过 2000 字 → 400
2. 路由存 `task.params["user_guidance"]`，并在提交任务时从 asset 表取当前全文存入 `task.params["current_content"]`
3. worker `run_architecture_task` / `run_directory_task` 读取两个字段，`current_content` 传给 `generate_architecture(project, user_guidance, current_content, llm_config)` / `generate_directory(project, architecture_text, user_guidance, current_content, llm_config)`
4. prompt 模板（`prompts.py`）新增「参考当前版本」段落：

   > 以下是当前已有的{架构/目录}全文。请**基于它优化**：保留其合理设定，针对作者要求调整，不要从零重写、不要丢失已有核心设定。

### 版本写入

- `_save_asset`（task_service）改造：写 `ProjectAsset`（version+1）与插 `asset_versions`（trigger=generate/manual，带 guidance）在同一事务内提交，避免半写
- 手动 upsert（assets.py `PUT /assets/{type}`）同样写历史，trigger=`manual`，guidance 空

### 版本 API

- `GET /api/projects/{id}/assets/{type}/versions` → 按 version 倒序列表：`{id, version, trigger_type, guidance, created_at}`
- `POST /api/projects/{id}/assets/{type}/rollback` body `{"version": N}`：
  - 校验 N 存在且属于该 asset，否则 404
  - 把 v{N} 的 `content_text` 写回 `ProjectAsset`（version 续 +1），插一条 trigger=`rollback` 的历史行（guidance=`回滚至 v{N}`）
  - 不删除历史
- 错误：guidance 超长 → 400；rollback 目标不存在 → 404；写入失败 → 事务回滚，历史不变

## 前端

- 抽公共组件：
  - `GuidancePanel`：可展开（默认收起，展开后常驻）输入框 + 生成按钮；按钮文案随状态切换——无内容时 `AI 生成架构`（原行为），有内容时 `基于当前架构优化生成`（副文案"将参考当前全文 + 你的提示词"）；生成中禁用防连点
  - `VersionHistory`：版本列表（`v5 · 2分钟前 · AI 生成`，悬浮显示 guidance）、`回滚到此版本` 按钮（confirm 后调 rollback，刷新内容 + 列表）、当前版本按钮禁用、空态文案"暂无历史版本"
- `generateArchitecture(id, guidance?)` / `generateDirectory(id, guidance?)` 扩展签名，无 guidance 时不带 body（与旧行为兼容）
- ArchitectureTab / DirectoryTab 各引用两个组件；`onGenerate` 签名扩展为 `(projectId, guidance?)`
- 回滚成功后 toast 提示，当前内容区即时更新

## 错误处理

- 并发生成沿用现有 task 队列顺序消费；写入用事务
- 生成失败（如 LLM key 未配置）沿用现有任务失败链路，不写版本行
- 前端加载/错误态沿用现有样式

## 测试

后端：
- 生成函数注入 `current_content` 后 prompt 包含"参考当前版本"段
- `_save_asset` 写历史行且 version 递增
- rollback 写回内容 + 新增 rollback 行
- versions 列表按 version 倒序

前端：
- GuidancePanel 文案随内容有无切换
- 无 guidance 时请求不带 guidance 字段

回归：手动保存、导出、无 guidance 生成不受影响。

## 文档

- `docs/API_SPEC.md`：2 个版本 API + 生成接口 body 变更
- `docs/DATA_MODEL.md`：`asset_versions` 表
- `docs/CHANGELOG.md`：功能变更记录
- `.env.example` 无改动（无新配置项）

## 非目标

- 不做 architecture/directory 之外 asset 类型的版本历史（后续可扩展，表已通用）
- 不做版本内容 diff 对比（本期仅列表 + 回滚）
- 不改 `_get_asset_text` 语义
