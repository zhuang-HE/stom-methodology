# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

"""
WorkBuddy Skill 语义路由器
===========================
实现三层路由策略：
  Layer 1: TF-IDF + 余弦相似度（轻量，无需 GPU，开箱即用）
  Layer 2: 上下文感知增强（利用对话历史中的实体和已用 skill）
  Layer 3: 置信度阈值决策（高置信直接触发 / 低置信降级处理）

依赖: pip install scikit-learn jieba
"""

import json
import re
import math
from pathlib import Path
from collections import Counter
from typing import Optional

# ─── 配置 ────────────────────────────────────────────────────────────────────

SKILL_INDEX_PATH = Path(__file__).parent / "skill_index.json"
CONFIDENCE_HIGH  = 0.35   # 高置信阈值 → 直接触发
CONFIDENCE_LOW   = 0.10   # 低置信阈值 → fallback
TOP_K            = 3       # 返回 Top-K 候选

# ─── TF-IDF 向量化（纯 Python，无外部依赖）──────────────────────────────────

def tokenize(text: str) -> list[str]:
    """改进中英文分词：保留 2-6 字中文词组 + 英文词 + 滑动窗口生成 bigram"""
    text = text.lower()
    tokens = []

    # 英文词和数字
    en_tokens = re.findall(r'[a-z][a-z0-9]*', text)
    tokens.extend(en_tokens)

    # 中文字符序列
    cn_seqs = re.findall(r'[\u4e00-\u9fff]+', text)
    for seq in cn_seqs:
        # 单字
        tokens.extend(list(seq))
        # bigram（相邻两字）
        for i in range(len(seq) - 1):
            tokens.append(seq[i:i+2])
        # trigram（相邻三字）
        for i in range(len(seq) - 2):
            tokens.append(seq[i:i+3])

    return tokens


def build_tfidf_index(skills: list[dict]) -> tuple[dict, list[Counter]]:
    """构建 TF-IDF 索引"""
    # 每个 skill 的文档 = description + triggers 拼接
    docs = []
    for skill in skills:
        text = skill["description"] + " " + " ".join(skill.get("triggers", []))
        docs.append(tokenize(text))

    # 计算 IDF
    N = len(docs)
    df: Counter = Counter()
    for tokens in docs:
        for token in set(tokens):
            df[token] += 1

    idf = {token: math.log((N + 1) / (count + 1)) + 1
           for token, count in df.items()}

    # 计算每个 doc 的 TF-IDF 向量
    tfidf_vecs = []
    for tokens in docs:
        tf = Counter(tokens)
        vec = {token: (count / len(tokens)) * idf.get(token, 0)
               for token, count in tf.items()}
        tfidf_vecs.append(vec)

    return idf, tfidf_vecs


def cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    """稀疏向量余弦相似度"""
    dot = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in vec_b)
    norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ─── 上下文感知 ───────────────────────────────────────────────────────────────

def extract_entities(text: str) -> list[str]:
    """从文本中提取金融实体（股票名、公司名等）"""
    # 简单规则：提取中文专有词（大写开头英文 + 常见公司/股票词）
    entities = []

    # 股票代码模式
    stock_codes = re.findall(r'\b[036]\d{5}\.[SA][ZH]\b', text)
    entities.extend(stock_codes)

    # 常见公司关键词（可扩展）
    company_patterns = [
        r'贵州茅台|茅台', r'腾讯|TENCENT', r'阿里|ALIBABA|阿里巴巴',
        r'宁德时代|CATL', r'比亚迪|BYD', r'中国平安', r'招商银行',
        r'万科|碧桂园|恒大', r'华为', r'字节跳动',
    ]
    for pattern in company_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        entities.extend(matches)

    return list(set(entities))


def augment_query(
    query: str,
    history: list[dict],
    used_skills: list[str]
) -> str:
    """
    上下文感知 Query 增强
    - 提取最近对话中的实体注入当前 query
    - 附上最近使用的 skill 名称帮助相关性提升
    """
    # 提取历史实体
    recent_text = " ".join(
        msg.get("content", "") for msg in history[-3:]
    )
    entities = extract_entities(recent_text)

    augmented = query
    if entities:
        augmented += f" [实体上下文: {' '.join(entities)}]"
    if used_skills:
        # 最近用过的 skill 的描述词有助于语义连续性
        augmented += f" [上文工具: {' '.join(used_skills[-2:])}]"

    return augmented


# ─── 主路由器 ─────────────────────────────────────────────────────────────────

class SkillRouter:
    def __init__(self, index_path: str = str(SKILL_INDEX_PATH), auto_sync: bool = False):
        self.index_path = index_path  # 保存路径供 FeedbackLearner 使用
        self.auto_sync = auto_sync

        # 自动同步索引（可选）
        if auto_sync:
            self._auto_sync_index()

        self._load_and_build()

    def _auto_sync_index(self):
        """自动扫描并同步索引"""
        try:
            from skill_index_manager import SkillIndexManager
            mgr = SkillIndexManager(index_path=self.index_path)
            mgr.full_sync(remove_missing=False)  # 不自动移除，避免误删
        except Exception as e:
            print(f"[SkillRouter] 自动同步跳过: {e}")

    def _load_and_build(self):
        """加载索引并构建 TF-IDF 向量"""
        with open(self.index_path, encoding="utf-8") as f:
            self.index = json.load(f)
        self.skills = self.index["skills"]
        self.routing_rules = self.index.get("routing_rules", {})

        # 构建 TF-IDF 索引
        self.idf, self.skill_vecs = build_tfidf_index(self.skills)
        print(f"[SkillRouter] 已加载 {len(self.skills)} 个 skill，索引构建完成")

    def reload(self):
        """重新加载索引（skill 变更后调用）"""
        self._load_and_build()

    def _query_vec(self, query: str) -> dict:
        tokens = tokenize(query)
        tf = Counter(tokens)
        return {token: (count / len(tokens)) * self.idf.get(token, 0)
                for token, count in tf.items()} if tokens else {}

    def route(
        self,
        query: str,
        history: Optional[list[dict]] = None,
        used_skills: Optional[list[str]] = None,
        top_k: int = TOP_K
    ) -> dict:
        """
        主路由方法

        Args:
            query:       用户输入
            history:     对话历史 [{role, content}, ...]
            used_skills: 本轮会话已使用的 skill 列表
            top_k:       返回候选数量

        Returns:
            {
              "action": "invoke" | "confirm" | "fallback",
              "skill":  skill_id or None,
              "candidates": [...],
              "augmented_query": "...",
              "reason": "..."
            }
        """
        history = history or []
        used_skills = used_skills or []

        # Step 0: 精确关键词快速通道（最高优先级）
        query_lower = query.lower()
        for pattern, skill_id in self.EXACT_OVERRIDE.items():
            if re.search(pattern, query_lower):
                skill = next((s for s in self.skills if s["id"] == skill_id), None)
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

        # Step 1: 上下文增强
        augmented = augment_query(query, history, used_skills)

        # Step 2: 向量检索
        q_vec = self._query_vec(augmented)
        if not q_vec:
            return {"action": "fallback", "skill": None, "candidates": [],
                    "augmented_query": augmented, "reason": "query 向量为空"}

        scores = [
            (self.skills[i]["id"], cosine_similarity(q_vec, self.skill_vecs[i]))
            for i in range(len(self.skills))
        ]
        scores.sort(key=lambda x: -x[1])

        # 来源优先级 boost：用户级 skill 在分数接近时优先
        scores = self._apply_source_boost(scores)

        # 类别先验 boost
        scores = self._apply_category_boost(scores, augmented)

        top_candidates = scores[:top_k]

        # Step 3: 置信度决策
        top_id, top_score = top_candidates[0]
        top_skill = next(s for s in self.skills if s["id"] == top_id)

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
            "skill_name": top_skill["name"],
            "confidence": round(top_score, 4),
            "candidates": [
                {"id": sid, "score": round(sc, 4)} for sid, sc in top_candidates
            ],
            "augmented_query": augmented,
            "reason": reason,
        }

    # ─── 来源优先级（用户级 > 插件级）────────────────────────────────────────
    SOURCE_BOOST = {
        "user": 1.20,    # 用户级 skill +20%
        "plugin": 1.00,  # 插件级 skill 不变
    }

    def _apply_source_boost(
        self, scores: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        """用户级 skill 在分数差距不大的情况下优先"""
        boosted = []
        for skill_id, score in scores:
            skill = next((s for s in self.skills if s["id"] == skill_id), None)
            source = skill.get("source", "plugin") if skill else "plugin"
            factor = self.SOURCE_BOOST.get(source, 1.0)
            boosted.append((skill_id, score * factor))
        return sorted(boosted, key=lambda x: -x[1])

    # ─── 类别先验过滤（处理已知歧义场景）────────────────────────────────────
    CATEGORY_HINTS = {
        # 金融数据词 → 优先金融类别
        r'cpi|gdp|pmi|ppi|通胀|利率|m2|宏观指标|经济数据': ["金融数据"],
        r'股价|行情|财报|涨跌|基金|板块|汇率|黄金|原油': ["金融数据"],
        # 产品类词 → 优先产品管理
        r'prd|需求文档|产品需求|功能规划|路线图|用户故事|迭代|产品经理': ["产品管理"],
    }

    # 精确关键词 → 直接指定 skill（最高优先级，绕过向量计算）
    EXACT_OVERRIDE = {
        r'\bprd\b|产品需求|功能需求|需求文档|用户故事|产品迭代': "product-management-workflows",
        r'\blbo\b|杠杆收购': "lbo-model",
        r'\bdcf\b|折现现金流': "dcf-model",
        r'\bcim\b|投资备忘录': "cim-builder",
        r'memory\.md|记忆整理|工作记忆': "memory-consolidation",
        r'做个\s*ppt|做\s*ppt|制作\s*ppt|ppt.*给我': "pptx",
    }

    # 同类别内优先级：key=类别, value=优先 skill 列表（按优先级排）
    CATEGORY_PRIORITY = {
        "金融数据": ["neodata-financial-search", "finance-data-retrieval", "stock-analyst"],
        "产品管理": ["product-management-workflows"],
        "办公文档": ["pptx", "docx", "xlsx", "pdf"],
    }

    def _apply_category_boost(
        self, scores: list[tuple[str, float]], query: str
    ) -> list[tuple[str, float]]:
        """根据类别先验对分数进行 boost"""
        query_lower = query.lower()
        boosted_categories = set()

        for pattern, categories in self.CATEGORY_HINTS.items():
            if re.search(pattern, query_lower):
                boosted_categories.update(categories)

        if not boosted_categories:
            return scores

        # 对命中类别的 skill 分数乘以 boost 系数
        CATEGORY_BOOST_FACTOR = 2.0
        boosted = []
        for skill_id, score in scores:
            skill = next((s for s in self.skills if s["id"] == skill_id), None)
            if skill and skill.get("category") in boosted_categories:
                boosted.append((skill_id, score * CATEGORY_BOOST_FACTOR))
            else:
                boosted.append((skill_id, score))
        result = sorted(boosted, key=lambda x: -x[1])

        # 类别内优先级：若 top-1 和 top-2 分数差 < 25%，用 CATEGORY_PRIORITY 决胜
        if len(result) >= 2:
            top_id, top_sc = result[0]
            sec_id, sec_sc = result[1]
            top_cat = next((s.get("category") for s in self.skills if s["id"] == top_id), None)
            sec_cat = next((s.get("category") for s in self.skills if s["id"] == sec_id), None)
            if top_cat == sec_cat and top_cat in self.CATEGORY_PRIORITY:
                prio = self.CATEGORY_PRIORITY[top_cat]
                top_rank = prio.index(top_id) if top_id in prio else 99
                sec_rank = prio.index(sec_id) if sec_id in prio else 99
                if sec_rank < top_rank and abs(top_sc - sec_sc) / max(top_sc, 1e-9) < 0.25:
                    # 交换 top-1 和 top-2
                    result[0], result[1] = result[1], result[0]

        return result

    def batch_test(self, test_cases: list[dict]) -> None:
        """批量测试路由准确性"""
        print("\n" + "=" * 60)
        print("  Skill Router 批量路由测试")
        print("=" * 60)
        correct = 0
        for case in test_cases:
            result = self.route(case["query"])
            hit = result["skill"] == case.get("expected")
            if hit:
                correct += 1
            status = "[OK]" if hit else "[MISS]"
            print(f"{status} [{result['action']:8s}] ({result['confidence']:.3f}) "
                  f"{case['query'][:30]:30s} → {result['skill']}")
            if not hit and case.get("expected"):
                print(f"   期望: {case['expected']}, "
                      f"实际候选: {[c['id'] for c in result['candidates']]}")
        print(f"\n准确率: {correct}/{len(test_cases)} = "
              f"{correct/len(test_cases)*100:.1f}%")
        print("=" * 60)


# ─── 自学习：触发词更新 ───────────────────────────────────────────────────────

class SkillFeedbackLearner:
    """
    当用户纠正 skill 选择时，自动提取触发词并写回 skill_index.json
    """
    def __init__(self, router: SkillRouter):
        self.router = router

    def on_correction(
        self,
        original_query: str,
        correct_skill_id: str
    ) -> str:
        """处理用户纠正，提取新触发词"""
        # 提取 query 中的关键词（去停用词）
        stopwords = {"帮我", "一下", "看看", "给我", "的", "了", "呢", "吗", "请", "能"}
        tokens = tokenize(original_query)
        new_triggers = [t for t in tokens if t not in stopwords and len(t) > 1]

        # 写回索引
        for skill in self.router.skills:
            if skill["id"] == correct_skill_id:
                existing = set(skill.get("triggers", []))
                added = [t for t in new_triggers if t not in existing]
                skill["triggers"].extend(added)
                break

        # 持久化
        self.router.index["skills"] = self.router.skills
        with open(self.router.index_path, "w", encoding="utf-8") as f:
            json.dump(self.router.index, f, ensure_ascii=False, indent=2)

        # 重建索引
        self.router.idf, self.router.skill_vecs = build_tfidf_index(self.router.skills)

        return f"已为 [{correct_skill_id}] 添加触发词: {added}"


# ─── 测试入口 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    router = SkillRouter()

    # 基础路由测试
    test_cases = [
        {"query": "帮我看看这段代码有没有 bug",         "expected": "code-review"},
        {"query": "贵州茅台今天股价多少",               "expected": "neodata-financial-search"},
        {"query": "写一个 README 文档",                "expected": "documentation"},
        {"query": "git commit 信息怎么写",              "expected": "git-workflow"},
        {"query": "帮我分析下宁德时代的 DCF 估值",       "expected": "dcf-model"},
        {"query": "最近的 CPI 数据怎么样",              "expected": "neodata-financial-search"},
        {"query": "做个 PPT 给我",                     "expected": "pptx"},
        {"query": "Excel 表格怎么加公式",               "expected": "xlsx"},
        {"query": "调研一下新能源汽车市场",              "expected": "web-research"},
        {"query": "可比公司估值倍数分析",               "expected": "comps-analysis"},
        {"query": "整理一下我的记忆文件",               "expected": "memory-consolidation"},
        {"query": "帮我做个 PRD 文档",                 "expected": "product-management-workflows"},
    ]

    router.batch_test(test_cases)

    # 单次路由示例（含上下文）
    print("\n--- 上下文感知路由示例 ---")
    history = [
        {"role": "user", "content": "帮我查一下贵州茅台的行情"},
        {"role": "assistant", "content": "茅台今日收盘价..."},
    ]
    result = router.route(
        "再看看它的利润表",
        history=history,
        used_skills=["neodata-financial-search"]
    )
    print(f"Query: '再看看它的利润表'")
    print(f"增强后: {result['augmented_query']}")
    print(f"路由结果: {result['action']} → {result['skill']} ({result['confidence']})")
    print(f"原因: {result['reason']}")
