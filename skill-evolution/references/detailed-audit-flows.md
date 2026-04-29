# Skill Evolution 详细参考

> **何时读此文件**：需要执行完整审计流程、生成进化报告、执行踩坑经验消化、或进行依赖健康检查时查阅。

---

## 1. 踩坑经验自动消化引擎（详细版）

### 触发条件
Skill 的未整合踩坑经验 ≥ 3 条

### 消化流程

```
扫描踩坑经验（过滤 [已整合]）
    ↓
提取：场景、工具/API、错误类型、解决方案
    ↓
聚类分析：是否有共同模式？
    ├── 是（≥ 2 条共享模式）→ 提炼为显式工作流步骤 → 标记 [已整合 → Step N]
    └── 否 → 保留在踩坑区，等待更多积累
```

### 消化示例（tushare-data）

**消化前（踩坑区）：**
```
- daily / ts_code 必须带交易所后缀（000001.SZ）
- stk_mins / freq 只接受 1min/5min/15min/30min/60min
- index_weight / 必须传 index_code，不支持 ts_code
```

**消化后（新增 Step 1.5）：**
```
### Step 1.5 · 参数预处理
1. 股票代码格式化：纯数字→自动追加 .SH/.SZ
2. 时间频率校验：freq 只接受 1/5/15/30/60min
3. 参数名匹配：指数用 index_code，个股用 ts_code
```

**踩坑区更新为：**
```
- daily / 查询单只股票：[已整合 → Step 1.5.1]
- stk_mins / 分钟线数据：[已整合 → Step 1.5.2]
- index_weight / 成分股权重：[已整合 → Step 1.5.3]
```

---

## 2. 注册表同步流程（Phase 3.5 详细版）

### 同步流程图

```
读取 skill-registry.json
    ↓
对比文件系统 ~/.workbuddy/skills/ 实际列表
    ↓
检测不一致：
┌───────────────────────┬────────────┐
│ 不一致类型              │ 处理方式   │
├───────────────────────┼────────────┤
│ 存在但注册表缺失        │ 自动补充   │
│ 注册表有但已删除        │ 移除       │
│ version 不一致          │ 以文件为准 │
│ trigger_keywords 不一致 │ 以文件为准 │
│ capabilities 缺失      │ 自动推断   │
└───────────────────────┴────────────┘
```

**capabilities 自动推断规则：**
从 description 提取功能关键词 + 工作流步骤名 + tools 字段 → 去重抽象化

**触发时机汇总：**

| 时机 | 动作 |
|------|------|
| skill-evolution 审计 | Phase 3.5 自动同步 |
| Skill 自动创建完成 | 追加新条目 |
| Skill 卸载/删除 | 从注册表移除 |
| Skill 版本升级 | 更新 version + triggers |

---

## 3. 依赖健康检查（Phase 3.6 详细版）

### 检查矩阵

| 依赖类型 | 检查方式 | 不可用时处理 |
|---------|---------|------------|
| 环境变量（TUSHARE_TOKEN 等）| 检查系统环境变量 | ⚠️ 报告缺少配置，建议用户配置 |
| 外部工具（AkShare、Node.js）| `--version` 验证 | ❌ 报告未安装，提供安装指引 |
| API Key（TMAP_*_KEY 等）| 检查环境变量 | ⚠️ 报告缺少 Key |
| MCP Server | 检查 mcp.json | ⚠️ 报告未配置 |

### 验证命令参考

```bash
# Python 包
python -c "import akshare; print(akshare.__version__)"
# Node.js
node -e "try{require('pkg')}catch(e){process.exit(1)}"
# 环境变量 (PowerShell)
[System.Environment]::GetEnvironmentVariable('VAR_NAME')
# MCP 配置
# 读取 ~/.workbuddy/mcp.json 检查 server 条目
```

### 依赖状态 JSON 格式

```json
{
  "name": "tushare-data",
  "depends_on": ["TUSHARE_TOKEN 环境变量"],
  "dependency_status": {
    "TUSHARE_TOKEN": "✅ 已配置",
    "last_checked": "2026-04-25"
  }
}
```

---

## 4. 健康度评分系统（Phase 4 详细版）

### 评分维度

| 维度 | 权重 | 评估方法 | 得分规则 |
|------|------|---------|---------|
| **版本同步** | 20% | 注册表 vs SKILL.md version | 一致=100，不一致=0 |
| **触发词覆盖** | 25% | 触发词数 + 盲区记录 | min(count×10,100)，盲区 -20 |
| **踩坑经验** | 15% | 踩坑区内容 | 有=60，已整合=80，≥5条=100，无=30 |
| **依赖可用** | 20% | Phase 3.6 结果 | 全部=100，部分=50，全部=0 |
| **活跃度** | 20% | 30天使用/更新记录 | 有使用=100，有更新=80，无=40 |

### 计算公式

```
health_score = Σ(维度分 × 权重)
等级: ≥80🟢健康 | 60-79🟡注意 | 40-59🟠亚健康 | <40🔴不健康
```

### 持久化 JSON 格式

```json
{
  "name": "self-improvement",
  "health_score": 85,
  "health_grade": "🟢",
  "health_details": {
    "version_sync": 100,
    "trigger_coverage": 90,
    "pitfall_richness": 60,
    "dependency_ready": 100,
    "activity": 100
  },
  "health_last_assessed": "2026-04-25"
}
```

### 趋势追踪

每次审计在 audit_history 追加：
```json
{"date":"2026-04-25","skill":"self-improvement","health_score":85,"health_delta":"+10","reason":"..."}
```

---

## 5. 进化报告模板

```markdown
# Skill 进化报告

**审计时间**：YYYY-MM-DD HH:mm
**审计范围**：用户级 Skill（~/.workbuddy/skills/）
**Skill 总数**：N 个

---

## 变更摘要

| Skill | 新增触发词 | 新增踩坑经验 | 添加进化模块 |
|-------|-----------|-------------|-------------|
| code-review | 3 个 | 1 条 | - |

## 详细变更

### code-review
新增触发词：帮我review、看看这段代码、有没有bug
新增踩坑经验：
- Python 代码审查：f-string 中复杂表达式不要超过 3 层嵌套

## 健康评分

| Skill | 触发词数 | 踩坑经验数 | 进化模块 | 健康度 |
|-------|---------|-----------|---------|--------|
| code-review | 15 | 3 | ✅ | ⭐⭐⭐⭐⭐ |

**下次建议审计**：{下周同一时间}
```

---

## 6. 进化模块标准模板

当 Skill 缺少进化模块时添加：

```markdown
## 🔄 触发词自进化规则

当用户输入某种表述但本 Skill 未被自动激活时：
1. 分析关键表述
2. 抽象为通用触发词
3. 用 replace_in_file 追加到 YAML frontmatter triggers 字段
4. 不得重复添加

## 📚 踩坑经验

> 由 AI 自动积累，请勿手动删除。
> 格式：`- 场景：经验要点`（≥ 2 次尝试才记录）

（暂无记录）
```

---

## 7. Completion Protocol 报告模板

```markdown
## Skill Evolution 完成报告

STATUS: DONE
**审计时间**：{datetime}  **审计范围**：{N} 个 Skill
**成功进化**：{N} 个  **跳过**：{N} 个

### 变更摘要
| Skill | 操作 | 详情 |
|-------|------|------|

### 健康评分变化
| Skill | 之前 | 之后 |
|-------|------|------|

**下次建议审计**：{date}
```

---

## 8. Skill 生命周期管理（v2.2 新增）

> 借鉴 Hermes Agent 规划：给 Skill 增加生命周期追踪字段，实现优胜劣汰。

### 生命周期字段

在 skill-registry.json 的每个 Skill 条目中增加（手动评估）：

```json
{
  "name": "code-review",
  "lifecycle": {
    "last_used": "2026-04-29",
    "use_count_estimate": 12,
    "success_rate_estimate": "high",
    "creation_date": "2026-04-20",
    "last_updated": "2026-04-27",
    "status": "active"
  }
}
```

### 状态定义

| 状态 | 条件 | 行动 |
|------|------|------|
| **active** | 30 天内使用过 | 正常维护 |
| **dormant** | 30-60 天未使用 | 审计时降优先级 |
| **stale** | 60-90 天未使用 | 审计时建议归档 |
| **archived** | 90+ 天未使用 | 审计时建议删除或归档到 references |

### 评估时机

由于 WorkBuddy 不提供 Skill 使用统计 API，这些字段在 `skill-evolution` **审计时手动评估**：

1. 回顾近期日志中的 Skill 触发记录
2. 检查 Skill 的踩坑经验区是否有近期条目
3. 评估 `last_used` 和 `use_count_estimate`
4. 更新 `status` 字段

### 与健康度评分的关联

生命周期数据纳入健康度评分的"活跃度"维度：
- active + 近期使用 = 100 分
- active + 无近期使用 = 80 分
- dormant = 40 分
- stale = 0 分

---

*来源: skill-evolution SKILL.md v2.2.0 详细内容提取 (2026-04-29)*
