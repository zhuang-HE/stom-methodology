# -*- coding: utf-8 -*-
"""
index_manager.py — 动态索引管理器（STOM 重构版）
=================================================
核心能力:
  1. 全量扫描: 扫描 ~/.workbuddy 下所有 SKILL.md（用户级 + 插件级）
  2. 智能同步: 新增入库 / 变更检测 / 废弃标记
  3. 索引持久化: JSON 格式 + 变更日志
  4. CLI 入口: --scan / --sync / --stats / --find

遵循 STOM 方法论：单一职责（索引生命周期管理），~300 行。
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 同包导入
from indexer.models import DiscoveredSkill, SyncReport, asdict
from indexer.yaml_parser import (
    parse_frontmatter,
    extract_triggers_from_description,
    extract_complexity,
    file_content_hash,
)
# 跨包导入
from config import DEFAULT_SCAN_ROOTS, DEFAULT_INDEX_PATH, DEFAULT_CHANGELOG_PATH


class SkillIndexManager:
    """
    Skill 索引动态管理器。
    
    使用方式:
        mgr = SkillIndexManager()
        report = mgr.full_sync()   # 一键扫描+同步
        
        # 或分步执行:
        mgr.scan()                 # 扫描文件系统
        report = mgr.sync()        # 生成变更报告
        mgr.apply_sync(report)     # 应用变更
    
    职责:
      1. 扫描 → 解析 frontmatter → DiscoveredSkill 列表
      2. 对比 → Diff → SyncReport（新增/变更/移除）
      3. 应用 → 合并到 skill_index.json
      4. 追踪 → 记录 changelog
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
        self.discovered: dict[str, DiscoveredSkill] = {}
        self.index: dict = {}
        self._load_index()

    # ─── 索引加载/保存 ──────────────────────────────

    def _load_index(self):
        """加载现有索引或创建空索引模板"""
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8-sig") as f:
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
        """保存索引到文件（自动更新时间戳和版本号）"""
        self.index["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.index["version"] = self._next_version()
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def _next_version(self) -> str:
        """递增 patch 版本号 (x.y.z → x.y.(z+1))"""
        ver = self.index.get("version", "1.0.0")
        parts = ver.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)

    # ─── 扫描 ────────────────────────────────────────

    def scan(self) -> int:
        """
        扫描所有 skill 目录，解析 SKILL.md frontmatter。
        
        Returns:
            发现的 skill 数量
        """
        self.discovered = {}
        count = 0

        for root in self.scan_roots:
            if not root.exists():
                continue

            for skill_md in root.rglob("SKILL.md"):
                try:
                    skill = self._parse_skill_md(skill_md)
                    if skill:
                        self.discovered[skill.id] = skill
                        count += 1
                except Exception as e:
                    print(f"[WARN] 解析失败: {skill_md} -> {e}")

        print(f"[Scanner] 发现 {count} 个 skill（用户级 + 插件级）")
        return count

    def _parse_skill_md(self, filepath: Path) -> Optional[DiscoveredSkill]:
        """解析单个 SKILL.md 文件为 DiscoveredSkill"""
        skill_id = filepath.parent.name

        # 跳过内部/测试目录
        skip_patterns = ["__pycache__", ".git", "node_modules", "test"]
        for pattern in skip_patterns:
            if pattern in str(filepath):
                return None

        content = filepath.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(content)
        if not frontmatter:
            return None

        name = frontmatter.get("name", skill_id)
        description = frontmatter.get("description", "")
        triggers = extract_triggers_from_description(description)

        # 提取精简描述（用于语义向量化的版本）
        route_desc = self._extract_route_description(description, frontmatter)

        # 判断来源
        fp_str = str(filepath).replace("\\", "/")
        source = ("user" if "/skills/" in fp_str and "/plugins/" not in fp_str
                  else "plugin")
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

    @staticmethod
    def _extract_route_description(description: str, frontmatter: dict) -> str:
        """提取用于路由的精简描述（第一段 + 去触发词 + 去空白）"""
        if not description:
            return frontmatter.get("name", "")

        desc = re.sub(r"触发词[：:].*$", "", description, flags=re.DOTALL).strip()
        first_part = re.split(r"[。\n]", desc, maxsplit=1)[0].strip()

        if len(first_part) < 20 and len(desc) > 20:
            first_part = desc[:200].strip()

        return re.sub(r"\s+", " ", first_part).strip()

    # ─── 同步（Diff）─────────────────────────────────

    def sync(self) -> SyncReport:
        """
        对比扫描结果与现有索引，生成变更报告（不写入）。
        
        Returns:
            SyncReport 实例
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
            from dataclasses import asdict as _ad
            report.added.append(_ad(skill))

        # 移除（在索引中但磁盘上不存在）
        for sid in sorted(index_ids - discovered_ids):
            report.removed.append({"id": sid, "name": index_skills[sid].get("name", sid)})

        # 变更检测（通过 file_hash）
        for sid in sorted(discovered_ids & index_ids):
            skill = self.discovered[sid]
            existing = index_skills[sid]
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

    # ─── 应用同步 ────────────────────────────────────

    def apply_sync(self, report: SyncReport, remove_missing: bool = True):
        """
        将同步报告中的变更应用到索引。
        
        策略:
          - 新增: 从扫描结果直接入库
          - 变更: 只更新 file_hash（保留人工优化的元数据）
          - 移除: 从索引中删除
        """
        skills = self.index.get("skills", [])
        skill_map = {s["id"]: s for s in skills}

        # 新增
        for item in report.added:
            new_skill = self.discovered[item["id"]]
            entry = new_skill.to_index_entry()
            skill_map[new_skill.id] = entry
            print(f"  [+] 新增: {new_skill.id} ({new_skill.source})")

        # 变更（只更新 hash，保留人工优化的 description/triggers）
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
        self._append_changelog(report)

        print(f"\n  索引已更新: {len(self.index['skills'])} 个 skill")

    def _append_changelog(self, report: SyncReport):
        """追加变更记录到 changelog JSON"""
        changelog = []
        if self.changelog_path.exists():
            try:
                with open(self.changelog_path, "r", encoding="utf-8") as f:
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
        changelog = changelog[-100:]  # 只保留最近 100 条

        with open(self.changelog_path, "w", encoding="utf-8") as f:
            json.dump(changelog, f, ensure_ascii=False, indent=2)

    # ─── 一键全量同步 ────────────────────────────────

    def full_sync(self, remove_missing: bool = True) -> SyncReport:
        """一键完成：扫描 -> 同步 -> 应用。返回报告。"""
        print("\n开始全量索引同步...")

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

    # ─── 查询接口 ────────────────────────────────────

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

    # ─── CLI 入口 ─────────────────────────────────────

    @staticmethod
    def cli():
        """命令行入口"""
        import argparse

        parser = argparse.ArgumentParser(
            description="Skill Index Manager — 动态索引管理"
        )
        parser.add_argument("--scan", action="store_true", help="仅扫描")
        parser.add_argument("--sync", action="store_true", help="扫描并同步")
        parser.add_argument("--stats", action="store_true", help="统计信息")
        parser.add_argument("--find", type=str, help="按ID查找")
        parser.add_argument("--root", type=str, help="自定义扫描根目录")
        parser.add_argument("--dry-run", action="store_true", help="仅预览不写入")

        args = parser.parse_args()

        kwargs = {}
        if args.root:
            kwargs["scan_roots"] = [args.root]

        mgr = SkillIndexManager(**kwargs)

        if args.stats:
            stats = mgr.get_stats()
            print(f"\n索引统计:")
            print(f"  总数: {stats['total_skills']}")
            print(f"  版本: {stats['index_version']}")
            print(f"  生成: {stats['generated_at']}")
            print(f"  来源: {stats['sources']}")
            print(f"  类别: {stats['categories']}")

        elif args.find:
            skill = mgr.get_skill(args.find)
            if skill:
                print(json.dumps(skill, ensure_ascii=False, indent=2))
            else:
                print(f"[NOT FOUND] '{args.find}' 不在索引中")

        elif args.scan:
            count = mgr.scan()
            print(f"\n发现的 skill:")
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
            mgr.full_sync()


if __name__ == "__main__":
    SkillIndexManager.cli()
