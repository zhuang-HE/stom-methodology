# -*- coding: utf-8 -*-
"""
tfidf_engine.py — TF-IDF 向量化引擎（纯 Python，零外部依赖）
=============================================================
提供中文 bigram/trigram 分词 + TF-IDF 稀疏向量构建 + 余弦相似度计算。

遵循 STOM 方法论：单一职责，仅负责向量化，~95 行。
"""

import math
import re
from collections import Counter
from typing import Tuple


def tokenize(text: str) -> list[str]:
    """
    改进中英文分词。
    
    策略：
      - 英文：提取小写单词和数字
      - 中文：单字 + bigram(2字) + trigram(3字) 滑动窗口
    
    Args:
        text: 原始文本
        
    Returns:
        token 列表
    """
    text = text.lower()
    tokens = []

    # 英文词和数字
    en_tokens = re.findall(r"[a-z][a-z0-9]*", text)
    tokens.extend(en_tokens)

    # 中文字符序列 → 滑动窗口生成 n-gram
    cn_seqs = re.findall(r"[\u4e00-\u9fff]+", text)
    for seq in cn_seqs:
        tokens.extend(list(seq))          # 单字
        for i in range(len(seq) - 1):
            tokens.append(seq[i:i+2])     # bigram
        for i in range(len(seq) - 2):
            tokens.append(seq[i:i+3])     # trigram

    return tokens


def build_tfidf_index(
    skills: list[dict]
) -> Tuple[dict, list[Counter]]:
    """
    构建 TF-IDF 索引。
    
    每个 skill 的「文档」= description + triggers 拼接。
    输出:
      - idf: 全局 IDF 字典 {token: idf_value}
      - tfidf_vecs: 每个 skill 的 TF-IDF 稀疏向量列表
    
    Args:
        skills: skill 元数据列表（需含 description 和 triggers 字段）
        
    Returns:
        (idf_dict, tfidf_vectors) 元组
    """
    docs = []
    for skill in skills:
        text = skill["description"] + " " + " ".join(skill.get("triggers", []))
        docs.append(tokenize(text))

    # IDF 计算（平滑版，避免除零）
    N = len(docs)
    df: Counter = Counter()
    for tokens in docs:
        for token in set(tokens):
            df[token] += 1

    idf = {token: math.log((N + 1) / (count + 1)) + 1
           for token, count in df.items()}

    # 每个文档的 TF-IDF 向量
    tfidf_vecs = []
    for tokens in docs:
        tf = Counter(tokens)
        vec = {token: (count / len(tokens)) * idf.get(token, 0)
               for token, count in tf.items()}
        tfidf_vecs.append(vec)

    return idf, tfidf_vecs


def cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    """
    稀疏向量余弦相似度。
    
    Args:
        vec_a: 稀疏向量 {token: weight}
        vec_b: 稀疏向量 {token: weight}
        
    Returns:
        相似度 [0.0, 1.0]，任一零向量返回 0.0
    """
    dot = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in vec_b)
    norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
