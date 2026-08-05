# 写作配置冲突规则引擎 设计（V2）

- 日期：2026-08-05
- 状态：设计已批准（完整矩阵已确认）
- 目标项目：`/Users/yxx/Desktop/novel_drama_v2`

## 背景

V3 P1 的积木式生成允许用户自由组合 7 维配置，但**没有冲突校验**——矛盾的组合（如 仙侠×末世废土、精简×群像）会被照单全收拼进 prompt，导致生成混乱。需要一套**冲突规则引擎**：硬冲突禁选/报错，软冲突提示确认，覆盖 8 个维度的两两冲突 + 豁免边界。

## 规则引擎设计

### 数据结构（`block_library.py` 新增）

```python
# 背景世界系分组（含中性标记）
BACKGROUND_SYSTEMS = {
    "古风": {"背景块": ["宗门林立", "王朝庙堂", "大陆争霸"], "neutral": False},
    "山野": {"背景块": ["山野灵异"], "neutral": True},   # 中性，可与任意系搭配
    "现代": {"背景块": ["都市霓虹", "学院青春"], "neutral": False},
    "未来": {"背景块": ["末世废土", "星际远征"], "neutral": False},
}

# 题材硬禁背景系（历史/体育）
GENRE_HARD_BACKGROUND = {
    "历史": ["现代", "未来"],
    "体育": ["古风", "未来"],
}

# 硬冲突（维度A, 值A, 维度B, 值B）——禁选/报错
HARD_CONFLICTS = [
    ("background", "宗门林立", "background", "末世废土"),  # 跨系（示例，实际按系统推导）
    # 背景跨系：由 BACKGROUND_SYSTEMS 推导（同一维多选跨系）
    ("cast_scale", "精简", "structure", "群像"),
    ("hook", "无敌流", "hook", "打脸"),
    ("hook", "娇软", "hook", "女强"),
]

# 软警告（返回提示文本，允许继续）
SOFT_WARNINGS = [
    # (条件, 提示)
    ("genre_x_background_fusion", ...),   # 罕见融合
    ("hook_x_genre_mismatch", ...),       # 卖点错位
    ("style_x_audience_tension", ...),    # 文风×受众张力
    ("style_x_genre", ...),               # 冷峻×甜宠
    ("structure_x_audience", ...),        # 种田日常×轻松爽文
    ("cast_x_genre", ...),                # 群像×甜宠
    ("structure_x_background", ...),      # 种田×星际
    ("plot_vs_setting", ...),             # 剧情走向×设定
    ("reborn_x_transmigrate", ...),       # 重生×穿越冗余
]
```

### 核心函数

```python
def check_hard_conflicts(config: dict) -> list[str]:
    """返回硬冲突列表（空=无冲突）。背景跨系、题材×背景系、规模×结构、卖点互斥。"""

def check_soft_warnings(config: dict) -> list[str]:
    """返回软警告提示列表。融合/错位/张力/剧情走向冲突。"""

def validate_writing_config(config: dict) -> dict:
    """校验入口：返回 {hard: [...], soft: [...], valid: bool}"""
```

### 前端实时检测

- 选题材 → 灰掉 `GENRE_HARD_BACKGROUND` 禁用的背景系选项
- 选背景 → 同系可选、跨系禁选（非中性）
- 选规模 → 冲突结构禁用（精简×群像）
- 选完触发 `check_soft_warnings` → 弹提示确认（可继续）
- 创建提交前 `check_hard_conflicts` → 有硬冲突则阻止提交并提示

### 后端校验

- `create_project` 时 `validate_writing_config`：
  - 硬冲突 → 拒绝（400，返回冲突项）
  - 软警告 → 允许，记录到日志/响应（不阻断）

### 前端提供检测接口

- 前端需要实时的 `check_hard_conflicts`/`check_soft_warnings` → 提供 `GET /api/inspiration/...`? 不——加 `GET /api/writing-config/validate?config=<json>`（或前端用常量副本）。为一致性，**后端提供校验接口**，前端可调用；或前端常量副本。采用：后端接口 + 前端常量副本双实现，以后端为准。

## 全局约束

- 规则数据放 `block_library.py`（单一真源）
- 硬冲突禁选/拒绝；软警告不阻断
- 不破坏既有创建流程（无冲突时行为不变）
- 文案不出现「小红书」；构建零错误
- 更新 CHANGELOG

## 涉及文件

- `backend/app/generator/block_library.py`（规则数据 + 3 个函数）
- `backend/app/services/project_service.py`（create 校验）
- `backend/app/tests/test_block_library.py`（规则测试）
- `frontend/src/pages/ProjectCreate.tsx`（实时检测）
- `docs/CHANGELOG.md`

## 不在范围

- 冲突的"智能消解"（自动改写配置）——只检测+提示
- 灵感导入时的冲突
- 编辑页的冲突校验（先做创建页）
