# -*- coding: utf-8 -*-
"""
Skill Semantic Router — 完整使用示例（STOM 重构版）
=====================================================
演示四种核心用法：基础路由、上下文感知、自学习反馈、批量测试
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from router import SkillRouter, SkillFeedbackLearner


def demo_basic_routing():
    """示例 1：基础路由（TF-IDF 语义匹配）"""
    print("\n" + "=" * 50)
    print(" 示例 1：基础路由")
    print("=" * 50)

    router = SkillRouter()

    queries = [
        "帮我看看这段代码有没有 bug",
        "贵州茅台今天股价多少",
        "写一个 README 文档",
        "帮我做个 PRD 文档",
        "Excel 表格怎么加公式",
        "最近的 CPI 数据怎么样",
    ]

    for q in queries:
        result = router.route(q)
        print(f"  [{result['action']:8s}] ({result['confidence']:.3f}) "
              f"'{q}' -> {result['skill']}")


def demo_context_aware():
    """示例 2：上下文感知路由（实体注入）"""
    print("\n" + "=" * 50)
    print(" 示例 2：上下文感知路由")
    print("=" * 50)

    router = SkillRouter()

    history = [
        {"role": "user",      "content": "帮我查一下贵州茅台的行情"},
        {"role": "assistant", "content": "茅台今日收盘价 1680 元，涨 0.5%..."},
    ]

    query = "再看看它的利润表"
    result = router.route(
        query,
        history=history,
        used_skills=["neodata-financial-search"]
    )

    print(f"  Query:     '{query}'")
    print(f"  增强后:     '{result['augmented_query']}'")
    print(f"  路由结果:   {result['action']} -> {result['skill']} (置信度: {result['confidence']})")
    print(f"  原因:       {result['reason']}")


def demo_feedback_learning():
    """示例 3：自学习反馈（触发词自动更新）"""
    print("\n" + "=" * 50)
    print(" 示例 3：自学习反馈（触发词自动更新）")
    print("=" * 50)

    router = SkillRouter()
    learner = SkillFeedbackLearner(router)

    original_query = "拉一下利润表"
    correct_skill = "finance-data-retrieval"

    before = router.route(original_query)
    print(f"  纠正前路由: '{original_query}' -> {before['skill']} ({before['confidence']:.3f})")

    msg = learner.on_correction(original_query, correct_skill)
    print(f"  纠正反馈:   {msg}")

    after = router.route(original_query)
    print(f"  纠正后路由: '{original_query}' -> {after['skill']} ({after['confidence']:.3f})")


def demo_batch_test():
    """示例 4：批量准确率测试"""
    print("\n" + "=" * 50)
    print(" 示例 4：批量准确率测试")
    print("=" * 50)

    router = SkillRouter()
    test_cases = [
        {"query": "帮我看看这段代码有没有 bug",       "expected": "code-review"},
        {"query": "贵州茅台今天股价多少",             "expected": "neodata-financial-search"},
        {"query": "写一个 README 文档",              "expected": "documentation"},
        {"query": "git commit 信息怎么写",            "expected": "git-workflow"},
        {"query": "帮我分析下宁德时代的 DCF 估值",     "expected": "dcf-model"},
        {"query": "最近的 CPI 数据怎么样",            "expected": "neodata-financial-search"},
        {"query": "做个 PPT 给我",                   "expected": "pptx"},
        {"query": "Excel 表格怎么加公式",             "expected": "xlsx"},
        {"query": "调研一下新能源汽车市场",            "expected": "web-research"},
        {"query": "可比公司估值倍数分析",             "expected": "comps-analysis"},
        {"query": "整理一下我的记忆文件",             "expected": "memory-consolidation"},
        {"query": "帮我做个 PRD 文档",               "expected": "product-management-workflows"},
    ]
    
    # 内联 batch_test 逻辑（不再依赖 router 类中的方法）
    correct = 0
    for case in test_cases:
        result = router.route(case["query"])
        hit = result["skill"] == case.get("expected")
        if hit:
            correct += 1
        status = "[OK]" if hit else "[MISS]"
        print(f"  {status} [{result['action']:8s}] ({result['confidence']:.3f}) "
              f"{case['query'][:30]:30s} -> {result['skill']}")
    
    pct = correct / len(test_cases) * 100
    print(f"\n  准确率: {correct}/{len(test_cases)} = {pct:.1f}%")


if __name__ == "__main__":
    demo_basic_routing()
    demo_context_aware()
    demo_batch_test()
    # demo_feedback_learning()  # 会修改 skill_index.json，默认注释
