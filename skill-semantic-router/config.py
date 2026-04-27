# -*- coding: utf-8 -*-
"""
config.py — Skill Semantic Router 统一配置层
=============================================
所有阈值、路径、Boost 系数、实体库集中管理。
修改路由行为只需改这里，无需动业务代码。

遵循 STOM 方法论：单一职责，≤50 行。
"""

from pathlib import Path

# ─── 路径配置 ───────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
DEFAULT_INDEX_PATH = PROJECT_ROOT / "skill_index.json"
DEFAULT_CHANGELOG_PATH = PROJECT_ROOT / "index_changelog.json"

# 默认扫描根目录（用户级 + 插件级）
DEFAULT_SCAN_ROOTS = [
    Path("~/.workbuddy/skills"),
    Path("~/.workbuddy/plugins/marketplaces"),
]

# ─── 路由决策阈值 ────────────────────────────────────────────

CONFIDENCE_HIGH = 0.35   # ≥ 此值 → 直接触发 (invoke)
CONFIDENCE_LOW = 0.10    # ≥ 此值 → 询问确认 (confirm)
TOP_K = 3               # 返回候选数量

# ─── Boost 系数 ───────────────────────────────────────────────

SOURCE_BOOST = {
    "user": 1.20,       # 用户级 skill +20% 优先
    "plugin": 1.00,     # 插件级 skill 不变
}

CATEGORY_BOOST_FACTOR = 2.0  # 命中类别时，对应 skill 分数 ×2

# ─── 来源优先级 ───────────────────────────────────────────────

# 同类别内，排在前面的 skill 在分数接近时优先
CATEGORY_PRIORITY: dict[str, list[str]] = {
    "金融数据": ["neodata-financial-search", "finance-data-retrieval", "stock-analyst"],
    "产品管理": ["product-management-workflows"],
    "办公文档": ["pptx", "docx", "xlsx", "pdf"],
}

# ─── 精确关键词快速通道（最高优先级，绕过向量计算） ─────────

EXACT_OVERRIDE: dict[str, str] = {
    r"\bprd\b|产品需求|功能需求|需求文档|用户故事|产品迭代": "product-management-workflows",
    r"\blbo\b|杠杆收购": "lbo-model",
    r"\bdcf\b|折现现金流": "dcf-model",
    r"\bcim\b|投资备忘录": "cim-builder",
    r"memory\.md|记忆整理|工作记忆": "memory-consolidation",
    r"做个\s*ppt|做\s*ppt|制作\s*ppt|ppt.*给我": "pptx",
}

# ─── 类别先验提示词 → 对应类别列表 ─────────────────────────

CATEGORY_HINTS: dict[str, list[str]] = {
    r"cpi|gdp|pmi|ppi|通胀|利率|m2|宏观指标|经济数据": ["金融数据"],
    r"股价|行情|财报|涨跌|基金|板块|汇率|黄金|原油": ["金融数据"],
    r"prd|需求文档|产品需求|功能规划|路线图|用户故事|迭代|产品经理": ["产品管理"],
}

# ─── 实体提取规则（上下文感知用） ───────────────────────────

# 公司/股票实体模式列表（可按需扩展）
ENTITY_PATTERNS: list[str] = [
    r"贵州茅台|茅台",
    r"腾讯|TENCENT",
    r"阿里|ALIBABA|阿里巴巴",
    r"宁德时代|CATL",
    r"比亚迪|BYD",
    r"中国平安",
    r"招商银行",
    r"万科|碧桂园|恒大",
    r"华为",
    r"字节跳动",
]
