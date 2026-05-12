# Perplexity Skills 设计方法论

> **来源**：Perplexity 官方博客 *Designing, Refining, and Maintaining Agent Skills at Perplexity*（2026-05-12 整理）
>
> **价值**：与 STOM v2.0 互补——STOM 解决「信息分层」，Perplexity 解决「Skill 该怎么写、怎么迭代、怎么积累」。

---

## 一、核心设计原则（Zen of Skills）

| Python之禅 | Skill设计原则 |
|-----------|-------------|
| 简单优于复杂 | Skill是文件夹，复杂性本身就是feature |
| 显式优于隐式 | 激活靠隐式模式匹配，靠渐进披露 |
| 稀疏优于密集 | 上下文昂贵，每个token都要承载最大信号 |
| 特殊情况不足以特殊对待 | Gotcha就是特殊情况，是最高价值内容 |
| 可解释的实现就是好主意 | 如果内容很容易解释清楚，说明模型已掌握，应删掉避免浪费token |

---

## 二、Skill四面体定义

### 1. Skill是目录（Hub-and-Spoke结构）

```
<skill-name>/
├── SKILL.md              # frontmatter + 主指令
├── scripts/              # 确定性逻辑（避免agent每次重写）
├── references/           # 重型文档（按需加载）
│   └── gotchas.md       # ⚠️ 踩坑记录（核心资产）
├── assets/              # 模板、schema
└── config.json          # 首次使用的用户配置
```

### 2. Skill是格式

- **`name`**：必须全小写、无空格、可用连字符，要和目录名完全一致
- **`description`**：**是路由触发器，而非内部说明文档**
  - 正确写法：`Load when...`（什么时候加载这个Skill）
  - 错误写法：`This Skill does...`（这个Skill做什么）

### 3. Skill可被调用

Skill是运行时按需加载，而非无脑塞入上下文。

### 4. Skill是渐进披露

三档上下文成本，从根源上控制token消耗：

| 档位 | 加载内容 | 预算 | 付费时机 |
|-----|---------|------|---------|
| **Index** | 所有Skill的`name: description` | ~100token/个 | 全局税（每会话每用户） |
| **Load** | 完整`SKILL.md`正文 | ~5000token/个 | 任务税（加载后到压缩边界前） |
| **Runtime** | `scripts/`、`references/`、`assets/` | 无上限 | 按需付费（实际读取时） |

---

## 三、Skill必要性判断

### ✅ 真的需要写Skill的场景

- agent缺少特殊上下文就会做错任务
- 跨多次运行需要极致一致性
- 知识稳定但不在模型训练数据内（如训练截止时间外的信息、企业私有流程）
- 属于「品味/判断类」知识（如设计类Skill中"哪种字体合适"的判断）

### ❌ 不需要写Skill的场景

- 模型本来就掌握的通用知识（如git命令执行顺序）
- 系统提示（system prompt）里已经有的重复内容
- 变化速度比维护速度还快的内容

---

## 四、Skill撰写五步法

### Step 0：先写评估集（Evals）

评估集是撰写的前提，来源分三类：
- 真实用户查询（生产环境采样或团队核心用户反馈）
- 已知失败用例（之前agent做错的任务场景）
- 邻域混淆样本（语义靠近但应该路由到其他Skill的查询）

> 注意：负面样本的价值往往高于正面样本

### Step 1：写description（最难的1行内容）

- 必须以「`Load when...`」开头
- 控制在50词以内
- 描述用户的真实意图（最好直接用真实用户查询的原话），而非描述Skill的工作流

**正例**：
```
Load when: 用户问「babysit」「watch CI」「make sure this lands」（监控PR/CI）
```

**反例**：
```
This Skill monitors pull requests and CI pipelines.
```

### Step 2：写SKILL.md正文

- 不要写过于细碎的步骤（避免"轨道化"），给模型留出灵活处理不同情况的空间
- 最高价值内容是长期积累的gotcha（agent之前翻车的点）
- 自检标准：「如果没这句话，agent会不会做错？」不会做错的内容直接删掉

### Step 3：用好目录结构

- `scripts/`放agent每次都要重复编写的确定性逻辑
- `references/`放需要条件触发加载的重型文档
- `assets/`放输出模板、schema等资产
- `config.json`放首次使用的用户配置

### Step 4：迭代

在分支上反复跑评估集再合入代码库。

---

## 五、Gotchas飞轮（核心资产）

### 什么是Gotcha

Gotcha = agent容易翻车的特殊场景/边界情况。这是Skill长期迭代的核心资产，比主体指令更重要。

### 什么时候追加Gotcha

| Agent表现 | 操作 |
|---------|------|
| 任务失败 | 追加一条gotcha到Skill中 |
| 加载了不该加载的Skill | 收紧description + 增加负样本 |
| 没加载该加载的Skill | 给description加关键词 + 增加正样本 |

### Gotchas.md格式示例

```markdown
# Gotchas

## 缠论买卖点
- ⚠️ 不要在次级别中枢未完成时提示背驰 → 模型会误判
- ⚠️ 第三类买卖点必须在次级别回调确认后才能标注
```

### 维护原则

- **不要随意修改description**：因为description决定路由，修改会对所有其他Skill产生外溢影响
- **大部分时候仅需追加gotcha**，不需要修改描述或主体指令
- Action at a distance（新加一个Skill可能让其他不相关的Skill效果变差）——必须做多模型评测

---

## 六、与 STOM v2.0 的关系

| 维度 | STOM v2.0 | Perplexity方法论 |
|------|-----------|----------------|
| **核心关注** | 信息分层（SKILL.md ≤ 350行） | Skill怎么写、怎么迭代 |
| **Description** | 要求简洁 | 要求是路由触发器（`Load when...`） |
| **踩坑积累** | 踩坑经验写在SKILL.md末尾 | 独立`references/gotchas.md` |
| **迭代方式** | 定期审计 | 失败用例驱动 |
| **共同点** | 上下文Token意识 | 上下文Token意识 |

**互补关系**：STOM v2.0 管「结构」，Perplexity 管「内容」。

---

## 七、六个可落地的Takeaway

1. **Skill不是新文档**——别把README当Skill写
2. **Description是最难的一行**——它决定路由，不是描述，必须以`Load when...`开头
3. **Gotcha是无价的**——出错就加一条，长期飞轮
4. **每个Skill都是税**——加之前先问"agent没它会不会出错"
5. **多模型评测**——别只跟一个模型耦合，同一Skill需在GPT/Claude等不同模型上验证
6. **Action at a distance是真实存在的**——新加一个Skill可能让另一个不相关的Skill变差

---

*整理日期：2026-05-12*
