# -*- coding: utf-8 -*-
"""
Skill Index Manager — 动态索引管理引擎
======================================
自动扫描文件系统中的 SKILL.md 文件，解析 frontmatter 元数据，
与 skill_index.json 进行 diff/merge/sync，实现索引的持续进化。

核心能力：
  1. 全量扫描：扫描 ~/.workbuddy 下所有 SKILL.md（用户级 + 插件级）
  2. 解析提取：从 YAML frontmatter 提取 name/description/triggers 等字段
  3. 智能同步：新增 skill 自动入库，变更 skill 检测并更新，废弃 skill 标记
  4. 索引重建：全量重建 skill_index.json + TF-IDF 向量索引
  5. 变更追踪：记录每次 sync 的 diff，支持审计回溯

用法:
  from skill_index_manager import SkillIndexManager

  mgr = SkillIndexManager()
  mgr.scan()                    # 扫描文件系统
  report = mgr.sync()           # 与索引对比，生成变更报告
  mgr.apply_sync(report)        # 应用变更到索引
  # 或一步到位：
  mgr.full_sync()               # scan + sync + apply
"""

import json
import re
import os
import sys
import io
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── 配置 ────────────────────────────────────────────────────────────────────

# 默认扫描根目录
DEFAULT_SCAN_ROOTS = [
    Path("~/.workbuddy/skills"),                          # 用户级 skill
    Path("~/.workbuddy/plugins/marketplaces"),            # 插件级 skill
]

# 索引文件路径
DEFAULT_INDEX_PATH = Path(__file__).parent / "skill_index.json"

# 变更日志路径
DEFAULT_CHANGELOG_PATH = Path(__file__).parent / "index_changelog.json"


# ─── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class DiscoveredSkill:
    """从 SKILL.md 解析出的 skill 元数据"""
    id: str                           # skill 标识（目录名）
    name: str                         # frontmatter name
    description: str                  # frontmatter description
    triggers: list[str]               # 从 description 中提取的触发词
    path: str                         # SKILL.md 绝对路径
    source: str                       # "user" | "plugin"
    file_hash: str                    # 文件内容 hash（用于变更检测）
    complexity: int = 2               # 复杂度
    category: str = ""                # 领域分类（可选）

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
    """索引同步报告"""
    timestamp: str = ""
    discovered_count: int = 0         # 扫描到的总数
    index_count: int = 0              # 索引中的总数
    added: list[dict] = field(default_factory=list)       # 新增
    modified: list[dict] = field(default_factory=list)     # 变更
    removed: list[dict] = field(default_factory=list)      # 移除/废弃
    unchanged: int = 0                # 无变化

    def summary(self) -> str:
        lines = [
            f"\n{'='*55}",
            f"  Skill Index Sync Report — {self.timestamp}",
            f"{'='*55}",
            f"  扫描发现: {self.discovered_count} 个 skill",
            f"  索引现有: {self.index_count} 个 skill",
            f"  {'─'*40}",
            f"  🆕 新增: {len(self.added)}",
            f"  🔄 变更: {len(self.modified)}",
            f"  ❌ 移除: {len(self.removed)}",
            f"  ✅ 无变化: {self.unchanged}",
            f"{'='*55}",
        ]
        for item in self.added:
            lines.append(f"  [+] {item['id']} ({item.get('source','?')})")
        for item in self.modified:
            lines.append(f"  [~] {item['id']} (hash changed)")
        for item in self.removed:
            lines.append(f"  [-] {item['id']} (not found on disk)")
        return "\n".join(lines)


# ─── YAML Frontmatter 解析（纯 Python，无 PyYAML 依赖）────────────────────

def parse_frontmatter(content: str) -> dict:
    """
    解析 SKILL.md 的 YAML frontmatter。
    支持 > 和 | 多行字符串、列表格式。
    """
    # 提取 --- 分隔的 frontmatter
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    raw = match.group(1)
    result = {}
    current_key = None
    current_val = []
    in_multiline = False
    multiline_indent = 0

    for line in raw.split('\n'):
        # 多行值继续
        if in_multiline:
            if line.strip() == '' or not line.startswith(' ' * multiline_indent):
                # 多行值结束
                result[current_key] = '\n'.join(current_val).strip()
                current_key = None
                current_val = []
                in_multiline = False
            else:
                current_val.append(line.strip())
            continue

        # 键值对
        kv_match = re.match(r'^(\w[\w-]*)\s*:\s*(.*)', line)
        if kv_match:
            if current_key and current_val:
                result[current_key] = current_val if isinstance(current_val, list) else '\n'.join(current_val).strip()

            current_key = kv_match.group(1)
            val = kv_match.group(2).strip()

            if val in ('>', '|'):
                # 多行字符串开始
                in_multiline = True
                current_val = []
                multiline_indent = len(line) - len(line.lstrip()) + 2
            elif val.startswith('['):
                # 内联列表: [a, b, c]
                items = re.findall(r'[\w.-]+', val)
                result[current_key] = items
                current_key = None
            elif val.startswith('- '):
                # 列表开始
                current_val = [val[2:].strip()]
            elif val:
                result[current_key] = val
                current_key = None
            # val 为空 → 下行可能是列表或多行值
            continue

        # 列表续行
        if current_key and line.strip().startswith('- '):
            current_val.append(line.strip()[2:].strip())
            continue

    # 收尾
    if current_key:
        if in_multiline:
            result[current_key] = '\n'.join(current_val).strip()
        elif isinstance(current_val, list) and current_val:
            result[current_key] = current_val

    return result


def extract_triggers_from_description(description: str) -> list[str]:
    """
    从 description 中提取触发词。
    WorkBuddy SKILL.md 的 description 常在末尾包含 "触发词：xxx、yyy"。
    """
    triggers = []

    # 匹配 "触发词：" 或 "触发词:" 后面的内容
    trigger_match = re.search(
        r'触发词[：:]\s*(.*?)(?:\n|$)',
        description, re.DOTALL
    )
    if trigger_match:
        trigger_text = trigger_match.group(1)
        # 按 "、", "，", "," 分割
        triggers = [t.strip() for t in re.split(r'[、，,\n]', trigger_text) if t.strip() and len(t.strip()) > 0]

    return triggers


def extract_complexity(frontmatter: dict) -> int:
    """从 frontmatter 中提取复杂度"""
    raw = frontmatter.get('complexity', '⭐⭐')
    if isinstance(raw, int):
        return min(max(raw, 1), 3)
    if isinstance(raw, str):
        star_count = raw.count('⭐')
        if star_count > 0:
            return min(star_count, 3)
    return 2


def file_content_hash(filepath: str) -> str:
    """计算文件内容的 SHA256 hash"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]
    except Exception:
        return ""


# ─── 索引管理器 ──────────────────────────────────────────────────────────────

class SkillIndexManager:
    """
    Skill 索引动态管理器
    
    职责：
      1. 扫描文件系统中所有 SKILL.md
      2. 解析提取元数据
      3. 与现有索引对比（diff）
      4. 生成同步报告
      5. 应用变更（merge）
      6. 追踪变更历史
    """

    def __init__(
        self,
        index_path: str = str(DEFAULT_INDEX_PATH),
        changelog_path: str = str(DEFAULT_CHANGELOG_PATH),
        scan_roots: list[str] | None = None,
    ):
        self.index_path = Path(index_path)
        self.changelog_path = Path(changelog_path)
        self.scan_roots = [Path(p).expanduser() for p in (scan_roots or DEFAULT_SCAN_ROOTS)]
        
        # 运行时状态
        self.discovered: dict[str, DiscoveredSkill] = {}  # id → DiscoveredSkill
        self.index: dict = {}                             # 当前索引数据
        self._load_index()

    # ─── 索引加载 ─────────────────────────────────────────────────────

    def _load_index(self):
        """加载现有索引"""
        if self.index_path.exists():
            with open(self.index_path, 'r', encoding='utf-8-sig') as f:
                self.index = json.load(f)
        else:
            self.index = {
                "version": "1.0.0",
                "generated_at": "",
                "description": "Skill 语义索引（自动管理）",
                "skills": [],
                "routing_rules": {},
            }

    def _save_index(self):
        """保存索引到文件"""
        self.index["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.index["version"] = self._next_version()
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def _next_version(self) -> str:
        """递增 patch 版本号"""
        ver = self.index.get("version", "1.0.0")
        parts = ver.split('.')
        parts[-1] = str(int(parts[-1]) + 1)
        return '.'.join(parts)

    # ─── 扫描 ─────────────────────────────────────────────────────────

    def scan(self) -> int:
        """
        扫描所有 skill 目录，解析 SKILL.md frontmatter。
        返回发现的 skill 数量。
        """
        self.discovered = {}
        count = 0

        for root in self.scan_roots:
            if not root.exists():
                continue

            # 递归查找所有 SKILL.md
            for skill_md in root.rglob("SKILL.md"):
                try:
                    skill = self._parse_skill_md(skill_md)
                    if skill:
                        self.discovered[skill.id] = skill
                        count += 1
                except Exception as e:
                    print(f"[WARN] 解析失败: {skill_md} → {e}")

        print(f"[Scanner] 发现 {count} 个 skill（用户级 + 插件级）")
        return count

    def _parse_skill_md(self, filepath: Path) -> Optional[DiscoveredSkill]:
        """解析单个 SKILL.md 文件"""
        # 提取 skill ID（SKILL.md 所在目录名）
        skill_id = filepath.parent.name
        
        # 跳过内部/测试 skill
        skip_patterns = ['__pycache__', '.git', 'node_modules', 'test']
        for pattern in skip_patterns:
            if pattern in str(filepath):
                return None

        content = filepath.read_text(encoding='utf-8')
        frontmatter = parse_frontmatter(content)
        
        if not frontmatter:
            return None

        name = frontmatter.get('name', skill_id)
        description = frontmatter.get('description', '')
        
        # 提取触发词
        triggers = extract_triggers_from_description(description)
        
        # 如果 description 太长（有多行），取第一段作为路由用描述
        route_desc = self._extract_route_description(description, frontmatter)
        
        # 判断来源
        source = "user" if "/skills/" in str(filepath).replace("\\", "/") and "/plugins/" not in str(filepath).replace("\\", "/") else "plugin"
        
        complexity = extract_complexity(frontmatter)
        fhash = file_content_hash(str(filepath))

        return DiscoveredSkill(
            id=skill_id,
            name=name,
            description=route_desc,
            triggers=triggers,
            path=str(filepath),
            source=source,
            file_hash=fhash,
            complexity=complexity,
        )

    def _extract_route_description(self, description: str, frontmatter: dict) -> str:
        """
        提取用于路由的精简描述。
        优先使用 description 的第一段（不含触发词），补充 name 和英文关键词。
        """
        if not description:
            return frontmatter.get('name', '')
        
        # 移除触发词部分
        desc = re.sub(r'触发词[：:].*$', '', description, flags=re.DOTALL).strip()
        
        # 取第一句/第一段（到第一个句号或换行）
        first_part = re.split(r'[。\n]', desc, maxsplit=1)[0].strip()
        
        # 如果太短，多取一些
        if len(first_part) < 20 and len(desc) > 20:
            first_part = desc[:200].strip()
        
        # 去掉多余空白
        first_part = re.sub(r'\s+', ' ', first_part).strip()
        
        return first_part

    # ─── 同步（Diff）───────────────────────────────────────────────────

    def sync(self) -> SyncReport:
        """
        对比扫描结果与现有索引，生成变更报告。
        """
        report = SyncReport(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            discovered_count=len(self.discovered),
            index_count=len(self.index.get("skills", [])),
        )

        index_skills = {s["id"]: s for s in self.index.get("skills", [])}
        discovered_ids = set(self.discovered.keys())
        index_ids = set(index_skills.keys())

        # 新增
        for sid in sorted(discovered_ids - index_ids):
            skill = self.discovered[sid]
            report.added.append(asdict(skill))

        # 移除（在索引中但磁盘上不存在）
        for sid in sorted(index_ids - discovered_ids):
            report.removed.append({"id": sid, "name": index_skills[sid].get("name", sid)})

        # 变更检测
        for sid in sorted(discovered_ids & index_ids):
            skill = self.discovered[sid]
            existing = index_skills[sid]
            
            # 通过 file_hash 检测内容变更
            if skill.file_hash and skill.file_hash != existing.get("file_hash", ""):
                report.modified.append({
                    "id": sid,
                    "name": existing.get("name", sid),
                    "old_hash": existing.get("file_hash", ""),
                    "new_hash": skill.file_hash,
                })
            else:
                report.unchanged += 1

        return report

    # ─── 应用同步 ─────────────────────────────────────────────────────

    def apply_sync(self, report: SyncReport, remove_missing: bool = True):
        """
        将 sync 报告中的变更应用到索引。
        
        策略：
          - 新增：直接从扫描结果入库
          - 变更：只更新 file_hash（用于下次 diff 检测），不覆盖 description/triggers
            因为手动精选的 description/triggers 质量高于自动提取的
          - 移除：从索引中删除
        
        Args:
            report: SyncReport 实例
            remove_missing: 是否移除磁盘上不存在的 skill（默认 True）
        """
        skills = self.index.get("skills", [])
        skill_map = {s["id"]: s for s in skills}

        # 新增
        for item in report.added:
            new_skill = self.discovered[item["id"]]
            entry = new_skill.to_index_entry()
            skill_map[new_skill.id] = entry
            print(f"  [+] 新增: {new_skill.id} ({new_skill.source})")

        # 变更 — 只更新 file_hash，保留人工优化的元数据
        for item in report.modified:
            updated_skill = self.discovered[item["id"]]
            old = skill_map.get(updated_skill.id)
            if old:
                old["file_hash"] = updated_skill.file_hash
                old["source"] = updated_skill.source
                print(f"  [~] 更新 hash: {updated_skill.id}")
            else:
                entry = updated_skill.to_index_entry()
                skill_map[updated_skill.id] = entry
                print(f"  [+] 新增: {updated_skill.id}")

        # 移除
        if remove_missing:
            for item in report.removed:
                sid = item["id"]
                if sid in skill_map:
                    del skill_map[sid]
                    print(f"  [-] 移除: {sid}")

        self.index["skills"] = list(skill_map.values())
        self._save_index()
        
        # 记录变更日志
        self._append_changelog(report)
        
        print(f"\n  索引已更新: {len(self.index['skills'])} 个 skill")

    def _append_changelog(self, report: SyncReport):
        """追加变更记录到 changelog"""
        changelog = []
        if self.changelog_path.exists():
            try:
                with open(self.changelog_path, 'r', encoding='utf-8') as f:
                    changelog = json.load(f)
            except Exception:
                changelog = []

        entry = {
            "timestamp": report.timestamp,
            "discovered": report.discovered_count,
            "index_total": report.index_count,
            "added": [i["id"] for i in report.added],
            "modified": [i["id"] for i in report.modified],
            "removed": [i["id"] for i in report.removed],
        }
        changelog.append(entry)

        # 只保留最近 100 条
        changelog = changelog[-100:]

        with open(self.changelog_path, 'w', encoding='utf-8') as f:
            json.dump(changelog, f, ensure_ascii=False, indent=2)

    # ─── 一键全量同步 ────────────────────────────────────────────────

    def full_sync(self, remove_missing: bool = True) -> SyncReport:
        """
        一键完成：扫描 → 对比 → 应用。
        返回同步报告。
        """
        print("\n🔄 开始全量索引同步...")
        
        count = self.scan()
        if count == 0:
            print("[WARN] 未发现任何 SKILL.md，请检查扫描路径")
            return SyncReport(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        report = self.sync()
        print(report.summary())

        if report.added or report.modified or report.removed:
            self.apply_sync(report, remove_missing=remove_missing)
        else:
            print("  索引已是最新，无需更新")

        return report

    # ─── 查询接口 ─────────────────────────────────────────────────────

    def get_skill(self, skill_id: str) -> Optional[dict]:
        """查询单个 skill 的索引信息"""
        for s in self.index.get("skills", []):
            if s["id"] == skill_id:
                return s
        return None

    def list_skills(self, source: str = "") -> list[dict]:
        """列出所有 skill（可按 source 过滤）"""
        skills = self.index.get("skills", [])
        if source:
            skills = [s for s in skills if s.get("source") == source]
        return skills

    def get_stats(self) -> dict:
        """获取索引统计信息"""
        skills = self.index.get("skills", [])
        categories = {}
        sources = {}
        for s in skills:
            cat = s.get("category", "未分类")
            src = s.get("source", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
            sources[src] = sources.get(src, 0) + 1

        return {
            "total_skills": len(skills),
            "categories": categories,
            "sources": sources,
            "index_version": self.index.get("version", "?"),
            "generated_at": self.index.get("generated_at", "?"),
        }


# ─── CLI 入口 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Skill Index Manager — 动态索引管理")
    parser.add_argument("--scan", action="store_true", help="仅扫描，输出发现的 skill 列表")
    parser.add_argument("--sync", action="store_true", help="扫描并同步到索引")
    parser.add_argument("--stats", action="store_true", help="显示索引统计信息")
    parser.add_argument("--find", type=str, help="按 ID 查找 skill")
    parser.add_argument("--root", type=str, help="自定义扫描根目录")
    parser.add_argument("--dry-run", action="store_true", help="仅显示变更，不写入")

    args = parser.parse_args()

    kwargs = {}
    if args.root:
        kwargs["scan_roots"] = [args.root]

    mgr = SkillIndexManager(**kwargs)

    if args.stats:
        stats = mgr.get_stats()
        print(f"\n📊 索引统计:")
        print(f"  总 skill 数: {stats['total_skills']}")
        print(f"  版本: {stats['index_version']}")
        print(f"  生成时间: {stats['generated_at']}")
        print(f"  来源分布: {stats['sources']}")
        print(f"  类别分布: {stats['categories']}")

    elif args.find:
        skill = mgr.get_skill(args.find)
        if skill:
            print(json.dumps(skill, ensure_ascii=False, indent=2))
        else:
            print(f"[NOT FOUND] skill '{args.find}' 不在索引中")

    elif args.scan:
        count = mgr.scan()
        print(f"\n发现的 skill 列表:")
        for sid, skill in sorted(mgr.discovered.items()):
            print(f"  [{skill.source:6s}] {sid}")

    elif args.sync:
        if args.dry_run:
            mgr.scan()
            report = mgr.sync()
            print(report.summary())
            print("\n  [DRY RUN] 未写入任何变更")
        else:
            mgr.full_sync()

    else:
        # 默认：全量同步
        mgr.full_sync()
