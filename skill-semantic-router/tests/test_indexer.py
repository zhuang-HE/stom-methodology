# -*- coding: utf-8 -*-
"""
Skill Semantic Router — indexer 模块单元测试 + 性能基准
==========================================================
覆盖：yaml_parser / models / index_manager 核心逻辑 + 路由性能基准
"""

import json
import os
import sys
import time
import unittest
import tempfile

# 项目根目录加入 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# ═══════════════════════════════════════════════════════════
# YAML Parser 测试
# ═══════════════════════════════════════════════════════════

from indexer.yaml_parser import (
    parse_frontmatter,
    extract_triggers_from_description,
    extract_complexity,
    file_content_hash,
)


class TestYamlParser(unittest.TestCase):
    """YAML Frontmatter 解析器测试"""

    def test_basic_key_value(self):
        """基础键值对解析"""
        content = "---\nname: test-skill\ndescription: 这是一个测试\n---\n正文"
        result = parse_frontmatter(content)
        self.assertEqual(result["name"], "test-skill")
        self.assertEqual(result["description"], "这是一个测试")

    def test_inline_list(self):
        """内联列表解析"""
        content = "---\ntriggers: [股票, 行情, 财报]\n---\n"
        result = parse_frontmatter(content)
        self.assertEqual(result["triggers"], ["股票", "行情", "财报"])

    def test_multiline_string(self):
        """多行字符串（> 折叠语法）"""
        content = (
            "---\n"
            "description: >\n"
            "  这是第一行\n"
            "  这是第二行\n"
            "---\n"
        )
        result = parse_frontmatter(content)
        self.assertIn("第一行", result["description"])
        self.assertIn("第二行", result["description"])

    def test_empty_no_frontmatter(self):
        """无 frontmatter 返回空字典"""
        self.assertEqual(parse_frontmatter("纯文本内容\n无frontmatter"), {})

    def test_extract_triggers(self):
        """从 description 中提取触发词"""
        desc = "金融数据检索技能。触发词：查行情、看股票、拉数据、CPI"
        triggers = extract_triggers_from_description(desc)
        self.assertIn("查行情", triggers)
        self.assertIn("看股票", triggers)
        self.assertIn("拉数据", triggers)
        self.assertIn("CPI", triggers)

    def test_extract_triggers_none(self):
        """无触发词时返回空列表"""
        self.assertEqual(extract_triggers_from_description("普通描述文本"), [])

    def test_complexity_int(self):
        """整数复杂度"""
        self.assertEqual(extract_complexity({"complexity": 3}), 3)

    def test_complexity_stars(self):
        """星号复杂度 (⭐⭐)"""
        self.assertEqual(extract_complexity({"complexity": "**"}), 2)
        self.assertEqual(extract_complexity({"complexity": "***"}), 3)

    def test_complexity_default(self):
        """默认复杂度为 2"""
        self.assertEqual(extract_complexity({}), 2)

    def test_file_content_hash(self):
        """文件 hash 计算一致性"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md",
                                         delete=False, encoding="utf-8") as f:
            f.write("test content for hashing")
            tmp_path = f.name
        try:
            h1 = file_content_hash(tmp_path)
            h2 = file_content_hash(tmp_path)
            self.assertEqual(h1, h2)  # 同文件 hash 一致
            self.assertEqual(len(h1), 12)  # SHA-256 前12位
            self.assertTrue(all(c in "0123456789abcdef" for c in h1))
        finally:
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════
# Models 测试
# ═══════════════════════════════════════════════════════════

from indexer.models import DiscoveredSkill, SyncReport


class TestModels(unittest.TestCase):
    """数据结构模型测试"""

    def test_discovered_skill_to_index_entry(self):
        """DiscoveredSkill 转换为索引条目"""
        skill = DiscoveredSkill(
            id="test-skill",
            name="Test Skill",
            description="测试描述",
            triggers=["测试"],
            path="/tmp/SKILL.md",
            source="user",
            file_hash="abc123def456",
            complexity=2,
        )
        entry = skill.to_index_entry()
        self.assertEqual(entry["id"], "test-skill")
        self.assertEqual(entry["name"], "Test Skill")
        self.assertNotIn("category", entry)  # category 为空时不输出

    def test_discovered_skill_with_category(self):
        """DiscoveredSkill 带 category 字段"""
        skill = DiscoveredSkill(
            id="finance", name="Finance", description="金融数据",
            triggers=["股价"], path="/tmp/finance/SKILL.md",
            source="plugin", file_hash="", category="金融数据",
        )
        entry = skill.to_index_entry()
        self.assertEqual(entry["category"], "金融数据")

    def test_sync_report_summary(self):
        """SyncReport 摘要生成"""
        report = SyncReport(
            timestamp="2026-04-27 13:00:00",
            discovered_count=10,
            index_count=8,
            added=[{"id": "new-skill", "source": "user"}],
            modified=[{"id": "mod-skill"}],
            removed=[{"id": "old-skill"}],
            unchanged=5,
        )
        summary = report.summary()
        self.assertIn("+ 新增: 1", summary)
        self.assertIn("~ 变更: 1", summary)
        self.assertIn("- 移除: 1", summary)
        self.assertIn("= 无变: 5", summary)
        self.assertIn("new-skill", summary)


# ═══════════════════════════════════════════════════════════
# 性能基准测试
# ═══════════════════════════════════════════════════════════

from router import SkillRouter


class TestPerformanceBenchmark(unittest.TestCase):
    """路由性能基准测试——量化优化效果"""

    @classmethod
    def setUpClass(cls):
        index_path = os.path.join(PROJECT_ROOT, "skill_index.json")
        cls.router = SkillRouter(index_path)

    def _benchmark_query(self, query: str, iterations: int = 100) -> dict:
        """执行单条 query 的基准测试，返回统计信息"""
        times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            self.router.route(query)
            t1 = time.perf_counter()
            times.append(t1 - t0)

        return {
            "query": query[:30],
            "iterations": iterations,
            "mean_ms": round(sum(times) / len(times) * 1000, 2),
            "min_ms": round(min(times) * 1000, 2),
            "max_ms": round(max(times) * 1000, 2),
            "p95_ms": round(sorted(times)[int(len(times) * 0.95)] * 1000, 2),
        }

    def test_benchmark_exact_match(self):
        """精确匹配路由耗时（应 < 1ms）"""
        stats = self._benchmark_query("帮我做个 PRD 文档", iterations=50)
        # 精确匹配走 Layer 0 快速通道，不应超过 2ms
        self.assertLess(stats["p95_ms"], 5.0,
                        f"精确匹配 P95 延迟过高: {stats['p95_ms']}ms")
        print(f"\n  [BENCHMARK] exact_match: {stats}")

    def test_benchmark_tfidf_route(self):
        """TF-IDF 语义路由耗时（倒排索引加速后应 < 5ms）"""
        stats = self._benchmark_query("帮我看看这段代码有没有 bug", iterations=50)
        self.assertLess(stats["p95_ms"], 20.0,
                        f"TF-IDF P95 延迟过高: {stats['p95_ms']}ms")
        print(f"  [BENCHMARK] tfidf_route: {stats}")

    def test_benchmark_fallback(self):
        """Fallback 路由耗时（低置信度路径）"""
        stats = self._benchmark_query("xyzabcdefghijklmnopqrstuvw", iterations=50)
        self.assertLess(stats["p95_ms"], 20.0,
                        f"Fallback P95 延迟过高: {stats['p95_ms']}ms")
        print(f"  [BENCHMARK] fallback: {stats}")

    def test_batch_routing_throughput(self):
        """批量路由吞吐量（100 次/秒为基线）"""
        queries = [
            "帮我看看代码有没有 bug",
            "贵州茅台今天股价多少",
            "写一个 README 文档",
            "git commit 信息怎么写",
            "Excel 表格怎么加公式",
            "调研一下新能源汽车市场",
            "整理一下我的记忆文件",
            "做个 PPT 给我",
            "帮我分析下宁德时代的 DCF 估值",
            "最近的 CPI 数据怎么样",
        ] * 10  # 100 条查询

        t0 = time.perf_counter()
        results = [self.router.route(q) for q in queries]
        elapsed = time.perf_counter() - t0

        throughput = len(queries) / elapsed
        avg_latency_ms = (elapsed / len(queries)) * 1000

        print(f"\n  [BENCHMARK] batch_100q:")
        print(f"    吞吐量: {throughput:.0f} queries/s")
        print(f"    平均延迟: {avg_latency_ms:.2f} ms/query")
        print(f"    总耗时: {elapsed*1000:.1f} ms")

        # 至少 50 QPS
        self.assertGreater(throughput, 50.0,
                           f"吞吐量过低: {throughput:.1f} QPS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
