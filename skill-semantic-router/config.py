# -*- coding: utf-8 -*-
"""
config.py — Skill Semantic Router 统一配置层（v2.2 外部化版）
=============================================================
所有阈值、路径、Boost 系数、实体库集中管理。
支持从 routing_rules.json 外部加载规则数据，
文件不存在时 fallback 到内置默认值。

遵循 STOM 方法论：单一职责，≤80 行。
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── 路径配置 ───────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
DEFAULT_INDEX_PATH = PROJECT_ROOT / "skill_index.json"
DEFAULT_CHANGELOG_PATH = PROJECT_ROOT / "index_changelog.json"
ROUTING_RULES_PATH = PROJECT_ROOT / "routing_rules.json"

# 默认扫描根目录（用户级 + 插件级）
DEFAULT_SCAN_ROOTS = [
    Path("~/.workbuddy/skills"),
    Path("~/.workbuddy/plugins/marketplaces"),
]

# ─── 分词器配置 ───────────────────────────────────────────────

# 可选值: "ngram"（内置 bigram/trigram）, "jieba"（需 pip install jieba）
TOKENIZER = "ngram"

# BM25 参数
BM25_K1 = 1.2       # 词频饱和参数
BM25_B = 0.75       # 文档长度归一化参数

# 缓存配置
ROUTING_CACHE_SIZE = 256   # LRU 缓存容量

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

# ─── 内置默认规则（routing_rules.json 不存在时的 fallback） ──

_DEFAULT_EXACT_OVERRIDE: dict[str, str] = {
    r"\bprd\b|产品需求|功能需求|需求文档|用户故事|产品迭代": "product-management-workflows",
    r"\blbo\b|杠杆收购": "lbo-model",
    r"\bdcf\b|折现现金流": "dcf-model",
    r"\bcim\b|投资备忘录": "cim-builder",
    r"memory\.md|记忆整理|工作记忆": "memory-consolidation",
    r"做个\s*ppt|做\s*ppt|制作\s*ppt|ppt.*给我": "pptx",
}

_DEFAULT_CATEGORY_HINTS: dict[str, list[str]] = {
    r"cpi|gdp|pmi|ppi|通胀|利率|m2|宏观指标|经济数据": ["金融数据"],
    r"股价|行情|财报|涨跌|基金|板块|汇率|黄金|原油": ["金融数据"],
    r"prd|需求文档|产品需求|功能规划|路线图|用户故事|迭代|产品经理": ["产品管理"],
}

_DEFAULT_CATEGORY_PRIORITY: dict[str, list[str]] = {
    "金融数据": ["neodata-financial-search", "finance-data-retrieval", "stock-analyst"],
    "产品管理": ["product-management-workflows"],
    "办公文档": ["pptx", "docx", "xlsx", "pdf"],
}

_DEFAULT_ENTITY_PATTERNS: list[str] = [
    r"贵州茅台|茅台", r"腾讯|TENCENT", r"阿里|ALIBABA|阿里巴巴",
    r"宁德时代|CATL", r"比亚迪|BYD", r"中国平安", r"招商银行",
    r"万科|碧桂园|恒大", r"华为", r"字节跳动",
]


def _load_rules_json() -> dict:
    """从 routing_rules.json 加载外部规则，失败返回空 dict"""
    if not ROUTING_RULES_PATH.exists():
        logger.info("路由规则文件不存在，使用内置默认值: %s", ROUTING_RULES_PATH)
        return {}
    try:
        with open(ROUTING_RULES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("路由规则 JSON 解析失败，使用内置默认值: %s", e)
        return {}


# 从外部 JSON 加载（或 fallback 到内置默认值）
_rules_data = _load_rules_json()

EXACT_OVERRIDE: dict[str, str] = _rules_data.get("exact_override", _DEFAULT_EXACT_OVERRIDE)
CATEGORY_HINTS: dict[str, list[str]] = _rules_data.get("category_hint", _DEFAULT_CATEGORY_HINTS)
CATEGORY_PRIORITY: dict[str, list[str]] = _rules_data.get("category_priority", _DEFAULT_CATEGORY_PRIORITY)
ENTITY_PATTERNS: list[str] = _rules_data.get("entity_patterns", _DEFAULT_ENTITY_PATTERNS)
