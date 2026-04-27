# WorkBuddy Skills — Token 优化的 Skill 生态

> **STOM v2.0** (Skill Token Optimization Method) — 让每个 token 都有存在的理由。

## 📌 这个仓库是什么

这是 [WorkBuddy](https://github.com/) 平台的 Skills 集合，所有 Skill 均经过 **STOM 方法论审计和优化**，确保加载时的 token 消耗最小化。

### 核心问题

WorkBuddy 的 Skill 机制通过 `use_skill` 将整个 `SKILL.md` 注入 AI 上下文。如果一个 Skill 文件过大（如 800+ 行），每次加载会消耗 ~20,000+ tokens——这直接挤占了实际任务的处理空间。

**本仓库的解决方案：三层信息架构（L1/L2/L3）。**

---

## 🏗️ STOM 方法论速览

```
┌─────────────────────────────────────────────────┐
│  L1 执行层 — SKILL.md（≤350行，常驻上下文）     │
│  → AI 执行任务时"必须知道"的信息                │
├─────────────────────────────────────────────────┤
│  L2 参考层 — references/（按需 read_file）      │
│  → 复杂场景时才查阅的工作流/示例/详细规则       │
├─────────────────────────────────────────────────┤
│  L3 外部层 — 实时搜索（不存储）                 │
│  → 完整 API 文档、SDK 源码等                   │
└─────────────────────────────────────────────────┘
```

完整方法论请查看：[skill-creation-guide.md](skill-creation-guide.md)

### 关键指标

| 指标 | 上限 | 说明 |
|------|------|------|
| SKILL.md 行数 | **≤ 350** | 超出移至 references/ |
| SKILL.md 大小 | **≤ 15 KB** | 约 300-500 tokens/KB |
| 引用链 | **禁止** | references/ 内文件禁止互引 |
| 80-20 原则 | **必须满足** | 仅凭 SKILL.md 完成 ≥80% 常见任务 |

---

## 📦 已审计 Skill 列表

| Skill | 版本 | 行数 | 大小 | 瘦身比例 | 说明 |
|-------|------|------|------|---------|------|
| **tushare-data** | v1.2.0 | 234 | 8.0 KB | **-73%** | 金融数据获取层，移出 3 个 ref |
| **strategic-compact** | v2.0.0 | 205 | 7.0 KB | **-47%** | 主动式上下文压缩，升级为主动模式 |
| **skill-optimizer** | v1.0.0 | 264 | 8.0 KB | *新建* | STOM 自动化审计工具 |

> 审计前后对比详见各 Skill 的变更记录。

---

## 🔧 包含的 Skills

### 数据与分析
- **tushare-data** — Tushare 金融数据获取（行情/财报/估值/资金流/宏观）
- **stock-analyst** — 股票五维技术分析（与 tushare-data 配合）

### 效率与优化
- **skill-optimizer** — 自动审计和优化任意 Skill 的 token 效率
- **strategic-compact** — 主动式上下文压缩管理
- **skill-creation-guide** — STOM 编写规范与方法论（v2.0）

### 开发
- **harmonyos-app-dev** — 鸿蒙 HarmonyOS NEXT 应用开发
- **Android 原生开发** — Android Kotlin/Compose 开发

### 其他
- 更多 Skills 持续审计中...

---

## 🚀 使用方法

### 1. 将 Skill 安装到 WorkBuddy

```bash
# 克隆整个仓库到本地 skills 目录
git clone https://github.com/{user}/workbuddy-skills.git ~/.workbuddy/skills

# 或单个 Skill
git clone https://github.com/{user}/workbuddy-skills.git --depth 1
cp -r workbuddy-skills/tushare-data ~/.workbuddy/skills/
```

### 2. 用 skill-optimizer 审计你的 Skill

在 WorkBuddy 中调用：
> "用 skill-optimizer 审计一下我的 xxx Skill"

### 3. 按 skill-creation-guide 创建新 Skill

参考 [skill-creation-guide.md](skill-creation-guide.md) 中的 STOM 规范编写。

---

## 📊 优化效果总览

```
改造前: tushare-data(879行) + strategic-compact(390行) = 1,269行 / 34.4KB
改造后: tushare-data(234行) + strategic-compact(205行) =   439行 / 15.0KB

节省: 65% 行数减少, 56% 体积减少 ≈ 每次 Skill 加载节省 ~20,000 tokens
```

---

## 📄 License

MIT License — 自由使用、修改和分发。

---

## 贡献

欢迎 PR！提交前请确认：
1. 你的 SKILL.md ≤ 350 行 / ≤ 15 KB
2. 通过 [skill-creation-guide.md](skill-creation-guide.md) 的审计 Checklist
3. references/ 目录为扁平结构（无引用链）

---

*Powered by [STOM v2.0](skill-creation-guide.md) · Built with ❤️ for efficient AI*
