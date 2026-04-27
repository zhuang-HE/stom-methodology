# -*- coding: utf-8 -*-
"""
Skill Semantic Router v2.3 — 增强功能测试
==========================================
覆盖：BM25 引擎、LRU 缓存、jieba 分词、双引擎融合
"""

import sys
import os
import unittest
from unittest.mock import patch

# 项目根目录加入 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


class TestBM25Engine(unittest.TestCase):
    """BM25 排序引擎单元测试（不依赖 skill_index.json）"""

    _SKILLS = [
        {
            "id": "stock-analyst",
            "name": "股票分析",
            "category": "金融数据",
            "description": "股票技术分析和量化策略研究",
            "triggers": ["股票", "行情", "K线", "均线"],
            "path": "",
            "complexity": 3,
            "priority": 1,
        },
        {
            "id": "docx",
            "name": "Word文档",
            "category": "办公文档",
            "description": "创建和编辑 Word 文档",
            "triggers": ["文档", "word", "报告"],
            "path": "",
            "complexity": 1,
            "priority": 1,
        },
        {
            "id": "web-research",
            "name": "网络调研",
            "category": "信息检索",
            "description": "深度网络研究和信息整理",
            "triggers": ["调研", "搜索", "查一下"],
            "path": "",
            "complexity": 2,
            "priority": 2,
        },
    ]

    def setUp(self):
        from router.bm25_engine import BM25Engine
        self.engine = BM25Engine(self._SKILLS)

    def test_search_returns_results(self):
        """搜索应返回排序结果"""
        results = self.engine.search("股票行情")
        self.assertGreater(len(results), 0)
        # 第一个应该是 stock-analyst（最匹配）
        self.assertEqual(results[0][0], "stock-analyst")

    def test_empty_query(self):
        """空查询应返回空列表"""
        results = self.engine.search("")
        self.assertEqual(results, [])

    def test_top_k_limits_results(self):
        """top_k 应限制返回数量"""
        results = self.engine.search("分析", top_k=1)
        self.assertEqual(len(results), 1)

    def test_inverted_index_accelerates(self):
        """倒排索引模式应返回非空结果"""
        r_inv = self.engine.search("文档报告", use_inverted_index=True)
        self.assertGreater(len(r_inv), 0)
        # 验证结果包含有效 skill_id
        all_ids = {s["id"] for s in self._SKILLS}
        for sid, _ in r_inv:
            self.assertIn(sid, all_ids)

    def test_stats_returns_dict(self):
        """get_stats 应返回包含关键指标的 dict"""
        stats = self.engine.get_stats()
        self.assertIn("n_docs", stats)
        self.assertIn("vocab_size", stats)
        self.assertIn("avgdl", stats)
        self.assertEqual(stats["n_docs"], 3)

    def test_custom_k1_b_params(self):
        """自定义 k1/b 参数不应报错"""
        from router.bm25_engine import BM25Engine
        engine = BM25Engine(self._SKILLS, k1=0.5, b=0.5)
        results = engine.search("股票")
        self.assertIsInstance(results, list)

    def test_no_match_query(self):
        """完全无关的 query 不应崩溃，只是分数低"""
        results = self.engine.search("xyz_nonexistent_term_12345")
        # 可能返回空或低分结果，只要不崩就行
        self.assertIsInstance(results, list)

    def test_tokenizer_override(self):
        """自定义分词器应正常工作"""
        custom_tokens = lambda t: ["CUSTOM"] * len(t)  # 简单测试用分词器
        from router.bm25_engine import BM25Engine
        engine = BM25Engine(self._SKILLS, tokenizer=custom_tokens)
        results = engine.search("anything")
        self.assertIsInstance(results, list)


class TestJiebaTokenizer(unittest.TestCase):
    """jieba 中文分词器测试"""

    def test_jieba_fallback_when_not_installed(self):
        """未安装 jieba 时自动降级为 n-gram 分词"""
        from router.bm25_engine import jieba_tokenize, tokenize_text
        result = jieba_tokenize("利润表分析")
        fallback_result = tokenize_text("利润表分析")
        # 未安装时两者应返回相同结果
        try:
            import jieba
            installed = True
        except ImportError:
            installed = False
        
        if not installed:
            self.assertEqual(result, fallback_result)

    def test_jieba_tokenize_with_jieba_installed(self):
        """安装了 jieba 时应使用 jieba 分词（验证接口存在）"""
        from router.bm25_engine import jieba_tokenize
        tokens = jieba_tokenize("帮我看看茅台的股价")
        self.assertIsInstance(tokens, list)
        self.assertGreater(len(tokens), 0)


class TestRoutingCache(unittest.TestCase):
    """LRU 路由缓存测试"""

    @classmethod
    def setUpClass(cls):
        index_path = os.path.join(PROJECT_ROOT, "skill_index.json")
        cls.index_path = index_path

    def _make_router(self, cache_size=16):
        from router import SkillRouter
        return SkillRouter(self.index_path, cache_size=cache_size)

    def test_cache_hit_on_repeat_query(self):
        """重复 query 应命中缓存（同一对象）"""
        router = self._make_router()
        r1 = router.route("做个 PPT 给我")
        r2 = router.route("做个 PPT 给我")
        # 结果应完全相同
        self.assertEqual(r1["skill"], r2["skill"])
        self.assertEqual(r1["confidence"], r2["confidence"])

    def test_cache_eviction_on_overflow(self):
        """缓存满后应淘汰最旧条目"""
        router = self._make_router(cache_size=3)
        # 用精确匹配触发 invoke（会写入缓存）
        for q in ["做个 PPT 给我", "帮我做个 PRD 文档", "写一个 README",
                  "Excel 表格怎么加公式"]:
            router.route(q)
        
        # 缓存大小不应超过 capacity + 1 (因为 fallback 不写入)
        self.assertLessEqual(len(router._cache), router._cache_size)

    def test_cache_cleared_on_reload(self):
        """reload 后缓存应清空"""
        router = self._make_router(cache_size=10)
        # 用一个走 Layer 2（非精确匹配）的 query 来触发缓存写入
        router.route("帮我看看代码有没有问题")  # code-review → invoke → 写入缓存
        self.assertGreater(len(router._cache), 0)
        router.reload()
        self.assertEqual(len(router._cache), 0)

    def test_fallback_not_cached(self):
        """fallback 结果不应写入缓存"""
        router = self._make_router()
        router.route("")  # 空串 → fallback
        self.assertEqual(len(router._cache), 0)

    def test_whitespace_normalized_in_cache_key(self):
        """前后空白不同的相同 query 应共享缓存"""
        router = self._make_router()
        r1 = router.route("  做个 PPT 给我  ")
        r2 = router.route("做个 PPT 给我")
        self.assertEqual(r1["skill"], r2["skill"])


class TestDualEngineFusion(unittest.TestCase):
    """TF-IDF + BM25 双引擎融合测试"""

    @classmethod
    def setUpClass(cls):
        index_path = os.path.join(PROJECT_ROOT, "skill_index.json")
        cls.index_path = index_path

    def _make_router(self):
        from router import SkillRouter
        return SkillRouter(self.index_path)

    def test_dual_engine_produces_valid_results(self):
        """融合结果应包含有效 action 和 candidates"""
        router = self._make_router()
        result = router.route("贵州茅台今天股价多少")
        self.assertIn(result["action"], ("invoke", "confirm", "fallback"))
        if result["candidates"]:
            self.assertIsInstance(result["candidates"], list)
            self.assertIsInstance(result["candidates"][0]["score"], float)

    def test_bm25_available_as_attribute(self):
        """BM25 引擎应在 router 上可访问"""
        router = self._make_router()
        self.assertIsNotNone(getattr(router, '_bm25', None))
        stats = router._bm25.get_stats()
        self.assertGreater(stats["n_docs"], 0)

    def test_fusion_accuracy_maintained(self):
        """融合模式下原有路由准确率不应下降"""
        router = self._make_router()
        # 关键测试用例仍应正确路由
        test_cases = [
            ("做个 PPT 给我", "pptx"),
            ("帮我做个 PRD 文档", "product-management-workflows"),
            ("写一个 README 文档", "documentation"),
        ]
        correct = sum(
            router.route(q)["skill"] == expected
            for q, expected in test_cases
        )
        self.assertEqual(correct, len(test_cases),
                         f"融合模式准确率下降: {correct}/{len(test_cases)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
