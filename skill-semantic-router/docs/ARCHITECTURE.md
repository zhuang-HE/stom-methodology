# 架构设计文档

## 总览

WorkBuddy Skill Semantic Router 是一套三层渐进式路由框架，解决 AI Agent 系统中多 Skill 的精准分发问题。

## 问题定义

在 AI Agent 系统中，通常存在数十个专项 Skill（工具），每个 Skill 处理特定领域的任务。核心挑战是：**给定用户的自然语言输入，如何准确路由到正确的 Skill？**

### 传统方案的局限

```
用户输入 → 关键词匹配 → 命中 → 触发 Skill
                      → 未命中 → fallback（通用处理）
```

**痛点：**
- 触发词需要人工穷举，维护成本高
- 用户表达多样，关键词覆盖率天花板约 70%
- 多 Skill 歧义时无法优雅处理
- 完全无法利用对话上下文

---

## 三层架构详解

### Layer 0：精确关键词快速通道

**目标**：处理高频、无歧义的专业术语

```python
EXACT_OVERRIDE = {
    r'\bprd\b|产品需求|功能需求': "product-management-workflows",
    r'\blbo\b|杠杆收购':          "lbo-model",
    r'\bdcf\b|折现现金流':         "dcf-model",
    r'\bcim\b|投资备忘录':         "cim-builder",
}
```

- 使用正则匹配，优先级最高
- 只覆盖"说了这个词，意图100%确定"的场景
- confidence = 1.0，直接触发，绕过后续向量计算
- **设计原则**：宁可少覆盖，不误触发

### Layer 1：上下文感知 Query 增强

**目标**：把对话历史中的信息注入当前 Query

```
"再看看它的利润表"
    ↓ 提取历史实体
    ↓ [历史: 贵州茅台今日收盘价...]
    ↓
"再看看它的利润表 [实体上下文: 贵州茅台] [上文工具: neodata-financial-search]"
```

**实体提取规则：**
- 股票代码：`[036]\d{5}\.[SA][ZH]`
- 公司名：预置常见公司名正则（可扩展）
- 取最近 3 轮对话，避免噪声引入

**上文工具注入：**
- 最近 2 个使用的 Skill 名称写入增强 Query
- 帮助向量检索识别"同类任务延续"的意图

### Layer 2：TF-IDF 语义向量检索

**目标**：捕捉语义相似度，覆盖关键词穷举无法处理的表达

#### 向量化方案选型

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 关键词匹配 | 零延迟，零资源 | 覆盖率低 | Skill 数量 <10 |
| **TF-IDF（本方案）** | 纯 Python，无外部依赖 | 无深层语义 | Skill 数量 10-100 |
| Dense Embedding | 语义理解强 | 需要 GPU/API | Skill 数量 >100 |

#### 中文分词策略

```python
def tokenize(text: str) -> list[str]:
    # 英文词 + 数字
    en_tokens = re.findall(r'[a-z][a-z0-9]*', text.lower())
    
    # 中文：单字 + bigram（相邻两字）+ trigram（相邻三字）
    for cn_seq in re.findall(r'[\u4e00-\u9fff]+', text):
        tokens.extend(list(cn_seq))                          # 单字
        tokens.extend(cn_seq[i:i+2] for i in range(len-1))  # bigram
        tokens.extend(cn_seq[i:i+3] for i in range(len-2))  # trigram
```

**为什么不用 jieba：**
- 去掉一个外部依赖
- bigram/trigram 覆盖分词错误场景
- 对短文本（Skill 描述 / 用户输入）效果接近

#### 类别先验 Boost

当 Query 命中领域词时，对该领域的所有 Skill 分数乘以 1.5：

```python
CATEGORY_HINTS = {
    r'cpi|gdp|股价|行情|财报': ["金融数据"],  # → 金融类 Skill x1.5
    r'prd|需求文档|路线图':     ["产品管理"],  # → 产品类 Skill x1.5
}
```

**类别内优先级仲裁：**
当 top-1 和 top-2 分数差 < 15% 且属同一类别，按 `CATEGORY_PRIORITY` 决定顺序：

```python
CATEGORY_PRIORITY = {
    "金融数据": ["neodata-financial-search", "finance-data-retrieval", "stock-analyst"],
}
```

### Layer 3：置信度阈值决策

```
confidence ≥ CONFIDENCE_HIGH (0.35) → action = "invoke"   直接触发
confidence ≥ CONFIDENCE_LOW  (0.10) → action = "confirm"  询问用户确认
confidence <  CONFIDENCE_LOW        → action = "fallback"  降级到通用处理
```

**返回结构：**
```json
{
  "action": "invoke",
  "skill": "finance-data-retrieval",
  "skill_name": "finance-data-retrieval",
  "confidence": 0.412,
  "candidates": [
    {"id": "finance-data-retrieval", "score": 0.412},
    {"id": "neodata-financial-search", "score": 0.380},
    {"id": "stock-analyst", "score": 0.201}
  ],
  "augmented_query": "再看看它的利润表 [实体上下文: 贵州茅台]",
  "reason": "高置信匹配 (0.412 ≥ 0.35)"
}
```

---

## 自学习模块

### 反馈驱动的触发词更新

```
用户纠正路由 → 提取 Query 中关键词 → 去停用词 → 写回 skill_index.json → 重建向量索引
```

**效果：**
- 每次纠错都是训练信号
- 索引随时间累积改进
- 无需重新训练模型

---

## 扩展路线图

### 短期（低成本高收益）

1. **Dense Embedding 替换 TF-IDF**：接入 bge-m3（本地）或 text-embedding-3-small（API），语义理解质量大幅提升
2. **FAISS 向量库**：Skill 数量超过 100 时，内存 numpy 计算瓶颈出现，切换 FAISS

### 中期

3. **LLM Rerank**：中等置信度（0.10-0.35）时，用 LLM 做二次判断，减少 confirm 频率
4. **实体识别增强**：接入 NER 模型替代规则，覆盖更多实体类型

### 长期

5. **ReAct 调度器**：对复杂多步任务，先 Plan（分解 + 预分配 Skill），再 Execute
6. **多 Skill 协同**：某些任务需要多个 Skill 串联，路由器支持返回有序 Skill 链
