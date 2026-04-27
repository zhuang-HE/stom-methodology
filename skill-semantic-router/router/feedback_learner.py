# -*- coding: utf-8 -*-
"""
feedback_learner.py — 自学习反馈模块
======================================
当用户纠正路由结果时，自动提取新触发词，
写回 skill_index.json 并重建 TF-IDF 索引。

遵循 STOM 方法论：单一职责，~45 行。
"""

from collections import Counter

from router.tfidf_engine import build_tfidf_index, tokenize

# 模块级停用词表（提取触发词时过滤）
DEFAULT_STOPWORDS: frozenset[str] = frozenset({
    "帮我", "一下", "看看", "给我", "的", "了", "呢", "吗",
    "请", "能", "这个", "那个", "怎么", "什么", "如何", "能否",
})


class SkillFeedbackLearner:
    """
    路由纠错自学习器。
    
    使用方式:
        learner = SkillFeedbackLearner(router)
        msg = learner.on_correction("拉一下利润表", "finance-data-retrieval")
        # → "已为 [finance-data-retrieval] 添加触发词: ['利润表', '拉一下']"
    
    注意:
        会直接修改 router 的索引和向量，并持久化到 JSON 文件。
    """

    def __init__(self, router, stopwords: set[str] | None = None):
        self.router = router
        self.stopwords = stopwords or DEFAULT_STOPWORDS

    def on_correction(
        self,
        original_query: str,
        correct_skill_id: str,
    ) -> str:
        """
        处理用户纠正，自动学习新触发词。
        
        Args:
            original_query:     用户原始输入
            correct_skill_id:   正确的 skill ID
            
        Returns:
            操作结果描述字符串
        """
        # 提取 query 中的关键词（去停用词，保留长度>1的 token）
        tokens = tokenize(original_query)
        new_triggers = [t for t in tokens
                        if t not in self.stopwords and len(t) > 1]

        # 写回索引
        for skill in self.router.skills:
            if skill["id"] == correct_skill_id:
                existing = set(skill.get("triggers", []))
                added = [t for t in new_triggers if t not in existing]
                skill["triggers"].extend(added)
                break

        # 持久化到 JSON
        self.router.index["skills"] = self.router.skills
        with open(self.router.index_path, "w", encoding="utf-8") as f:
            import json as _json
            _json.dump(self.router.index, f, ensure_ascii=False, indent=2)

        # 重建 TF-IDF 索引（使新触发词立即生效）
        self.router.idf, self.router.skill_vecs = build_tfidf_index(
            self.router.skills
        )

        return f"已为 [{correct_skill_id}] 添加触发词: {added}"
