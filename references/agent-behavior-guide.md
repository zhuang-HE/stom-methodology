# Agent 行为指南（全局执行策略规范）

> **注意**：这些不是 SKILL.md 的编写规则，而是 AI Agent 在**执行任务时**应遵循的行为准则。
> 本文件属于 L2 参考层，不需要在每次 Skill 加载时都读入上下文。

---

## A. 搜索优于遍历

```
❌ 错误：read_file 读取整个大文件，然后在上下文搜索
   → 代价：整个文件内容进入上下文 = 大量 token

✅ 正确：先用 search_content / search_file 定位目标
   → 然后用 read_file + limit/offset 只读相关部分
   → 代价：只有匹配行 + 目标区域进入上下文
```

| 场景 | 推荐方法 |
|------|---------|
| 找某个函数/类/变量定义 | `search_content(pattern="def function_name")` |
| 找某个配置项 | `search_content(pattern="config_key")` |
| 找某段代码的调用位置 | `search_content(pattern="function_name\(")` |
| 浏览项目结构 | `list_dir` + `search_file`（按 pattern）|
| 读日志找错误 | `search_content(pattern="ERROR\|Exception", path=logfile)` |

---

## B. 子智能体卸载

当需要探索 **≥10 个文件** 或做 **大规模代码分析** 时：

```python
# ❌ 在主上下文中逐个 read_file 20 个文件
# → 每个 file 的内容都占上下文 → 很快撑爆

# ✅ 卖给 code-explorer 子智能体
task(subagent_name="code-explorer",
     prompt="在 {project} 中找出所有 Controller 类，列出它们的方法和路由")
# → 主上下文只收到最终摘要（通常 < 100 行）
```

**触发条件**：
- 需要读 10+ 文件才能回答的问题
- "帮我看看这个项目的架构"
- "找到所有使用了 X 的地方"
- 跨多文件的依赖关系分析

---

## C. 工具结果裁剪

工具返回的数据往往比需要的多。在回复用户时：

```
❌ 差："这是 API 返回的所有数据：[粘贴 5000 字 JSON]"

✅ 好："关键发现：
       - 茅台 PE(TTM)=28.5，处于近 3 年 45% 分位
       - 近 5 日北向资金净流入 2.3 亿
       - 详细数据已保存到 {path}
       如需完整原始数据可以查看该文件"
```

**原则**：
- 用户要结论 → 给结论 + 关键证据 + 数据文件路径
- 用户要原始数据 → 给文件路径 + 格式说明 + 行数
- 不要把大数据原样塞进对话

---

## D. 并行调用

多个**无依赖**的操作，一次并行发出：

```python
# ❌ 串行（4 轮对话）
read_file("A.py")  → 等待 → read_file("B.py")  → 等待 → ...
total: 4 rounds

# ✅ 并行（1 轮对话）
同时发出:
  - read_file("A.py")
  - read_file("B.py")
  - read_file("C.py")
  - read_file("D.py")
total: 1 round (4x 效率提升)
```

**注意**：有依赖关系的操作不能并行（如：先读 A 决定是否读 B）。

---

## E. 综合效率清单（任务中随时自检）

```
□ 我是否在读已经读过的文件？→ 停止，从上下文引用
□ 我是否能用 search 代替全文件读取？→ 改用 search
□ 这 3 个操作是否有依赖？→ 无依赖则并行发出
□ 我是否在向用户展示过多原始数据？→ 裁剪为摘要
□ 是否应该把这个探索性任务给子智能体？→ >10 文件时考虑
□ 当前 Skill 加载了几个？→ ≥3 个时警惕
```
