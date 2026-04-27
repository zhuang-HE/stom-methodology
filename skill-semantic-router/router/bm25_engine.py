# -*- coding: utf-8 -*-
"""
bm25_engine.py — BM25 排序算法引擎（纯 Python，零外部依赖）
=============================================================
Okapi BM25 实现，对短文本/查询场景优于 TF-IDF 余弦相似度。

核心优势:
  - 词频饱和: 单个 term 重复出现不会无限增加分数
  - 文档长度归一化: 长文档不会因包含更多词而天然占优
  - 可调参数 k1/b 支持不同场景微调

遵循 STOM 方法论：单一职责，仅负责 BM25 评分 + 倒排检索。
"""

import math
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set, Tuple

# BM25 默认参数（经验值，适合短文档/技能描述场景）
DEFAULT_K1 = 1.2      # 词频饱和参数（通常 1.2~2.0）
DEFAULT_B = 0.75      # 文档长度归一化参数（通常 0.75）


class BM25Engine:
    """
    Okapi BM25 检索引擎。
    
    使用方式:
        engine = BM25Engine(skills)       # 构建索引
        scores = engine.search("query")    # 返回 [(skill_id, score), ...]
    
    内部维护:
      - dl: 各文档长度（token 数）
      - avgdl: 平均文档长度
      - df: 各 token 的文档频率
      - tf_matrix: 各文档的 {token: freq} 稀疏矩阵
      - inv_index: 倒排索引 {token: set(doc_idx)}
    """

    def __init__(
        self,
        skills: list[dict],
        *,
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
        tokenizer=None,
    ):
        """
        Args:
            skills: skill 元数据列表（需含 description 和 triggers 字段）
            k1:     词频饱和参数（越大越不饱和）
            b:      长度归一化强度（0=不考虑长度，1=完全归一化）
            tokenizer: 分词函数，默认使用内置 tokenize_text
        """
        self.k1 = k1
        self.b = b
        self._tokenizer = tokenizer or tokenize_text
        self.skills = skills
        self.n_docs = len(skills)
        
        # 文档 token 列表 + 统计
        self.doc_tokens: list[list[str]] = []
        self.tf_matrix: list[Counter] = []   # 每篇文档的词频向量
        self.dl: List[int] = []              # 文档长度
        self.avgdl: float = 0.0              # 平均文档长度
        
        # IDF + 倒排索引
        self.idf: Dict[str, float] = {}
        self.inv_index: Dict[str, Set[int]] = {}
        
        self._build_index()

    def _build_index(self):
        """构建 BM25 索引：分词 → TF矩阵 → IDF → 倒排索引"""
        # 分词 + TF 矩阵
        for skill in self.skills:
            text = skill["description"] + " " + " ".join(skill.get("triggers", []))
            tokens = self._tokenizer(text)
            self.doc_tokens.append(tokens)
            tf = Counter(tokens)
            self.tf_matrix.append(tf)
            self.dl.append(len(tokens))
        
        # 平均文档长度
        self.avgdl = sum(self.dl) / max(self.n_docs, 1)
        
        # DF + IDF
        df_counter: Counter = Counter()
        for idx, tf in enumerate(self.tf_matrix):
            for token in tf:
                df_counter[token] += 1
                
        # BM25 IDF (Lucene 变体: log((N - df + 0.5)/(df + 0.5) + 1))
        N = self.n_docs
        self.idf = {
            token: math.log((N - count + 0.5) / (count + 0.5) + 1.0)
            for token, count in df_counter.items()
        }
        
        # 倒排索引
        inv: Dict[str, Set[int]] = defaultdict(set)
        for idx, tf in enumerate(self.tf_matrix):
            for token in tf:
                inv[token].add(idx)
        self.inv_index = dict(inv)

    def _score_doc(self, query_tokens: list[str], doc_idx: int) -> float:
        """计算单个文档的 BM25 分数"""
        tf = self.tf_matrix[doc_idx]
        dl = self.dl[doc_idx]
        
        score = 0.0
        for token in query_tokens:
            if token not in self.idf:
                continue
            
            freq = tf.get(token, 0)
            if freq == 0:
                continue
            
            idf = self.idf[token]
            
            # BM25 核心公式
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            score += idf * numerator / denominator
        
        return score

    def search(
        self,
        query: str,
        top_k: int = 5,
        use_inverted_index: bool = True,
    ) -> List[Tuple[str, float]]:
        """
        搜索并返回排序结果。
        
        Args:
            query:             查询文本
            top_k:             返回前 K 个结果
            use_inverted_index: 是否用倒排索引加速（默认 True）
        
        Returns:
            [(skill_id, bm25_score), ...] 按 score 降序
        """
        query_tokens = self._tokenizer(query)
        if not query_tokens:
            return []
        
        # 倒排索引模式：只计算候选文档
        if use_inverted_index:
            candidates: Set[int] = set()
            for token in query_tokens:
                candidates.update(self.inv_index.get(token, set()))
            
            # 兜底：无命中则全量扫描
            if not candidates:
                candidates = set(range(self.n_docs))
        else:
            candidates = set(range(self.n_docs))
        
        # 计算分数
        scored = [
            (self.skills[idx]["id"], self._score_doc(query_tokens, idx))
            for idx in candidates
        ]
        scored.sort(key=lambda x: -x[1])
        
        return scored[:top_k]

    def get_stats(self) -> dict:
        """返回索引统计信息（调试/监控用）"""
        return {
            "n_docs": self.n_docs,
            "avgdl": round(self.avgdl, 1),
            "vocab_size": len(self.idf),
            "inv_index_entries": len(self.inv_index),
            "avg_inv_list_len": (
                sum(len(s) for s in self.inv_index.values()) / max(len(self.inv_index), 1)
            ),
        }


# ─── 内置分词器 ────────────────────────────────────────

def tokenize_text(text: str) -> list[str]:
    """
    默认中英文分词器（与 tfidf_engine.tokenize 保持一致）。
    
    如果安装了 jieba，可替换为 jieba_tokenize() 获得更好的中文分词效果。
    """
    import re
    
    text = text.lower()
    tokens = []
    
    # 英文词和数字
    en_tokens = re.findall(r"[a-z][a-z0-9]*", text)
    tokens.extend(en_tokens)
    
    # 中文字符序列 → n-gram
    cn_seqs = re.findall(r"[\u4e00-\u9fff]+", text)
    for seq in cn_seqs:
        tokens.extend(list(seq))          # 单字
        for i in range(len(seq) - 1):
            tokens.append(seq[i:i+2])     # bigram
        for i in range(len(seq) - 2):
            tokens.append(seq[i:i+3])     # trigram
    
    return tokens


def jieba_tokenize(text: str) -> list[str]:
    """
    jieba 中文分词器（可选依赖）。
    
    使用前需确保已安装: pip install jieba
    未安装时自动降级为内置 n-gram 分词器。
    """
    try:
        import jieba
    except ImportError:
        return tokenize_text(text)
    
    import re
    text_lower = text.lower()
    tokens = []
    
    # 英文词和数字
    en_tokens = re.findall(r"[a-z][a-z0-9]*", text_lower)
    tokens.extend(en_tokens)
    
    # 中文用 jieba 分词
    cn_seqs = re.findall(r"[\u4e00-\u9fff]+", text)
    for seq in cn_seqs:
        tokens.extend(jieba.lcut(seq))
    
    return tokens
