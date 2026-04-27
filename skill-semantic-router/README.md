# 🧠 Skill Semantic Router

> **AI Agent 语义路由框架** — 基于多层语义检索的智能 Skill 路由引擎，让正确的工具总能被找到。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Accuracy](https://img.shields.io/badge/Routing%20Accuracy-100%25-brightgreen.svg)]()
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-None-brightgreen.svg)]()

**Tags**: `ai-agent` · `skill-routing` · `nlp` · `intent-classification` · `tf-idf` · `semantic-search` · `zero-dependency` · `self-learning`

---

## 📖 背景

现代 AI Agent 系统（如 WorkBuddy、Cursor、Copilot 等）通常需要从数十甚至上百个专项 Skill 中，准确识别用户意图并路由到正确的工具。传统方案依赖**关键词匹配**，存在：

- 触发词覆盖不全 → Skill 该起没起
- 多 Skill 歧义 → 不知选哪个
- 用户表达多样 → 关键词无法穷举

本项目实现了一套**三层语义路由架构**，在不依赖外部 GPU / 向量数据库的前提下，实现 **100% 路由准确率**（12/12 测试集）。

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🚀 **零依赖运行** | 纯 Python 实现 TF-IDF 向量化，无需安装 PyTorch / transformers |
| 🎯 **多层路由架构** | 精确匹配 → 语义检索 → 置信度决策，层层兜底 |
| 🧠 **上下文感知** | 利用对话历史中的实体（股票名、公司名）增强当前 Query |
| 📚 **类别先验 Boost** | 金融/产品等领域词命中时，对对应类别 Skill 加权 2x |
| 🔄 **自学习反馈** | 用户纠错时自动提取触发词，写回索引并重建向量 |
| 🔄 **动态索引管理** | 自动扫描文件系统，发现新增/变更/废弃 Skill 并同步索引 |
| 📊 **487 个 Skill 覆盖** | 自动发现用户级 + 插件级 Skill，支持持续扩展 |

---

## 🏗️ 架构设计

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────┐
│  Layer 0: 精确关键词快速通道                  │
│  PRD / DCF / LBO / CIM → confidence = 1.0   │
└──────────────────┬──────────────────────────┘
                   │ 未命中
                   ▼
┌─────────────────────────────────────────────┐
│  Layer 1: 上下文感知 Query 增强              │
│  提取对话历史中的实体 → 拼接增强 Query        │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  Layer 2: TF-IDF 语义向量检索               │
│  bigram/trigram 中文分词 + 余弦相似度        │
│  + 类别 Boost (2.0x) + 来源优先级 + 排序    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  Layer 3: 置信度阈值决策                     │
│  ≥ 0.35 → invoke  (直接触发)               │
│  ≥ 0.10 → confirm (询问确认)                │
│  < 0.10 → fallback (降级处理)               │
└─────────────────────────────────────────────┘
```

---

## 📁 项目结构

````
.
├── skill_router.py          # 核心路由器实现（含测试用例）
├── skill_index_manager.py   # 动态索引管理（扫描/同步/重建）
├── skill_index.json         # 487 个 Skill 的语义索引
├── index_changelog.json     # 索引变更日志（自动生成）
├── docs/
│   ├── ARCHITECTURE.md      # 详细架构设计文档
│   ├── METHODOLOGY.md       # 方法论：从关键词到语义路由的演进
│   └── SKILL_SCHEMA.md      # skill_index.json 字段说明
├── examples/
│   └── demo.py              # 完整使用示例
├── tests/
│   └── test_router.py       # 单元测试
└── README.md
````

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/zhuang-HE/skill-semantic-router.git
cd skill-semantic-router
```

### 2. 运行演示

```bash
# 无需安装任何依赖，纯标准库即可运行
python -X utf8 skill_router.py
```

### 3. 在代码中使用

```python
from skill_router import SkillRouter

router = SkillRouter("skill_index.json")

# 基础路由
result = router.route("帮我看看这段代码有没有 bug")
print(result["action"])     # "invoke"
print(result["skill"])      # "code-review"
print(result["confidence"]) # 0.412

# 上下文感知路由
history = [
    {"role": "user", "content": "帮我查一下贵州茅台的行情"},
    {"role": "assistant", "content": "茅台今日收盘价 1680..."},
]
result = router.route(
    "再看看它的利润表",
    history=history,
    used_skills=["neodata-financial-search"]
)
# 自动识别"茅台"实体，路由至 finance-data-retrieval
```

### 4. 自学习反馈

```python
from skill_router import SkillRouter, SkillFeedbackLearner

router = SkillRouter()
learner = SkillFeedbackLearner(router)

# 当用户纠正路由时，自动学习新触发词
msg = learner.on_correction(
    original_query="拉一下利润表",
    correct_skill_id="finance-data-retrieval"
)
print(msg)  # "已为 [finance-data-retrieval] 添加触发词: ['利润表', '拉一下']"
```

### 5. 动态索引管理（自动发现 & 同步）

```python
from skill_index_manager import SkillIndexManager

mgr = SkillIndexManager()

# 全量扫描 + 同步（新增/变更 Skill 自动入库）
report = mgr.full_sync()
# 扫描发现: 508 个 skill
# 🆕 新增: 462  🔄 变更: 25  ✅ 无变化: 0

# 查看统计
stats = mgr.get_stats()
# {"total_skills": 487, "sources": {"plugin": 462, "user": 25}, ...}

# 仅预览变更（不写入）
mgr.scan()
report = mgr.sync()  # dry-run
print(report.summary())
```

**Skill 生命周期管理：**

```
新 Skill 安装到 ~/.workbuddy/skills/ 或 plugins/
    │
    ▼
python skill_index_manager.py --sync
    │
    ├── [+] 新增：自动解析 SKILL.md frontmatter，提取 name/description/triggers
    ├── [~] 变更：检测 file_hash 变化，仅更新 hash（保留人工优化的元数据）
    └── [-] 移除：磁盘上不存在的 Skill 从索引中清除
    │
    ▼
skill_index.json 更新 → TF-IDF 索引重建 → 路由器 reload()
```

---

## 📊 性能演进

| 版本 | 机制 | 准确率 | Skill 数量 |
|------|------|--------|-----------|
| v0 | 关键词匹配 | 66.7% | 25 |
| v1 | bigram/trigram 分词 | 83.3% | 25 |
| v2 | + 类别 Boost + 优先级排序 | 91.7% | 25 |
| v3 | + 精确词快速通道 | 100% | 25 |
| **v4** | **+ 动态索引管理 + 来源优先级 + 2.0x Boost** | **100%** | **487** |

---

## 🗺️ Skill 覆盖范围

| 类别 | Skill | 说明 |
|------|-------|------|
| 代码质量 | `code-review` | 代码审查、安全审计 |
| 文档 | `documentation` | README、API 文档生成 |
| 版本控制 | `git-workflow` | Commit 规范、分支策略 |
| 金融数据 | `neodata-financial-search` | 实时行情、财报、宏观数据 |
| 金融数据 | `finance-data-retrieval` | 209 个结构化 API 精确查询 |
| 金融分析 | `dcf-model` | DCF 估值建模 |
| 金融分析 | `comps-analysis` | 可比公司分析 |
| 金融分析 | `lbo-model` | 杠杆收购建模 |
| 投行 | `cim-builder` | 投资备忘录 |
| 投行 | `buyer-list` | 买方名单 |
| 产品管理 | `product-management-workflows` | PRD、路线图、用户研究 |
| 数据分析 | `data-analysis-workflows` | 数据探索、可视化、SQL |
| 研究调研 | `web-research` | 深度网络调研 |
| 办公文档 | `xlsx` / `docx` / `pptx` / `pdf` | 文档处理 |
| 股票分析 | `stock-analyst` | A/H/US 股四维分析 |
| 工作流 | `memory-consolidation` | 工作记忆整理 |
| 外部集成 | `mcp-connector` | GitHub、数据库、Docker |

---

## 🔧 自定义扩展

### 添加新 Skill

在 `skill_index.json` 的 `skills` 数组中添加：

```json
{
  "id": "my-new-skill",
  "name": "my-new-skill",
  "category": "自定义类别",
  "description": "详细描述你的 Skill 做什么，中英文均可，越详细越好",
  "triggers": ["触发词1", "触发词2", "trigger phrase"],
  "path": "path/to/SKILL.md",
  "complexity": 2,
  "priority": 1
}
```

路由器启动时会自动将新 Skill 纳入语义索引。

### 调整置信度阈值

```python
# skill_router.py 顶部配置
CONFIDENCE_HIGH = 0.35   # 直接触发
CONFIDENCE_LOW  = 0.10   # fallback
TOP_K           = 3      # 返回候选数
```

---

## 🤔 方法论

详见 [docs/METHODOLOGY.md](docs/METHODOLOGY.md)

核心思路：

1. **语义 > 关键词**：用 TF-IDF + bigram/trigram 捕捉语义，比穷举关键词更鲁棒
2. **上下文感知**：对话不是孤立的，利用历史信息增强当前 Query 是最低成本的提升
3. **分层兜底**：精确通道 → 语义检索 → 置信度门控，每层都有 fallback
4. **在线自学习**：每次用户纠错都是训练信号，系统随时间持续变好

---

## 🛣️ 路线图

- [x] ~~动态索引管理~~ — 自动扫描 / 同步 / 变更检测
- [x] ~~来源优先级~~ — 用户级 Skill 优先于插件级
- [x] ~~487 个 Skill 覆盖~~ — 自动发现用户级 + 插件级 Skill
- [ ] 接入真实 Embedding 模型（bge-m3 / text-embedding-3-small）
- [ ] 支持 FAISS 向量数据库（千级以上 Skill）
- [ ] LLM Rerank（中等置信度二次判断）
- [ ] 完整 ReAct 调度器（复杂多步任务）
- [ ] Web UI 可视化路由过程

---

## 📄 License

MIT License — 自由使用、修改、分发。

---

*Built with ❤️ · Exploring the better way to route AI Agent skills*
