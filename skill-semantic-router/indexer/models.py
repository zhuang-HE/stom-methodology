# -*- coding: utf-8 -*-
"""
models.py — 索引数据结构定义
================================
DiscoveredSkill: 从 SKILL.md 解析出的 skill 元数据
SyncReport:      索引同步变更报告

遵循 STOM 方法论：纯数据层，~65 行。
"""

from dataclasses import dataclass, field, asdict


@dataclass
class DiscoveredSkill:
    """
    从 SKILL.md 解析出的 skill 元数据。
    
    由 SkillIndexManager.scan() 生成，
    通过 to_index_entry() 转换为 skill_index.json 格式。
    """
    id: str              # skill 标识（目录名）
    name: str            # frontmatter name
    description: str     # frontmatter description（精简版，用于路由）
    triggers: list[str]  # 触发关键词列表
    path: str            # SKILL.md 绝对路径
    source: str          # "user" | "plugin"
    file_hash: str       # 文件内容 SHA-256 (前12位)
    complexity: int = 2  # 复杂度 1-3
    category: str = ""   # 领域分类（可选）

    def to_index_entry(self) -> dict:
        """转换为 skill_index.json 格式"""
        entry = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "triggers": self.triggers,
            "path": str(self.path),
            "complexity": self.complexity,
            "priority": 1,
            "source": self.source,
            "file_hash": self.file_hash,
        }
        if self.category:
            entry["category"] = self.category
        return entry


@dataclass
class SyncReport:
    """
    索引同步报告。
    
    由 SkillIndexManager.sync() 生成，
    记录本次扫描与索引之间的 diff 结果。
    """
    timestamp: str = ""
    discovered_count: int = 0          # 扫描到的总数
    index_count: int = 0               # 索引中的总数
    added: list[dict] = field(default_factory=list)      # 新增
    modified: list[dict] = field(default_factory=list)    # 变更
    removed: list[dict] = field(default_factory=list)     # 移除/废弃
    unchanged: int = 0                 # 无变化

    def summary(self) -> str:
        """生成可读的同步摘要文本"""
        lines = [
            f"\n{'='*55}",
            f"  Skill Index Sync Report — {self.timestamp}",
            f"{'='*55}",
            f"  扫描发现: {self.discovered_count} 个 skill",
            f"  索引现有: {self.index_count} 个 skill",
            f"  {'─'*40}",
            f"  + 新增: {len(self.added)}",
            f"  ~ 变更: {len(self.modified)}",
            f"  - 移除: {len(self.removed)}",
            f"  = 无变: {self.unchanged}",
            f"{'='*55}",
        ]
        for item in self.added:
            lines.append(f"  [+] {item['id']} ({item.get('source','?')})")
        for item in self.modified:
            lines.append(f"  [~] {item['id']} (hash changed)")
        for item in self.removed:
            lines.append(f"  [-] {item['id']} (not found on disk)")
        return "\n".join(lines)
