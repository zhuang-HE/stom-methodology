---
name: skill-optimizer
version: 1.0.0
description: >
  Skill Token 优化器。自动审计任意 SKILL.md 的 token 效率，
  识别可剥离内容、生成优化方案、执行瘦身改造。
  基于 STOM 方法论（三层信息架构 L1/L2/L3）。
  触发词：skill优化、token优化、Skill瘦身、SKILL.md审计、
  skill audit、skill analyzer、token分析、Skill过大、
  减少token消耗、优化Skill、审计Skill、skill optimizer
complexity: ⭐⭐
tools:
  - read_file
  - write_to_file
  - replace_in_file
  - list_dir
  - execute_command
references:
  - path: references/audit-report-template.md
    desc: "审计报告输出模板"
  - path: references/migration-checklist.md
    desc: "内容迁移操作 checklist"
---

# Skill Optimizer — STOM 自动化引擎

> **定位**：对任意 SKILL.md 执行诊断→设计→实施的自动化优化工具。
> **方法论**：基于 `skill-creation-guide.md` 中定义的 STOM v2.0 方法论。

## 适用场景

| 场景 | 示例 |
|------|------|
| 审计单个 Skill | "审计一下 tushare-data 的 token 效率" |
| 全量批量审计 | "审计所有 Skills，按大小排序" |
| 执行优化改造 | "把 harmonyos-app-dev 瘦身到 350 行以内" |
| 新 Skill 预检 | "我要新建一个 Skill，先帮我规划结构" |
| 健康检查 | "我的 Skills 有没有超标的？" |

**不适用**：修改 Skill 的业务逻辑（只管 token 效率，不管功能正确性）、创建新 Skill 的业务内容。

---

## 核心工作流

### 工作流 A：单个 Skill 审计（Audit）

```
输入：skill_name 或 SKILL.md 路径

Step 1: 读取目标 SKILL.md → 统计行数/大小/section分布
Step 2: 逐 section 分析：
        - 标记 L1(保留) / L2应移 / L3应删
        - 识别表格压缩机会
        - 识别重复内容
        - 检测引用链风险
Step 3: 计算：
        - 当前 token 估算 (行数 × 25 tokens/行)
        - 优化后预估
        - 节省比例
        - 风险评级（低/中/高）
Step 4: 输出审计报告（见 report template）
```

### 工作流 B：全量审计（Batch Audit）

```
输入：--all 或 skills 目录路径

Step 1: 遍历所有 */SKILL.md → 统计行数+大小
Step 2: 排序（按行数降序）→ 标记超标项（>350行或>15KB）
Step 3: 对每个超标项执行「工作流A」的 Step 1-3（简化版）
Step 4: 汇总为全局报告：
        - 总量统计
        - TOP 10 最大 Skill
        - 超标清单 + 各自优化建议
        - 总节省潜力估算
```

### 工作流 C：执行优化（Optimize）

```
输入：skill_name + 审计报告（或 --auto 从头跑）

前置确认：
  ⚠️ 此操作将修改 SKILL.md 并创建 references/ 文件！
  确认后继续：

Step 1: 运行审计（工作流A）→ 得到优化方案
Step 2: 创建 references/ 目录（如不存在）
Step 3: 将标记为 L2 的内容写入 references/ 子文件
Step 4: 在 SKILL.md 中替换为引用指针
Step 5: 插入「复杂任务检测」条件触发区块
Step 6: 更新 YAML frontmatter:
        - version minor +1
        - 添加 references 列表
Step 7: 验证：
        - 新行数 ≤ 350？
        - 引用指针指向的文件确实存在？
        - 无引用链？
Step 8: 输出前后对比报告
```

---

## 审计维度与评分标准

### 维度 1：规模合规性（权重 30%）

| 等级 | 行数 | 大小 | 评分 |
|------|------|------|------|
| 🟢 优秀 | ≤ 250 行 | ≤ 10 KB | 10/10 |
| 🟡 合格 | 251-350 行 | 10-15 KB | 7/10 |
| 🟠 轻微超标 | 351-500 行 | 15-22 KB | 4/10 |
| 🔴 严重超标 | > 500 行 | > 22 KB | 1/10 |

### 维度 2：信息密度（权重 25%）

```
检测指标：
- 表格占比（表格行数 / 总行数）：>40% → 高密度
- Checklist 使用频率：有 checklist → 加分
- 平均段落长度：<5 行/段 → 密集
- 是否有大段纯文本（>15行连续段落）：有 → 扣分

评分：10（高密）~ 2（低密）
```

### 维度 3：分层合理性（权重 25%）

```
检测指标：
- L2 内容是否已移至 references/？是 → 加分
- 是否存在"参考型"内容留在 L1？有 → 扣分
- 引用指针是否清晰？模糊/缺失 → 扣分
- 是否有条件触发式的复杂任务检测？有 → 加分

评分：10（分层合理）~ 2（混乱）
```

### 维度 4：架构健康度（权重 20%）

```
检测指标：
- YAML frontmatter 是否完整？（name/version/description/references）
- 是否存在引用链风险？
- 踩坑经验区是否干净？
- 版本号是否合理？

评分：10（健康）~ 2（有问题）
```

### 综合评分

```
总分 = D1×0.30 + D2×0.25 + D3×0.25 + D4×0.20

等级划分：
  9.0-10  🏆 Gold   → 无需优化
  7.0-8.9  ✅ Silver → 小改即可
  5.0-6.9  ⚠️ Bronze → 建议优化
  <5.0     🔴 Fail   → 必须优化
```

---

## Section 分类指南（审计时用）

对 SKILL.md 中每个 ## 或 ### section 做分类：

| Section 特征 | 推荐分类 | 典型例子 |
|-------------|---------|---------|
| 包含接口/参数映射表 | **L1 保留** | 意图→接口速查表 |
| 短 checklist（<20 行）| **L1 保留** | 环境校验、输入规范 |
| 核心 3-7 条原则 | **L1 保留** | 最佳实践 |
| 完整工作流模板（每步展开）| **L2 移出** | 9 个任务模板详情 |
| 示例代码/对话（>10 行）| **L2 移出** | examples |
| 详细错误处理矩阵 | **L2 移出** | detailed-rules |
| FAQ 列表 | **L2 移出 或删除** | faq |
| 完整 API 参数说明 | **L3 外部/不存** | api-docs |

---

## 输出规范

### 审计报告格式

```markdown
# Skill 审计报告：{skill_name}

## 基本信息
| 项目 | 值 |
|------|-----|
| 文件路径 | ... |
| 当前版本 | ... |
| 行数 | xxx / 350 (xx%) |
| 大小 | xx.x KB / 15 KB (xx%) |
| Section 数 | x 个 |

## 评分卡
| 维度 | 得分 | 权重 | 加权分 |
|------|------|------|--------|
| 规模合规 | x/10 | 30% | x |
| 信息密度 | x/10 | 25% | x |
| 分层合理 | x/10 | 25% | x |
| 架构健康 | x/10 | 20% | x |
| **综合** | | | **x/10 🏆/✅/⚠️/🔴** |

## 问题清单
| # | 类型 | 位置 | 说明 | 建议 |
|---|------|------|------|------|
| 1 | 超标 | L50-200 | 工作流模板占 150 行 | 移至 references/workflow-templates.md |
| ...

## 优化方案
### 建议移至 references/ 的内容（按优先级）
1. [ ] ...
2. [ ] ...

### 可压缩的内容
1. [ ] ...

### 预估效果
| 指标 | 当前 | 优化后 | 变化 |
|------|------|--------|------|
| 行数 | xxx | ~xxx | -xx% |
| 大小 | xx KB | ~xx KB | -xx% |
| Token(估) | ~xxxx | ~xxxx | -xx% |

## 风险评估
- 风险等级：低/中/高
- 主要风险点：...
- 缓解措施：...
```

详见 `references/audit-report-template.md`。

---

## 最佳实践

1. **审计不修改**：工作流 A/B 只读+分析，不动文件；只有工作流 C 才写文件
2. **先审计后动手**：永远先跑 Audit 再跑 Optimize，让用户看到报告再决定
3. **保持业务逻辑不变**：只做信息架构调整（移动/压缩/重构），不改业务含义
4. **版本号必须更新**：每次优化后 version minor +1
5. **备份意识**：重大改动前提醒用户当前版本信息（方便回溯）

---

## 与其他 Skill 的关系

| 关系 | Skill | 说明 |
|------|-------|------|
| 依赖 | skill-creation-guide | STOM 方法论的权威来源，审计标准以此为准 |
| 输入 | 任意 SKILL.md | 审计目标 |
| 输出 | 被优化的 SKILL.md + references/ | 优化产物 |
| 协同 | strategic-compact | 优化后的 Skill 更适合 strategic-compact 管理 |
| 记录 | skill-creation-guide 末尾表 | 审计结果记录到「已审计 Skill 记录」|

## 📚 踩坑经验

> 由 AI 在实际优化中积累，请勿手动删除。

（暂无记录——等待首次实际使用）
