---
name: skill-evolution
version: 2.2.0
description: >
  Skill 自动进化管理器（STOM v2.0 瘦身版）。
  审计所有 Skill 的触发词覆盖率和踩坑经验，自动优化更新。
  详细审计流程/消化引擎/健康评分/报告模板移至 references/detailed-audit-flows.md。
references:
  - references/detailed-audit-flows.md
tags: [skill进化, skill升级, 优化skill, 审计skill, 触发词优化, 技能升级, 技能进化, skill管理, 更新触发词]
triggers:
  - skill 进化
  - skill 升级
  - 优化 skill
  - 审计 skill
  - skill 自进化
  - 触发词优化
  - 技能升级
  - 技能进化
  - 帮我优化技能
  - skill 管理
  - 更新触发词
  - 检查 skill
  - skill health
  - 技能健康检查
complexity: ⭐⭐⭐
tools:
  - read_file
  - replace_in_file
  - list_dir
  - write_to_file
---

# Skill Evolution - 技能自动进化管理器

## 🎯 定位

周期性健康审计所有 Skill：触发词覆盖、踩坑经验、描述时效、进化模块缺失。

> **详细参考**（消化引擎完整示例、注册表同步图、依赖检查矩阵、健康度评分公式、报告模板、进化模块标准模板）→ `references/detailed-audit-flows.md`

---

## 📋 审计流程（6 Phase）

| Phase | 核心动作 | 产出 |
|-------|---------|------|
| **1** Scan | list_dir + read_file 所有 SKILL.md → 建清单 | 名称/版本/触发词数/进化模块 |
| **2** Analyze | 读工作日志 → 提取盲区/踩坑/偏好 | 进化建议清单 |
| **3** Evolve | 执行 5 类改进（见下表） | 已修改的 Skill 文件 |
| **3.5** Registry | 对比 skill-registry.json vs 文件系统 | 同步后的注册表 |
| **3.6** Dep Health | 验证 depends_on 依赖可用性 | 依赖健康报告 |
| **4** Health | 5 维度加权评分 → 健康等级 | 每个 Skill 的健康分 |
| **5** Report | 生成完整审计报告 | Markdown 进化报告 |

> Phase 3.5/3.6/4 详细执行流程 + JSON 格式 → 见 references §2-4

---

## Phase 3 · 5 种改进动作

| # | 动作 | 条件 |
|---|------|------|
| ① | 补触发词 | 发现盲区，每次 ≤ 5 个，通用化 |
| ② | 补踩坑经验 | 日志中 ≥ 2 次重试模式 |
| ③ | 添加进化模块 | 缺触发词自进化 + 踩坑区 |
| ④ | 踩坑消化 | ≥ 3 条未整合 → 聚类 → 提炼为工作流步骤 |
| ⑤ | 自优化闭环 | 经验共同模式 → Skill 显式步骤 |

---

## Phase 4 · 健康度评分速查

5 维度加权（0-100 分）：

| 维度 | 权重 | 得分规则 |
|------|------|---------|
| 版本同步 | 20% | 一致=100 / 不一致=0 |
| 触发词覆盖 | 25% | min(count×10,100)，盲区-20 |
| 踩坑经验 | 15% | 无=30 / 有=60 / 整合=80 / ≥5=100 |
| 依赖可用 | 20% | 全部=100 / 部分=50 / 无=0 |
| 活跃度 | 20% | 使用=100 / 更新=80 / 无=40 |

**等级：** ≥80🟢 | 60-79🟡 | 40-59🟠 | <40🔴

> 完整公式 + JSON 持久化 + 趋势追踪 → 见 references §4

---

## ⚙️ 核心规则

1. **只追加不覆盖** — 不删现有触发词或经验
2. **通用化表述** — 新触发词可复用，不过于具体
3. **去重检查** — 语义不重复才添加
4. **透明变更** — 每次进化生成报告
5. **尊重原结构** — 只丰富元数据，不改核心工作流

---

## 🔍 Search Before Building

| Layer | 动作 |
|-------|------|
| L1 | grep 工作记忆中最近的进化记录和上次报告 |
| L2 | 检查已有进化报告模板 + 可复用模式 |
| L3 | 定义审计优先级：高频使用 > 踩坑缺失 > 触发词不足 |

---

## 🚨 Escalation

| 触发条件 | 处理 |
|---------|------|
| Skill 文件损坏 | STOP，跳过 |
| 安全漏洞（硬编码凭证）| STOP，报告 |
| 涉及自身修改 | STOP，改手动 |
| 3 次进化均失败 | STOP，报告原因 |

---

## 🔗 联动

```
上游：周期审计(每周) / 用户要求 / 发现问题
下游：self-improvement(踩坑) / skill-creator(新建) / MEMORY.md
审计优先级：P0 code-review+workflow-loop / P1 web-research+documentation / P2 其他
```

---

## 🔄 触发词自进化

用户表述未激活本 Skill 时：分析关键表述 → 抽象通用触发词 → 追加到 frontmatter triggers → 去重。

---

## 📚 踩坑经验

> AI 自动积累，请勿手动删除。格式：`- 场景：经验要点`（≥ 2 次尝试才记录）

- 踩坑即时追加：不等审计，≥ 2 次重试成功后会话结束时直接追加
- Skill 候选识别：应在 self-improvement 中加入候选识别，降低创建门槛
