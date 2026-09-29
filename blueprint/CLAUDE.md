# CLAUDE.md（blueprint）

本文件是 `blueprint/` 下八个 skill 的**唯一权威说明**。仓库根 `CLAUDE.md` 只保留指向本文件的一行指针，blueprint 相关的边界、契约、命名空间一律不在根文件复述——改动这八个 skill 的任何内容前先读完本文件。仓库级的通用规则（SKILL.md 标准形态、体量上限、退出码约定、书写规范位置、如何校验）仍以根 `CLAUDE.md` 与 `skill-check/references/` 为准。

## 这个目录是什么

`blueprint/` 是一个**分组目录，不是 skill**：它自身没有 `SKILL.md`，只用来把同一条流水线的八个 skill 与一份共用协议收在一起。

- 根 `CLAUDE.md`「skill 根目录只允许四项（`SKILL.md` / `references/` / `scripts/` / `assets/`）」约束的是 `blueprint-product/` 这一层，**不是** `blueprint/` 这一层。本文件与 `_shared/` 放在 `blueprint/` 下合规，不要当成违规去「修正」。
- `_shared/` 目录下没有 `SKILL.md`，`install.sh` 的两层发现规则会直接跳过它，**不会**把它当成 skill。
- `frontmatter.name` 必须等于**各自的目录名**（如 `blueprint-product`），**不含** `blueprint/` 前缀。编排段的目录名与 name 都仍是 `idea-blueprint`——旧的触发语与已安装的符号链接因此继续有效。
- 每个 skill 内部的**链接基准仍是各自的 skill 根目录**（`references/x.md`），不随分组目录改变，也严禁写成 `../` 跨出自己的 skill 根。

## 这条流水线是怎么拆出来的（2026-08-25）

原先是单个 `idea-blueprint`（`SKILL.md` 199 行顶满上限、`references/` 23 份、25 条约束），按「产品 / 商业 / 技术 / 营销 / 推广 / 实施」六个方面各自可独立运行的诉求拆成八段。拆分的三条硬理由，都能在文件里逐条核对：

1. **裁决必须独立成段**：八条算式里只有 `FC1` 的输入落在单一段内，其余七条跨两个以上段（`FC4` 要 `TEC1`+`PRD4`+`OPS2`+`OPS7`）；十一个否决项里六个跨段（`KO2`/`KO3`/`KO4`/`KO5`/`KO9`/`KO10`）。任何单段 skill 都判不了这 13 项。
2. **完整度分母从全局改成分段**：旧口径是「42 项门禁 / 全局分母」，现在每段报自己的分母（产品 11 / 商业 8 / 技术 5 / 营销 5 / 推广 5 / 实施 7 = 41），裁决段另按 `scope` 取 41 或 14 作为【模型假设】占比的分母。
3. **共创协议只能单源**：提问、取证、标签、发散、就地更新这套机制八段都要用，照抄八份必然漂移，故收进 `_shared/co-create.md` 并用脚本同步（见下节）。

拆分带来的三处**净删除**，不要再把它们找回来：

- `split-rules.md`（135 行）与 `BP24` 整体作废。旧的八个分册后缀 `prd`/`com`/`tec`/`mkt`/`grw`/`ops`/`verdict`/`evidence` 与现在各段天然各写一份产物 1:1，「终稿拆分 + 节名守恒自检」这套补丁没有存在理由了。
- 旧 `completeness-gate.md` 的 42 项门禁砍到 6 项。`CG1`~`CG15` 与 `CG22`~`CG42` 共 36 项的通过判据全是「字段闭环」，拆分后由各段字段清单的闭环判据直接承载；只有 6 项非字段门禁留在裁决段，重编为 `CG1`~`CG6`。
- `mode=screen` 不再横切各段的判定规则。档位退化为编排段的参数：编排段决定调哪几段、以哪个 `scope` 调；各段只在自己的 `fields.md` 第四节声明本档字段子集。旧 `evidence` 分册也一并取消——取证记录与冲突登记各自留在本段分册里。

原始 23 份文件的完整副本在仓库根 `_backup/idea-blueprint-20260825/`（与 `_backup/idea-blueprint-old-toplevel/` 内容相同，是同一份的两次备份）。确认新结构可用后可以整个删掉 `_backup/`，`install.sh` 已把它列入 `EXCLUDE`。

## 八段的边界（改任一个前先读这段）

段序恒为产品 → 商业 → 技术 → 营销 → 推广 → 实施 → 裁决，由编排段调度。

| 段 | skill | 约束前缀 | 字段 | 产物 |
|---|---|---|---|---|
| 编排 | `idea-blueprint` | `BP` | `RQ1`~`RQ8` | 索引 `blueprint-{slug}.md` + 台账 `blueprint-{slug}.fields.json` |
| 产品 | `blueprint-product` | `IBP` | `PRD1`~`PRD11` | `-prd.md` |
| 商业 | `blueprint-commercial` | `IBC` | `COM1`~`COM8` | `-com.md` |
| 技术 | `blueprint-tech` | `IBT` | `TEC1`~`TEC5` | `-tec.md` |
| 营销 | `blueprint-marketing` | `IBM` | `MKT1`~`MKT5` | `-mkt.md` |
| 推广 | `blueprint-growth` | `IBG` | `GRW1`~`GRW5` | `-grw.md` |
| 实施 | `blueprint-ops` | `IBO` | `OPS1`~`OPS7` | `-ops.md` |
| 裁决 | `blueprint-verdict` | `IBV` | `FC1`~`FC8` / `KO1`~`KO11` / `CG1`~`CG6` | `-verdict.md` + 回填索引 |

三条贯穿全部八段的越界禁令：

- **六个共创段只闭环字段与登记事实，不做否决判定、不写结论态**（`IBP13`/`IBC12`/`IBT12`/`IBM12`/`IBG12`/`IBO12`）。段内发现单位经济性为负、验证失败、渠道进不去时**只**如实记录并当场告知用户，判定权在裁决段。这是拆分后最容易被违反的一条：模型很容易顺手在商业段下「这事不行」的结论。
- **任一段严禁改写别段的分册**。需要改上游取值时交回编排段调对应段执行（`IBV11` 与各段 `fields.md` 第四节末条）。
- **各段只写台账里自己前缀的那个顶层键**（各段 `output-spec.md` 第四节）。裁决段只读台账、不写字段记录。

跨段一律以**产物文件**传递，**严禁**互链对方的 `references/`——`../blueprint-product/references/…` 违规，与 `etf-t0` 的同名禁令一字不变。各段之所以能引用上游取值，是因为它读的是台账，而不是上游 skill 的规范文件。

## 字段台账的落盘契约（`blueprint-{slug}.fields.json`，改动前必读）

台账是这条流水线的**唯一事实源**，八段共写一份、同名累加，替代了旧版「全程只维护一份 Markdown 工作文档」的契约。

- 顶层键固定八个：`meta` / `RQ` / `PRD` / `COM` / `TEC` / `MKT` / `GRW` / `OPS`（`idea-blueprint/references/pipeline-contract.md` 第二节）。裁决结果**不进台账**，只进裁决分册与索引。
- 单条记录形态 `{value, label, grade, source, date}` 定义在 `_shared/co-create.md` 10.1——**刻意放在共享协议里**，这样八段各自「定义自己写什么」时用的是同一份形态定义，不构成跨 skill 复述。
- `label` 五值封闭（`已确认`/`模型假设`/`缺口`/`不适用`/`待核实`），`grade` 取 `E1`~`E6` 或 `null`。裁决段的门禁三态判定、`CG2` 取证痕迹检查、【模型假设】占比全部只读这两个字段——**改动这两个枚举会同时打断 `gate-check.md` 的三节判据**。
- 台账**可以不存在**：任一段独立运行时先新建台账并追问 `RQ2` 与 `RQ4` 两项（各段 `fields.md` 第四节）。这正是「每段可独立运行」的技术前提。
- 台账缺 `PRD` 分区时，下游段把上游字段全部标【缺口】并在分册首行下方写「本册未经产品方案锚定」一行（`IBC14`/`IBT14`/`IBM14`/`IBG14`/`IBO14`）。这一行是 `RF-IBx14` 的唯一判据，**严禁**省略。
- 幂等以「索引的还原字段是否与本次 `demand` 一致」为判据（`pipeline-contract.md` 第六节），不一致时停下来请用户选定沿用哪一份，**严禁**替用户判定两份诉求是同一件事。

## 共创协议的单源与同步（改 `co-create.md` 前必读）

⚠️ `_shared/co-create.md`（352 行）是**唯一编辑入口**，八个 skill 的 `references/co-create.md` 都是它的逐字副本。

- 改完**必须**跑 `blueprint/_shared/sync.sh` 重新分发；`sync.sh -c`（或 `--check`）只比对不写，八份都报「一致」才算同步完成，任一份不一致时退出码为 `1`。
- **严禁**直接改某个 skill 里的副本——下一次 `sync.sh` 会静默覆盖掉你的修改。
- 该文件**刻意不含任何 markdown 链接**：它要在八个不同的 skill 根下都能通过「链接基准为 skill 根目录 + 无死链」两条检查，任何跨文件指向一律写成反引号包裹的文件名（`references/fields.md`、`references/output-spec.md`）。往里加链接会在缺少该文件的 skill 里变成死链——裁决段就没有 `fields.md`。
- 它承载的十节：闭环三形态、候选生成、处置四分类、单字段处置上限、来源等级 `E1`~`E6`、取证记录、来源追问与冲突登记、发散手法 `DG1`~`DG12`、单轮输出五行格式、分册与台账的就地更新。**`DG` 与 `E` 因此是跨 skill 共用的编号命名空间**，是本仓库唯一一处刻意共用的编号。

## 档位契约（`mode=screen` / `scope=screen`）

编排段的 `mode` 决定调哪几段并把 `scope` 透传下去，两个参数名不同、值域相同（`screen`/`full`），**不要合并**：`mode` 管调度，`scope` 管单段内的字段范围。

- 快筛档只调五段：产品、商业、技术、实施、裁决（`idea-blueprint/references/screen-mode.md` 第二节，封闭清单）。营销段与推广段在本档**必须**整段跳过并且**严禁**建立分册——空分册会让索引把它们标成已交回。
- 各段的 screen 子集：产品 3（`PRD1`/`PRD2`/`PRD4`）、商业 6、技术 3、实施 2，合计 14。**这个 14 与 `blueprint-verdict/references/gate-check.md` 文首的 `scope=screen` 取 14 必须同步改**；`full` 档的 41 同理，等于六段字段数之和。
- 快筛档只能判「证据不足」/「不做」/「可继续」三态（`feasibility-gate.md` 4.2），**严禁**判「推进」「缩范围推进」「转向」。结论态名称与判据都由裁决段持有，编排段的 `screen-mode.md` 刻意不声明取值范围，只在结论态为「可继续」时按第三节发升档问询。

## 三处机械可查的耦合（改任一处后按这三条对一遍）

1. **字段数三处一致**：每段 `fields.md` 文首声明的字段总数 ↔ `pipeline-contract.md` 第一节段序表的「字段数」列 ↔ `gate-check.md` 文首的 41 / 14。
2. **算式输入必须在台账里有对应字段**：`feasibility-gate.md` 第一、二节引用的每个字段编号，都必须是某段 `fields.md` 第一节所载字段或 `RQ` 还原字段。引用了不存在的字段，算式恒为不可判定，结论恒为「证据不足」。
3. **产物类型路由成对**：`blueprint-product/references/product-spec.md` 第一节的六行路由 ↔ 六份 `product-type-*.md`。未命中六类的产物类型回落 `product-type-tool.md`；加新类型必须同时加路由行与一份同构分册（表头逐字一致的三列），只加一处即破坏 `IBP2` 的读取指向。

## 八段占用的编号命名空间

前缀须在**整个仓库内**唯一（约束前缀、检查项 ID、skill 内部条目 ID 三类之间也不得撞车）。这八个 skill 已占用：

- 约束：`BP`（编排，沿用旧前缀）、`IBP`、`IBC`、`IBT`、`IBM`、`IBG`、`IBO`、`IBV`
- 内部条目 ID：`RQ`（编排段还原字段）、`PRD`/`COM`/`TEC`/`MKT`/`GRW`/`OPS`（各段字段，一个前缀只属一个 skill）、`FC`/`KO`/`CG`（裁决段的算式、否决项、非字段门禁）
- 跨 skill 共用：`DG`（发散手法）、`E`（来源等级），定义在 `_shared/co-create.md`，八份副本里各出现一次
- 已消失：`DIM-`（旧维度代码，段代码改用 `PRD`/`COM`/… 裸前缀）

## 退出码例外

八段全部属「纯对话执行、无进程退出码」，须在输出末尾单独打印一行 `状态：{含义}（exitCode={N}）`。该例外的判据是「`SKILL.md` **正文**中既无 `scripts/` 调用行、也无 `basic.md` §1.1 所列反引号命令串」——`_shared/sync.sh` 是分组目录下的运维脚本，不属任何 skill 的 `scripts/`，也没有任何 `SKILL.md` 调用它，故例外成立。往任何一份 `SKILL.md` 正文加一行 shell 命令会当场破掉这个例外。

`allowed-tools` 两档：七个共创段为 `[Read, Write, Edit, WebSearch, WebFetch]`，裁决段为 `[Read, Write, Edit]`（它不取证，缺证据一律交回对应段）。八段的 description 都刻意**不含** `basic.md` §1.1 只读型词表里的词（检查/审查/校验/排查/诊断/查询/分析/调研/统计），故按非只读型技能判定，`Edit` 合规——**往能力描述里加一个「分析」会让八份 `allowed-tools` 同时违规**（只读型技能的落盘例外只放开 `Write`）。

## 改完怎么校验

任何结构性改动之后对改过的 `SKILL.md` 跑一次 `skill-check`（`filePath=blueprint/<skill>/SKILL.md`、`scope=all`）。其报告检查项总数为 `57 + 16 × refCount`（编排段 refCount=4、产品段 10、商业/技术/营销/推广/实施段各 3、裁决段 4）；通过 + 违规 + 不适用三数之和不等于该数，说明检查没跑完。指令质量另按 `karpathy-check`（`mode=instruction`）。

改 `_shared/co-create.md` 之后额外跑 `blueprint/_shared/sync.sh -c`，八份都报「一致」才算改完。
