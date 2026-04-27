# skill_index.json 字段说明

## 顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `version` | string | 索引版本号，遵循 semver |
| `generated_at` | string | 生成日期 |
| `description` | string | 索引文件说明 |
| `schema` | object | 各字段的含义说明（文档用途） |
| `skills` | array | Skill 元数据列表 |
| `routing_rules` | object | 路由规则配置（可选） |

---

## Skill 对象字段

```json
{
  "id": "finance-data-retrieval",
  "name": "finance-data-retrieval",
  "category": "金融数据",
  "description": "...",
  "triggers": ["..."],
  "path": "...",
  "complexity": 2,
  "priority": 1
}
```

### `id`
- 类型：string
- 说明：Skill 的唯一标识符，路由结果中返回此字段
- 约定：与 Skill 目录名一致，小写 kebab-case
- 示例：`"finance-data-retrieval"`

### `name`
- 类型：string
- 说明：Skill 展示名称，通常与 id 相同
- 用途：面向用户展示时使用

### `category`
- 类型：string
- 说明：Skill 所属领域分类，用于类别先验 Boost
- 当前有效类别：`代码质量` / `文档` / `版本控制` / `金融数据` / `金融分析` / `投行` / `产品管理` / `数据分析` / `研究调研` / `办公文档` / `股票分析` / `工作流` / `外部集成`

### `description`
- 类型：string
- 说明：**最重要的字段**，用于 TF-IDF 向量化。描述越准确、词汇越丰富，路由准确率越高
- 最佳实践：
  - 包含中文描述和英文描述（双语检索）
  - 覆盖 Skill 的核心功能、适用场景、典型输出
  - 长度建议 50-200 字
- 示例：`"NeoData 自然语言通用金融数据搜索。查询股票行情、财务报表、基金净值...Real-time financial data search, stock quotes..."`

### `triggers`
- 类型：string[]
- 说明：关键词列表，兼容旧有关键词匹配机制，同时也会拼接进 description 参与 TF-IDF 向量化
- 最佳实践：
  - 覆盖用户的高频表达方式
  - 包含同义词、缩写、常见错别字
  - 通过 `SkillFeedbackLearner` 自动维护和扩充

### `path`
- 类型：string
- 说明：SKILL.md 文件的路径，供路由器加载完整 Skill 定义
- 支持绝对路径和相对路径，`~` 会被展开为用户主目录

### `complexity`
- 类型：integer (1-3)
- 说明：Skill 的执行复杂度
  - `1`：简单，单步完成（如 git commit 建议）
  - `2`：中等，需要多步或外部调用（如文档生成）
  - `3`：复杂，需要多轮交互或长时间执行（如 DCF 建模）
- 用途：路由器可根据复杂度决定是否需要用户确认

### `priority`
- 类型：integer（越小越优先）
- 说明：同一 category 内多个 Skill 分数相近时的决胜依据
- 通常 `1` 为最优先，数字越大优先级越低
- 结合 `CATEGORY_PRIORITY` 规则使用

---

## routing_rules 字段（可选）

用于在 JSON 中配置路由规则（当前路由器也支持在代码中硬编码）：

```json
{
  "routing_rules": {
    "category_hints": {
      "股价|行情|财报": ["金融数据"]
    },
    "exact_overrides": {
      "\\bdcf\\b": "dcf-model"
    },
    "category_priority": {
      "金融数据": ["neodata-financial-search", "finance-data-retrieval"]
    }
  }
}
```

---

## 添加新 Skill 的检查清单

- [ ] `id` 与 Skill 目录名一致
- [ ] `description` 中英文均有，覆盖核心功能词
- [ ] `triggers` 包含至少 5 个常见触发表达
- [ ] `category` 与现有类别体系对齐（或新增类别时同步更新路由规则）
- [ ] `complexity` 和 `priority` 已合理赋值
- [ ] 运行 `python skill_router.py` 确认准确率无下降
