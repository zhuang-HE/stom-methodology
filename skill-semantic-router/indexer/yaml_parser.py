# -*- coding: utf-8 -*-
"""
yaml_parser.py — YAML Frontmatter 解析器（纯 Python，无 PyYAML 依赖）
=====================================================================
解析 SKILL.md 的 YAML frontmatter，提取 name/description/triggers 等字段。

支持格式:
  - 键值对: key: value
  - 内联列表: [a, b, c]
  - 列表项: - item
  - 多行字符串: > 或 |

遵循 STOM 方法论：单一职责，~75 行。
"""

import re


def parse_frontmatter(content: str) -> dict:
    """
    解析 SKILL.md 的 YAML frontmatter。
    
    Args:
        content: 完整的 SKILL.md 文件内容
        
    Returns:
        解析出的字段字典，未匹配到返回空字典
    """
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    raw = match.group(1)
    result = {}
    current_key = None
    current_val = []
    in_multiline = False
    multiline_indent = 0

    for line in raw.split("\n"):
        # 多行值继续
        if in_multiline:
            if line.strip() == "" or not line.startswith(" " * multiline_indent):
                result[current_key] = "\n".join(current_val).strip()
                current_key = None
                current_val = []
                in_multiline = False
            else:
                current_val.append(line.strip())
            continue

        # 键值对
        kv_match = re.match(r"^(\w[\w-]*)\s*:\s*(.*)", line)
        if kv_match:
            if current_key and current_val:
                result[current_key] = (current_val if isinstance(current_val, list)
                                       else "\n".join(current_val).strip())

            current_key = kv_match.group(1)
            val = kv_match.group(2).strip()

            if val in (">", "|"):
                in_multiline = True
                current_val = []
                multiline_indent = len(line) - len(line.lstrip()) + 2
            elif val.startswith("["):
                items = re.findall(r"[\w.-]+", val)
                result[current_key] = items
                current_key = None
            elif val.startswith("- "):
                current_val = [val[2:].strip()]
            elif val:
                result[current_key] = val
                current_key = None
            continue

        # 列表续行
        if current_key and line.strip().startswith("- "):
            current_val.append(line.strip()[2:].strip())

    # 收尾
    if current_key:
        if in_multiline:
            result[current_key] = "\n".join(current_val).strip()
        elif isinstance(current_val, list) and current_val:
            result[current_key] = current_val

    return result


def extract_triggers_from_description(description: str) -> list[str]:
    """
    从 description 中提取触发词。
    
    WorkBuddy SKILL.md 常在 description 末尾包含：
      "触发词：xxx、yyy、zzz"
      
    Args:
        description: frontmatter 中的 description 字段
        
    Returns:
        触发词字符串列表
    """
    trigger_match = re.search(
        r"触发词[：:]\s*(.*?)(?:\n|$)",
        description,
        re.DOTALL,
    )
    if not trigger_match:
        return []

    trigger_text = trigger_match.group(1)
    return [t.strip() for t in re.split(r"[、，,\n]", trigger_text)
            if t.strip() and len(t.strip()) > 0]


def extract_complexity(frontmatter: dict) -> int:
    """
    从 frontmatter 中提取复杂度等级。
    
    支持格式:
      - 整数: 1 / 2 / 3
      - 星号: ⭐ / ⭐⭐ / ⭐⭐⭐
      - 默认: 2
      
    Args:
        frontmatter: 已解析的 frontmatter 字典
        
    Returns:
        复杂度 1-3
    """
    raw = frontmatter.get("complexity", "**")
    if isinstance(raw, int):
        return min(max(raw, 1), 3)
    if isinstance(raw, str):
        star_count = raw.count("*")
        if star_count > 0:
            return min(star_count, 3)
    return 2


def file_content_hash(filepath: str) -> str:
    """计算文件内容的 SHA-256 hash（前12位）"""
    import hashlib
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    except Exception:
        return ""
