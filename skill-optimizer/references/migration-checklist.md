# 迁移操作 Checklist

> skill-optimizer 执行「工作流C: 优化」时逐项确认。

## 前置检查

```
□ 已完成审计报告？用户已确认？
□ 当前 SKILL.md 的 version 号记录：v___
□ 备份当前版本的关键信息（行数/大小/主要结构）
```

## 内容迁移

### Step 1: 创建 references/

```
□ mkdir -p references/
□ 确认目录为扁平结构（无子目录）
```

### Step 2: 写入 L2 文件

对每个要移出的内容块：

```
□ [文件名] 内容完整移出？
□ 文件头有来源说明？（"从 SKILL.md v{x.y} 移出"）
□ 无引用其他 ref 文件的内容？
□ 文件大小 ≤ 200KB？
```

### Step 3: 重构 SKILL.md

```
□ 原内容块替换为引用指针？
□ 引用指针格式统一？（`详见 references/xxx.md`）
□ 新增「复杂任务检测」条件触发区块？
□ YAML frontmatter 中有 references 列表？
   - path 正确？
   - desc 简洁准确？
□ version 更新（minor +1）？
```

## 验证

```
□ 新行数 ≤ 350？
□ 新大小 ≤ 15 KB？
□ 所有引用路径指向实际存在的文件？
□ 无引用链（ref 文件之间不互引）？
□ YAML frontmatter 格式正确？
□ 核心业务含义未改变？
□ Top 10 常见任务中 ≥8 个仍可仅凭 SKILL.md 完成？
```

## 收尾

```
□ 审计报告更新为「后对比」数据？
□ 结果写入 skill-creation-guide「已审计 Skill 记录」表？
□ 记录到今日日志 memory file？
