# -*- coding: utf-8 -*-
"""
skill_router.py — 核心路由器（STOM 重构版）
============================================
四层路由架构：
  Layer 0: 精确关键词快速通道（最高优先级）
  Layer 1: 上下文感知 Query 增强
  Layer 2: TF-IDF 语义向量检索 + Boost 策略
  Layer 3: 置信度阈值决策

遵循 STOM 方法论：单一职责（路由决策），~220 行。
"""

import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 同包导入
from router.tfidf_engine import build_tfidf_index, build_inverted_index, cosine_similarity, tokenize
from router.context_enhancer import augment_query
# 跨包导入
from config import (
    DEFAULT_INDEX_PATH,
    CONFIDENCE_HIGH, CONFIDENCE_LOW, TOP_K,
    SOURCE_BOOST, CATEGORY_BOOST_FACTOR,
    CATEGORY_PRIORITY, EXACT_OVERRIDE, CATEGORY_HINTS,
)


class SkillRouter:
    """
    Skill 语义路由器。
    
    使用方式:
        router = SkillRouter()
        result = router.route("帮我看看这段代码有没有 bug")
        # → {"action": "invoke", "skill": "code-review", "confidence": 0.412, ...}
    """

    def __init__(self, index_path: str = str(DEFAULT_INDEX_PATH), auto_sync: bool = False):
        self.index_path = index_path
        self.auto_sync = auto_sync

        if auto_sync:
            self._auto_sync_index()

        self._load_and_build()

    def _auto_sync_index(self):
        """自动扫描并同步索引"""
        try:
            from indexer.index_manager import SkillIndexManager
            mgr = SkillIndexManager(index_path=self.index_path)
            mgr.full_sync(remove_missing=False)
        except Exception as e:
            logger.warning("自动同步跳过: %s", e)

    # ─── 索引加载 ──────────────────────────────────────

    def _load_and_build(self):
        """加载 skill_index.json 并构建 TF-IDF 向量"""
        index_file = Path(self.index_path)
        if not index_file.exists():
            raise FileNotFoundError(
                f"Skill 索引文件不存在: {index_file}\n"
                f"请先运行: python -m indexer.index_manager --sync\n"
                f"或检查 DEFAULT_INDEX_PATH 配置是否正确"
            )

        with open(index_file, encoding="utf-8") as f:
            self.index = json.load(f)
        self.skills = self.index["skills"]
        self.routing_rules = self.index.get("routing_rules", {})

        self.idf, self.skill_vecs = build_tfidf_index(self.skills)
        # O(1) 技能查找索引（替代逐个遍历）
        self._skill_map: dict[str, dict] = {s["id"]: s for s in self.skills}
        # 倒排索引：token → 命中的 skill 索引集合（O(N)→O(K) 检索加速）
        self._inv_index = build_inverted_index(self.skill_vecs)
        logger.info("已加载 %d 个 skill，索引构建完成（倒排索引 token 数: %d）",
                     len(self.skills), len(self._inv_index))

    def reload(self):
        """重新加载索引（skill 变更后调用）"""
        self._load_and_build()

    # ─── 向量查询 ──────────────────────────────────────

    def _query_vec(self, query: str) -> dict:
        """将 query 文本转为 TF-IDF 稀疏向量"""
        tokens = tokenize(query)
        tf = Counter(tokens)
        return {token: (count / len(tokens)) * self.idf.get(token, 0)
                for token, count in tf.items()} if tokens else {}

    # ─── 主路由方法 ────────────────────────────────────

    def route(
        self,
        query: str,
        history: Optional[list[dict]] = None,
        used_skills: Optional[list[str]] = None,
        top_k: int = TOP_K,
    ) -> dict:
        """
        执行语义路由。
        
        Args:
            query:       用户输入
            history:     对话历史 [{role, content}, ...]
            used_skills: 本轮会话已使用的 skill 列表
            top_k:       返回候选数量
            
        Returns:
            {
              "action": "invoke" | "confirm" | "fallback",
              "skill":  skill_id or None,
              "skill_name": str,
              "confidence": float,
              "candidates": [{"id", "score"}, ...],
              "augmented_query": str,
              "reason": str,
            }
        """
        history = history or []
        used_skills = used_skills or []

        # Layer 0: 精确关键词快速通道
        query_lower = query.lower()
        for pattern, skill_id in EXACT_OVERRIDE.items():
            if re.search(pattern, query_lower):
                skill = self._skill_map.get(skill_id)
                if skill:
                    return {
                        "action": "invoke",
                        "skill": skill_id,
                        "skill_name": skill["name"],
                        "confidence": 1.0,
                        "candidates": [{"id": skill_id, "score": 1.0}],
                        "augmented_query": query,
                        "reason": f"精确关键词匹配: {pattern}",
                    }

        # Layer 1: 上下文增强
        augmented = augment_query(query, history, used_skills)

        # Layer 2: 向量检索 + Boost（倒排索引加速：O(N) → O(K)）
        q_vec = self._query_vec(augmented)
        if not q_vec:
            return {"action": "fallback", "skill": None, "candidates": [],
                    "augmented_query": augmented, "reason": "query 向量为空"}

        # 通过倒排索引找到候选 skill 集合（只计算命中的）
        candidate_indices: set[int] = set()
        for token in q_vec:
            candidate_indices.update(self._inv_index.get(token, set()))

        # 如果无候选命中，fallback 到全量扫描兜底
        if not candidate_indices:
            scores = [
                (self.skills[i]["id"], cosine_similarity(q_vec, self.skill_vecs[i]))
                for i in range(len(self.skills))
            ]
        else:
            scores = [
                (self.skills[i]["id"], cosine_similarity(q_vec, self.skill_vecs[i]))
                for i in candidate_indices
            ]

        # 兜底：如果倒排索引候选数 < total/10 且分数极低，补充全量扫描
        if len(candidate_indices) > 0 and len(candidate_indices) < len(self.skills) // 10:
            scores_full = [
                (self.skills[i]["id"], cosine_similarity(q_vec, self.skill_vecs[i]))
                for i in range(len(self.skills)) if i not in candidate_indices
            ]
            if scores_full and scores_full[0][1] > (scores[0][1] if scores else 0):
                scores = scores_full + scores

        scores.sort(key=lambda x: -x[1])

        scores = self._apply_source_boost(scores)
        scores = self._apply_category_boost(scores, augmented)

        top_candidates = scores[:top_k]

        # Layer 3: 置信度决策
        top_id, top_score = top_candidates[0]
        top_skill = self._skill_map.get(top_id)
        top_name = top_skill["name"] if top_skill else top_id

        if top_score >= CONFIDENCE_HIGH:
            action = "invoke"
            reason = f"高置信匹配 ({top_score:.3f} ≥ {CONFIDENCE_HIGH})"
        elif top_score >= CONFIDENCE_LOW:
            action = "confirm"
            reason = f"中置信，建议确认 ({top_score:.3f})"
        else:
            action = "fallback"
            reason = f"低置信，无明确匹配 ({top_score:.3f} < {CONFIDENCE_LOW})"

        return {
            "action": action,
            "skill": top_id if action != "fallback" else None,
            "skill_name": top_name,
            "confidence": round(top_score, 4),
            "candidates": [
                {"id": sid, "score": round(sc, 4)} for sid, sc in top_candidates
            ],
            "augmented_query": augmented,
            "reason": reason,
        }

    # ─── Boost 策略 ────────────────────────────────────

    def _apply_source_boost(
        self, scores: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        """用户级 skill 在分数接近时优先（+20%）"""
        boosted = []
        for skill_id, score in scores:
            skill = self._skill_map.get(skill_id)
            source = skill.get("source", "plugin") if skill else "plugin"
            factor = SOURCE_BOOST.get(source, 1.0)
            boosted.append((skill_id, score * factor))
        return sorted(boosted, key=lambda x: -x[1])

    def _apply_category_boost(
        self, scores: list[tuple[str, float]], query: str
    ) -> list[tuple[str, float]]:
        """
        类别先验 boost + 同类优先级决胜。
        
        当 query 中包含领域关键词时，对应类别的 skill 分数 ×2。
        若 top-1/top-2 属于同类且分数差 <25%，用 CATEGORY_PRIORITY 排序决胜。
        """
        query_lower = query.lower()
        boosted_categories = set()

        for pattern, categories in CATEGORY_HINTS.items():
            if re.search(pattern, query_lower):
                boosted_categories.update(categories)

        if not boosted_categories:
            return scores

        boosted = []
        for skill_id, score in scores:
            skill = self._skill_map.get(skill_id)
            if skill and skill.get("category") in boosted_categories:
                boosted.append((skill_id, score * CATEGORY_BOOST_FACTOR))
            else:
                boosted.append((skill_id, score))
        result = sorted(boosted, key=lambda x: -x[1])

        # 类别内优先级决胜
        if len(result) >= 2:
            top_id, top_sc = result[0]
            sec_id, sec_sc = result[1]
            top_cat = self._skill_map.get(top_id, {}).get("category")
            sec_cat = self._skill_map.get(sec_id, {}).get("category")
            if (top_cat == sec_cat and top_cat in CATEGORY_PRIORITY
                    and top_cat):
                prio = CATEGORY_PRIORITY[top_cat]
                top_rank = prio.index(top_id) if top_id in prio else 99
                sec_rank = prio.index(sec_id) if sec_id in prio else 99
                if sec_rank < top_rank and abs(top_sc - sec_sc) / max(top_sc, 1e-9) < 0.25:
                    result[0], result[1] = result[1], result[0]

        return result
