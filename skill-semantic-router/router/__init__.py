# -*- coding: utf-8 -*-
"""
router — 语义路由引擎子包
=========================
导出核心类，对外提供统一入口。

遵循 STOM 方法论：SKILL.md ≤350 行 → 本文件为薄代理层。
"""

from router.tfidf_engine import tokenize, build_tfidf_index, cosine_similarity
from router.context_enhancer import extract_entities, augment_query
from router.skill_router import SkillRouter
from router.feedback_learner import SkillFeedbackLearner

__all__ = [
    "tokenize",
    "build_tfidf_index", 
    "cosine_similarity",
    "extract_entities",
    "augment_query",
    "SkillRouter",
    "SkillFeedbackLearner",
]
