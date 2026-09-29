# 检查项清单

本文件承载 skill-check 的全部检查项清单，由 `SKILL.md` 的核心流程逐条执行。

判定依据为 [basic.md](references/basic.md)、[organization.md](references/organization.md)、[constraint.md](references/constraint.md)、[numbering.md](references/numbering.md) 四份规范原文；本文件只给检查项名称与规范出处，判定标准以每项标注的规范出处原文为唯一来源。

清单分四类。`CK-B*`、`CK-C*`、`CK-N*` 的作用对象为被检查的 `SKILL.md` 单文件；`CK-R*` 的作用对象为被检查 skill `references/` 目录下的每一个 `.md` 文件，逐文件独立判定一遍。

## 一、结构检查（依据 basic.md、organization.md）

| # | 检查项 | 规范出处 |
|---|--------|---------|
| CK-B1 | frontmatter 存在性 | basic.md §1 |
| CK-B2 | `name` 格式 | basic.md §1 |
| CK-B3 | `name` 与父目录名一致 | basic.md §1 |
| CK-B4 | `description` 格式与写法要求 | basic.md §1 |
| CK-B5 | `triggers` 字段 | basic.md §1 |
| CK-B6 | `inputArgs` 与 `## 参数` 表双向一致 | basic.md §1 |
| CK-B7 | frontmatter 字段白名单 | basic.md §1 |
| CK-B8 | 路径解析 callout 位置 | basic.md §2 |
| CK-B9 | 路径解析 callout 措辞逐字匹配 | basic.md §2 |
| CK-B10 | 约束章节标题 | basic.md §3 |
| CK-B11 | 总纲与内联强约束格式 | basic.md §3 |
| CK-B12 | 约束表格列结构 | basic.md §3 |
| CK-B13 | `## 输出规范` 章节存在性 | basic.md §4 |
| CK-B14 | 产物文件表格列数 | basic.md §4.1 |
| CK-B15 | 退出码表格列数 | basic.md §4.2 |
| CK-B16 | 退出码值域 | basic.md §4.2 |
| CK-B17 | 退出码触发场景全覆盖 | basic.md §4.2 |
| CK-B18 | stderr 格式章节 | basic.md §4.3 |
| CK-B19 | 参数校验步骤位置 | basic.md §5 |
| CK-B20 | 参数校验声明式写法 | basic.md §5 |
| CK-B21 | 参数校验行标签顺序 | basic.md §5 |
| CK-B22 | 错误信息承载位置 | basic.md §6 |
| CK-B23 | 危险信号章节 | basic.md §8.1 |
| CK-B24 | 反合理化章节 | basic.md §8.2 |
| CK-B25 | 目录结构与 references 文件命名 | organization.md §1 |
| CK-B26 | `SKILL.md` 行数上限 | organization.md §2 |
| CK-B27 | 判定依据未被复制进 `SKILL.md` | organization.md §2 |
| CK-B28 | 对照原文的声明配有显式读取步骤 | organization.md §3 |
| CK-B29 | 相对链接有效性与书写基准 | organization.md §4 |
| CK-B30 | 脚本与指令单一承载 | organization.md §7 |
| CK-B31 | 格式约定规则配有正例 | organization.md §8 |
| CK-B32 | 易错点规则配有反例 | organization.md §8 |
| CK-B33 | 反例标注违规原因 | organization.md §8 |
| CK-B34 | 正反例注释标记格式 | organization.md §8 |
| CK-B35 | 示例不含真实业务信息 | organization.md §8 |
| CK-B36 | 同类表格表头一致性 | organization.md §8 |
| CK-B37 | 同类表格示例行一致性 | organization.md §8 |
| CK-B38 | `allowed-tools` 声明与工具收窄 | basic.md §1.1 |

## 二、约束书写检查（依据 constraint.md）

| # | 检查项 | 规范出处 |
|---|--------|---------|
| CK-C1 | 编号前缀格式 | constraint.md 规则 3 |
| CK-C2 | 编号连续性与起始值 | constraint.md 规则 3 |
| CK-C3 | 约束表 `#` 列禁止纯数字编号 | constraint.md 禁止事项 |
| CK-C4 | 约束表 `#` 列禁止中文编号 | constraint.md 禁止事项 |
| CK-C5 | 禁止超长前缀 | constraint.md 禁止事项 |
| CK-C6 | 禁止小写前缀 | constraint.md 禁止事项 |
| CK-C7 | 单一职责 | constraint.md 规则 4 |
| CK-C8 | 可判定性 | constraint.md 规则 4 |
| CK-C9 | 正面陈述 + 反面强调 | constraint.md 规则 4 |
| CK-C10 | 关键词粗体标记 | constraint.md 规则 6 |
| CK-C11 | 违反后处理写法 | constraint.md 规则 5 |
| CK-C12 | 约束集中管理（全文扫描） | constraint.md 禁止事项、basic.md §3 |

## 三、编号检查（依据 numbering.md）

| # | 检查项 | 规范出处 |
|---|--------|---------|
| CK-N1 | L1 大流程标题格式 | numbering.md §1、§6 |
| CK-N2 | L2 子步骤标题格式 | numbering.md §1、§6 |
| CK-N3 | L3 原子操作标题格式 | numbering.md §1、§6 |
| CK-N4 | 禁止罗马数字后缀 | numbering.md 禁止事项 |
| CK-N5 | 禁止有序列表充当子步骤（全文扫描） | numbering.md 禁止事项、不适用范围 |
| CK-N6 | 禁止小数编号 | numbering.md 禁止事项 |
| CK-N7 | 禁止中文前缀 | numbering.md 禁止事项 |

## 四、references 检查（依据 organization.md）

| # | 检查项 | 规范出处 |
|---|--------|---------|
| CK-R1 | 文件命名格式 | organization.md §1 |
| CK-R2 | 禁止无主题聚合命名 | organization.md §1 |
| CK-R3 | 单文件行数上限 | organization.md §2 |
| CK-R4 | 未复制被引用文档的判定依据 | organization.md §2 |
| CK-R5 | 相对链接有效性与书写基准 | organization.md §4 |
| CK-R6 | 不含免责或豁免声明 | organization.md §5 |
| CK-R7 | 条目无模糊词 | organization.md §9 S1 |
| CK-R8 | 条目无主观形容词 | organization.md §9 S2 |
| CK-R9 | 条目未合并多个判据 | organization.md §9 S3 |
| CK-R10 | 格式约定规则配有正例 | organization.md §8 |
| CK-R11 | 易错点规则配有反例 | organization.md §8 |
| CK-R12 | 反例标注违规原因 | organization.md §8 |
| CK-R13 | 正反例注释标记格式 | organization.md §8 |
| CK-R14 | 示例不含真实业务信息 | organization.md §8 |
| CK-R15 | 同类表格表头一致性 | organization.md §8 |
| CK-R16 | 同类表格示例行一致性 | organization.md §8 |
