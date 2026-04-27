---
name: tushare-data
description: "Tushare 金融数据获取层。负责所有数据获取：行情、财报、估值、资金流、新闻、宏观等。与 stock-analyst 配合使用：本 Skill 取数据，stock-analyst 做分析。触发词：查行情、查财报、看走势、拉数据、导出数据、资金流向、板块分析、北向资金、宏观指标、CPI、PMI、龙虎榜、涨停、估值"
author: tushare.pro
version: 1.2.0
credentials:
  - name: TUSHARE_TOKEN
    description: Tushare Token，用于认证和授权访问Tushare数据服务。
    how_to_get: "https://tushare.pro/register"
requirements:
  python: 3.7+
  packages:
    - name: tushare
  environment_variables:
    - name: TUSHARE_TOKEN
      required: false
      sensitive: true
  network_access true
references:
  - path: references/workflow-templates.md
    desc: "9个详细任务模板（单票行情/对比/财务/估值/资金流/板块/公告/导出/综合简报）"
  - path: references/examples.md
    desc: "按任务类型分组的典型查询示例"
  - path: references/detailed-rules.md
    desc: "数据质量清单/缓存策略/错误分层处理/自然语言映射表"
---

# tushare-data v1.2 — 精简版

> **Token 优化**：v1.2 将详细模板和规则移至 `references/` 目录。
> 主文件只保留执行时必须参考的核心信息（~350行）。
> 详细内容请 `read_file references/xxx.md` 按需读取。

## 定位

把自然语言财经数据请求 → 可执行的 Tushare 数据工作流。

## 适用场景

| 类别 | 触发示例 |
|------|---------|
| 行情趋势 | 看下 XX 最近怎么样 / 今年涨了多少 / 最近有没有放量 |
| 财务估值 | 看 XX 财报 / 利润趋势 / ROE / PE PB / 现金流 |
| 对比筛选 | XX 和 YY 谁更强 / 筛高 ROE 低负债 / 排前十 |
| 板块指数 | 哪个板块最强 / 半导体怎么样 / 成分股有哪些 |
| 资金情绪 | 资金在买什么 / 北向流向 / 龙虎榜 |
| 公告新闻 | 有什么公告 / 催化消息 / 政策面 |
| 宏观跨市场 | CPI PMI / 市场风格 / 港股美股 |
| 数据导出 | 导出行情 CSV / 回测数据表 |

**不适用**：买卖建议、自动下单、毫秒级实时交易、复杂回测引擎实现、无权限时伪造数据。

---

## 环境前置校验（每次必做）

```
1. Python 3.7+ 可用？
2. tushare 包已安装？
3. TUSHARE_TOKEN 环境变量存在？
4. 冒烟测试？(trade_cal 轻量调用)
5. 高权限接口？→ 提前提示积分限制
```

缺失 token 时立即告知修复路径，不等到主查询失败。

---

## 意图 → 接口速查表

> 详细说明见 `references/detailed-rules.md` 自然语言映射表

| # | 意图 | 核心接口 | 辅助接口 |
|---|------|---------|---------|
| 1 | 行情/趋势 | daily, pro_bar, daily_basic | weekly, monthly, stk_mins |
| 2 | 标的识别 | stock_basic, stock_company | fund_basic, index_basic, stock_st |
| 3 | 财务/质量 | income, fina_indicator | balancesheet, cashflow, forecast, express |
| 4 | 估值 | daily_basic, fina_indicator | - |
| 5 | 资金流 | moneyflow, moneyflow_hsgt | hsgt_top10, top_list, top_inst |
| 6 | 板块/主题 | index_daily, index_classify, sw_daily | ths_index, ths_member, dc_index |
| 7 | 打板/情绪 | limit_list_d, limit_step | kpl_list, dc_hot, ths_hot |
| 8 | 公告/新闻 | anns_d, news, research_report | major_news, npr |
| 9 | 宏观/跨市 | cn_cpi, cn_pmi, cn_gdp | cn_ppi, shibor, us_tycr, us_daily, hk_daily |
| 10 | 数据导出 | 取决于上游任务 | 统一输出规则 |

---

## 标的解析规则

- **代码格式**：统一为 `600519.SH` / `000001.SZ`（必须带后缀）
- **默认市场**：A 股；用户提港股/美股/基金/债券/期货时切换
- **时间默认值**：
  - "最近走势" → 近 20 个交易日
  - "最近一段时间" → 近 3 个月
  - "财报" → 最近 8 季度 + 年度
  - "资金流" → 近 5-20T（按粒度调整）
  - "宏观" → 最近 6-12 期
- **板块口径未指定时**：行业→申万/中信；概念→同花顺/东方财富

---

## 输入规范化 Checklist

- [ ] 日期格式 `YYYYMMDD`
- [ ] `start_date <= end_date`
- [ ] 未来日期自动裁剪
- [ ] 裸代码 `000001` 不盲猜，能补全则补全规则说明
- [ ] 冲突参数先裁决（trade_date vs start/end）

---

## 数据拉取核心规则

### 文档先行
写请求前确认：接口名正确、必填/可选参数、返回字段、积分限制。不要仅凭记忆硬写字段名。

### 分段策略
长区间不一次性全拉：
- 日线/周线/月线 → 按年或季度切片
- 财报 → 按年份/报告期切片
- 分钟数据 → 按月/周切片
- 大批量多标的 → 按标的分批 + 日期分段

### 重试与限流
- ✅ 仅瞬时错误重试（网络抖动/超时/429）
- ❌ 参数错误/权限不足/字段错误不盲重试
- 批量拉取加节流防撞限

### 分段合并
合并 → 去重 → 主键排序 → 记录失败分段 → 部分成功明确告知

> 详细的数据质量检查清单见 `references/detailed-rules.md`

---

## 输出规范

### 结构（除非用户只要原始表）

1. **一句话结论**
2. **数据范围与口径**
3. **关键指标 / 表格**
4. **异常点 / 风险点 / 限制**
5. **本地输出文件路径**（如有）

### 交付形态选择

| 任务规模 | 形态 |
|---------|------|
| 小结果 | Markdown 摘要 + 简短表格 |
| 中等数据表 | CSV |
| 大规模/后续分析 | Parquet |
| 需复用流程 | 附 Python 脚本 |
| 需可视化 | 图表 PNG 或可绘制说明 |

### 元信息记录
生成数据文件时附带：接口名、参数、拉取时间、行数、字段列表、是否有失败段。

---

## 核心接口集（80% 任务覆盖）

```
stock_basic, trade_cal, daily, pro_bar, daily_basic,
fina_indicator, income, balancesheet, cashflow,
forecast, express, moneyflow, moneyflow_hsgt,
hsgt_top10, top_list, index_basic, index_daily,
index_classify, sw_daily, ths_index, ths_member,
limit_list_d, limit_step, news, major_news,
research_report, anns_d, cn_cpi, cn_pmi, us_tycr
```

完整接口列表 → `references/数据接口.md`

---

## 最佳实践

1. 先理解任务再选接口，不从接口反推任务
2. 能少取就少取，先核心数据再扩展
3. 先给结论再给证据
4. 模糊中文表达有合理默认口径
5. 大任务先给计划再开跑
6. 导出任务保留脚本+元信息+路径

### Quick Rule

当用户说"看走势/查财报/比较公司/看板块/看资金流/梳理公告/看宏观/导出数据"时：

❌ 不要先想"有哪些接口"
✅ 先想："这是什么任务？走哪条工作流？结果怎么交付才真正有用？"

详细工作流模板 → `references/workflow-templates.md`
示例 → `references/examples.md`

---

## 与 stock-analyst 的协作

用户说"分析XXX"时需要两 Skill 配合：

```
"分析300263"
  → tushare-data: daily/daily_basic/income/fina_indicator/moneyflow/news/forecast → JSON
  → stock-analyst: 读JSON → full_analysis.py → 技术指标+形态+缠论+信号共振+情绪指数
```

| 场景 | 用什么 |
|------|--------|
| 纯数据查询（行情/财报/导出CSV） | 仅 tushare-data |
| 需要分析（技术分析/形态/评分） | tushare-data + stock-analyst |

**分工边界**：stock-analyst v4.0 已移除数据获取能力，不要让它自己取数据。

---

## 📚 踩坑经验

> 由 AI 在实际调用中自动积累，请勿手动删除。
> 格式：`- 接口/场景：经验要点`

- daily / 查询单只股票：ts_code 必须带交易所后缀（000001.SZ），不能只传数字代码
- moneyflow / 个股资金流向：需要 ts_code + trade_date 范围，单次最多返回约100条
- daily_basic / 每日指标：字段 pe_ttm 比 pe 更常用，pb 就是市净率
- fina_indicator / 财务指标：返回数据按 ann_date 降序，取前 5-8 期即可

---

## 🔄 触发词自进化规则

当用户输入某种表述但本 Skill 未被自动激活时：
1. 分析关键表述 → 抽象为通用触发词
2. 追加到 YAML frontmatter `description` 字段末尾
3. 不重复添加已存在的触发词
