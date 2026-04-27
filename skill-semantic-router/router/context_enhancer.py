# -*- coding: utf-8 -*-
"""
context_enhancer.py — 上下文感知 Query 增强
==============================================
从对话历史中提取实体（股票名、公司名等），
注入当前 Query 以提升路由准确性。

遵循 STOM 方法论：单一职责，~50 行。
"""

import re

from config import ENTITY_PATTERNS


def extract_entities(text: str) -> list[str]:
    """
    从文本中提取金融/商业实体。
    
    当前支持：
      - 股票代码模式 (000001.SZ / 600519.SH 等)
      - 常见公司/股票名称（可配置扩展）
    
    Args:
        text: 输入文本
        
    Returns:
        去重后的实体列表
    """
    entities = []

    # 股票代码
    stock_codes = re.findall(r"\b[036]\d{5}\.[SA][ZH]\b", text)
    entities.extend(stock_codes)

    # 公司/股票名称（从 config.py 读取）
    for pattern in ENTITY_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        entities.extend(matches)

    return list(set(entities))


def augment_query(
    query: str,
    history: list[dict],
    used_skills: list[str],
) -> str:
    """
    上下文感知 Query 增强。
    
    策略：
      1. 从最近 3 轮对话中提取实体 → 拼接到 query
      2. 附上最近使用的 skill 名称 → 提升语义连续性
    
    Args:
        query: 用户原始输入
        history: 对话历史 [{role, content}, ...]
        used_skills: 本轮会话已使用的 skill 列表
        
    Returns:
        增强后的 query 字符串
    """
    # 提取最近对话中的实体
    recent_text = " ".join(
        msg.get("content", "") for msg in history[-3:]
    )
    entities = extract_entities(recent_text)

    augmented = query
    if entities:
        augmented += f" [实体上下文: {' '.join(entities)}]"
    if used_skills:
        augmented += f" [上文工具: {' '.join(used_skills[-2:])}]"

    return augmented
