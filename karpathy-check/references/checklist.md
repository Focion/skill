# 检查项清单

本文件承载 karpathy-check 的全部检查项清单，由 `SKILL.md` 的核心流程逐条执行。

判定依据为 [guidelines.md](references/guidelines.md)（Agent 行为准则）与 [instruction.md](references/instruction.md)（指令书写准则）两份准则原文；本文件只给检查项编号、名称、依据锚点与严重度归档，判定条款以每项 `依据` 列指向的章节原文为唯一来源。

清单分两类：`K1`–`K13` 对应 `mode=agent`，`I1`–`I5` 对应 `mode=instruction`，`mode=both` 时两类全量判定。

`严重度` 列为固定归档值，同一检查项在不同被检查文件中的取值一律相同，**严禁**按个案调整。

## 一、Agent 行为准则检查项（依据 guidelines.md）

作用对象：代码文件、Agent 的产出物。

上下文依赖：K1、K6、K7、K10、K11 的判定依赖 `sessionLog` 中的会话过程记录；K4、K5 的判定依赖 `diffRef` 解析出的改动行集合。对应参数缺省时该项一律标 `➖`。

| # | 检查项 | 依据 | 严重度 |
|---|--------|------|--------|
| K1 | 暴露假设与权衡 | [§1](references/guidelines.md#1-编码前先思考) | 高 |
| K2 | 简洁优先 | [§2](references/guidelines.md#2-简洁优先) | 中 |
| K3 | 禁止投机性设计 | [§2](references/guidelines.md#2-简洁优先) | 中 |
| K4 | 精准改动 | [§3](references/guidelines.md#3-精准改动) | 中 |
| K5 | 孤儿代码清理 | [§3](references/guidelines.md#3-精准改动) | 中 |
| K6 | 可验证成功标准 | [§4](references/guidelines.md#4-目标驱动执行) | 高 |
| K7 | 困惑暂停机制 | [§5](references/guidelines.md#5-困惑管理) | 高 |
| K8 | 禁止编造 | [§6](references/guidelines.md#6-输出边界) | 高 |
| K9 | TODO/FIXME 残留 | [§6](references/guidelines.md#6-输出边界) | 低 |
| K10 | 错误即承认 | [§6](references/guidelines.md#6-输出边界) | 高 |
| K11 | 改前说明计划 | [§6](references/guidelines.md#6-输出边界) | 中 |
| K12 | 调试残留 | [§7](references/guidelines.md#7-自查清单) | 低 |
| K13 | 错误处理覆盖 | [§7](references/guidelines.md#7-自查清单) | 中 |

## 二、指令书写准则检查项（依据 instruction.md）

作用对象：Skill 定义文件、Prompt 文件、给 Agent 的指令文档。

本类各项只依赖 `filePath` 全文，无 `diffRef` / `sessionLog` 依赖。[§5 反模式](references/instruction.md#5-反模式) 为本类各项的取反表述，与各项 `依据` 章节同为判定条款来源。

| # | 检查项 | 依据 | 严重度 |
|---|--------|------|--------|
| I1 | 声明式优于命令式 | [§1](references/instruction.md#1-给成功标准不给步骤) | 高 |
| I2 | 可执行验证标准 | [§4](references/instruction.md#4-让-agent-自己进-loop) | 高 |
| I3 | 先朴素后优化 | [§2](references/instruction.md#2-先朴素正确版再优化) | 中 |
| I4 | 测试先行与测试审查 | [§3](references/instruction.md#3-写测试先行把审查重心从实现移到测试) | 中 |
| I5 | 自循环能力 | [§4](references/instruction.md#4-让-agent-自己进-loop) | 高 |

## 三、可观测信号补充

下列信号在准则原文中无对应字符串，仅作为机械扫描的入口，用于把该检查项定位到具体行；命中后是否计入违规，**必须**回落该项 `依据` 章节的原文条款判定。未列入本节的检查项一律直接按 `依据` 章节原文逐条判定。

- K12：被检查文件中出现字符串 `console.log`、`print`、`debugger` 之一的行
- I1：连续 3 步及以上的「先做 X 再做 Y 再做 Z」步骤序列形态
