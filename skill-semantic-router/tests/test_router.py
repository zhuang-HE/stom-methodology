# -*- coding: utf-8 -*-
"""
Skill Semantic Router — 单元测试（STOM 重构版）
================================================
测试覆盖：分词、向量、路由准确性、上下文感知、自学习
"""
import sys
import os
import json
import tempfile
import unittest

# 项目根目录加入 sys.path（支持 router/ 和 indexer/ 子包导入）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 使用新的子包导入路径
from router.tfidf_engine import tokenize, cosine_similarity
from router.skill_router import SkillRouter
from router.feedback_learner import SkillFeedbackLearner


class TestTokenize(unittest.TestCase):
    """TF-IDF 分词器测试"""

    def test_english(self):
        tokens = tokenize("code review bug")
        self.assertIn("code", tokens)
        self.assertIn("review", tokens)
        self.assertIn("bug", tokens)

    def test_chinese_bigram(self):
        tokens = tokenize("利润表")
        self.assertIn("利润", tokens)
        self.assertIn("润表", tokens)

    def test_chinese_trigram(self):
        tokens = tokenize("财务报表")
        self.assertIn("财务报", tokens)
        self.assertIn("务报表", tokens)

    def test_mixed(self):
        tokens = tokenize("DCF 折现现金流")
        self.assertIn("dcf", tokens)
        self.assertIn("折现", tokens)


class TestCosineSimilarity(unittest.TestCase):
    """余弦相似度测试"""

    def test_identical(self):
        v = {"a": 1.0, "b": 2.0}
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=5)

    def test_orthogonal(self):
        v1, v2 = {"a": 1.0}, {"b": 1.0}
        self.assertAlmostEqual(cosine_similarity(v1, v2), 0.0, places=5)

    def test_zero_vector(self):
        self.assertEqual(cosine_similarity({}, {"a": 1.0}), 0.0)


class TestSkillRouter(unittest.TestCase):
    """核心路由器测试"""

    @classmethod
    def setUpClass(cls):
        index_path = os.path.join(PROJECT_ROOT, "skill_index.json")
        cls.router = SkillRouter(index_path)

    def _assert_routes_to(self, query, expected_skill, **kwargs):
        result = self.router.route(query, **kwargs)
        self.assertEqual(
            result["skill"], expected_skill,
            f"Query '{query}' -> '{result['skill']}', expected '{expected_skill}' "
            f"(conf={result['confidence']:.3f})"
        )

    # ─── 精确关键词快速通道 ────────────────────────

    def test_prd_exact_match(self):
        self._assert_routes_to("帮我做个 PRD 文档", "product-management-workflows")

    def test_dcf_exact_match(self):
        self._assert_routes_to("帮我分析下宁德时代的 DCF 估值", "dcf-model")

    def test_pptx_exact_match(self):
        self._assert_routes_to("做个 PPT 给我", "pptx")

    # ─── TF-IDF 语义路由 ────────────────────────────

    def test_code_review(self):
        self._assert_routes_to("帮我看看这段代码有没有 bug", "code-review")

    def test_stock_query(self):
        self._assert_routes_to("贵州茅台今天股价多少", "neodata-financial-search")

    def test_documentation(self):
        self._assert_routes_to("写一个 README 文档", "documentation")

    def test_git_workflow(self):
        self._assert_routes_to("git commit 信息怎么写", "git-workflow")

    def test_xlsx(self):
        self._assert_routes_to("Excel 表格怎么加公式", "xlsx")

    def test_web_research(self):
        self._assert_routes_to("调研一下新能源汽车市场", "web-research")

    def test_comps_analysis(self):
        self._assert_routes_to("可比公司估值倍数分析", "comps-analysis")

    def test_memory_consolidation(self):
        self._assert_routes_to("整理一下我的记忆文件", "memory-consolidation")

    # ─── 金融数据类别 boost ─────────────────────────

    def test_macro_data_finance_category(self):
        """CPI 查询应路由到任意一个金融数据 skill"""
        result = self.router.route("最近的 CPI 数据怎么样")
        self.assertIn(
            result["skill"],
            ["neodata-financial-search", "finance-data-retrieval"],
            f"Expected finance skill, got: {result['skill']}"
        )

    # ─── 上下文感知 ────────────────────────────────

    def test_context_aware_entity_injection(self):
        """历史提到茅台，当前问利润表，增强 query 应含实体"""
        history = [
            {"role": "user", "content": "帮我查一下贵州茅台的行情"},
            {"role": "assistant", "content": "茅台今日收盘 1680..."},
        ]
        result = self.router.route(
            "再看看它的利润表",
            history=history,
            used_skills=["neodata-financial-search"]
        )
        self.assertIn("贵州茅台", result["augmented_query"])
        self.assertNotEqual(result["action"], "fallback")

    # ─── Fallback ──────────────────────────────────

    def test_fallback_on_empty(self):
        result = self.router.route("")
        self.assertEqual(result["action"], "fallback")

    # ─── 完整准确率测试 ────────────────────────────

    def test_all_12_cases_accuracy(self):
        """完整 12 个测试用例准确率应为 100%"""
        test_cases = [
            ("帮我看看这段代码有没有 bug",       "code-review"),
            ("贵州茅台今天股价多少",             "neodata-financial-search"),
            ("写一个 README 文档",              "documentation"),
            ("git commit 信息怎么写",            "git-workflow"),
            ("帮我分析下宁德时代的 DCF 估值",     "dcf-model"),
            ("最近的 CPI 数据怎么样",             None),   # 允许任一金融数据 skill
            ("做个 PPT 给我",                   "pptx"),
            ("Excel 表格怎么加公式",             "xlsx"),
            ("调研一下新能源汽车市场",            "web-research"),
            ("可比公司估值倍数分析",             "comps-analysis"),
            ("整理一下我的记忆文件",             "memory-consolidation"),
            ("帮我做个 PRD 文档",               "product-management-workflows"),
        ]
        FINANCE_SKILLS = {"neodata-financial-search", "finance-data-retrieval"}
        correct = sum(
            (result["skill"] in FINANCE_SKILLS) if expected is None
            else (result["skill"] == expected)
            for query, expected in test_cases
            for result in [self.router.route(query)]
        )
        self.assertEqual(correct, 12, f"准确率不达标: {correct}/12")


class TestFeedbackLearner(unittest.TestCase):
    """自学习反馈模块测试"""

    def test_on_correction_adds_triggers(self):
        minimal_index = {
            "version": "test",
            "generated_at": "test",
            "description": "test",
            "schema": {},
            "skills": [{
                "id": "finance-data-retrieval",
                "name": "finance-data-retrieval",
                "category": "金融数据",
                "description": "结构化金融数据 API",
                "triggers": ["股票", "行情"],
                "path": "",
                "complexity": 2,
                "priority": 1,
            }],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(minimal_index, f, ensure_ascii=False)
            tmp_path = f.name

        try:
            router = SkillRouter(tmp_path)
            learner = SkillFeedbackLearner(router)
            initial_count = 2

            learner.on_correction("查季度净利润增速", "finance-data-retrieval")

            with open(tmp_path, encoding="utf-8") as f:
                updated = json.load(f)
            updated_skill = next(s for s in updated["skills"]
                                 if s["id"] == "finance-data-retrieval")
            self.assertGreater(
                len(updated_skill.get("triggers", [])),
                initial_count,
                "纠错后触发词数量应增加"
            )
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
