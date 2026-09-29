# CLAUDE.md（etf-t0）

本文件是 `etf-t0/` 下三个 skill 的**唯一权威说明**。仓库根 `CLAUDE.md` 只保留指向本文件的一行指针，ETF 相关的边界、契约、既存偏差一律不在根文件复述——改动这三个 skill 的任何内容前先读完本文件。仓库级的通用规则（SKILL.md 标准形态、体量上限、退出码约定、书写规范位置、如何校验）仍以根 `CLAUDE.md` 与 `skill-check/references/` 为准。

## 这个目录是什么

`etf-t0/` 是一个**分组目录，不是 skill**：它自身没有 `SKILL.md`，只用来把同一条流水线的三个 skill 收在一起。

- 根 `CLAUDE.md`「skill 根目录只允许四项（`SKILL.md` / `references/` / `scripts/` / `assets/`）」约束的是 `etf-t0-analysis/` 这一层，**不是** `etf-t0/` 这一层。本文件放在 `etf-t0/` 下合规，不要当成违规去「修正」。
- ⚠️ **这三个 skill 不随 `install.sh` 安装**：脚本顶部 `EXCLUDE="etf-t0"` 把整个分组排除，`install`、全量安装、`--uninstall` 一律不碰它们；`./install.sh -l` 仍会列出它们并标「已排除」（末尾附 `← etf-t0/` 标出来自分组目录），指名安装则报错退 `2`。要恢复随脚本安装，从 `EXCLUDE` 里删掉 `etf-t0`；只想临时装一个，手动 `ln -s "$PWD/etf-t0/<name>" ~/.claude/skills/<name>`——注意链接名**只取 basename**，不带 `etf-t0/` 前缀，否则路由不到。
- 因此 `frontmatter.name` 必须等于**各自的目录名**（如 `etf-t0-analysis`），**不含** `etf-t0/` 前缀。
- 每个 skill 内部的**链接基准仍是各自的 skill 根目录**（`references/x.md`），不随分组目录改变，也严禁写成 `../` 跨出自己的 skill 根。

## 三个 ETF skill 的边界（改任一个前先读这段）

`etf-t0-analysis` → `etf-t0-execution` → `etf-t0-summary` 是**一条流水线的三段**，按交易日的盘前 / 盘中 / 盘后切分，边界由约束固定，不要合并也不要互相搬内容：

| | analysis（盘前） | execution（盘中） | summary（盘后） |
|---|---|---|---|
| 产出 | 分析报告 + 计划态 `.state.json` | 操作手册 `etf-t0-ops-{symbol}-{date}.md` | 复盘 `etf-t0-review-{symbol}-{date}.md` + 结算态 `.state.json` + 长期沉淀 `etf-t0-lessons-{symbol}.md` |
| 决定 | 三态、`W`/`L`、生效上限、轮次、委托单清单、关键价位 | 只做落地：成本锚点、股数取小、挂单尾数、时段动作、错误预案 | 登记：成交台账、差异归因（`DV1`–`DV7`）、纪律核查（`DA1`–`DA14`）、相对强弱与量能（`BM1`–`BM4`）、结算数据、沉淀条目；判定：信号有效性（`SG1`–`SG6`）、次日情景落点（A/B/C 或未落点）；周/月度只做聚合（`PA1`–`PA9`、`PT1`–`PT3`） |
| 个人数据 | 只用 `position` 做结构诊断 | 必须问到 `Q1`–`Q6` 才能生成（`ETE2`） | 必须问到 `RV1`/`RV2`/`RV5` 才能生成（`ETS3`） |
| 越界禁令 | `ETA12`：不得在报告里写逐时段时间表/挂单尾数，须发交接问询后等用户同意 | `ETE1`：不得重算或改写报告任何策略参数 | `ETS5`：次日内容**只允许**以「观察项 + 阈值 + 情景 + 定性操作倾向」形态出现，不得写次日的三态/`W`/`L`/价位/委托单清单/轮次数字/金额；`ETS2`：不得重算或改写报告与手册所载值 |

- 下游段一律以 `reportPath` / `manualPath` / `statePath` 消费上游的**产物文件**，不跨 skill 链接对方的 `references/`——跨目录链接会破坏「链接基准为 skill 根目录」这条规则。**三者被收进同一个 `etf-t0/` 目录后这条禁令一字不变**：物理上更近了不构成互链的理由，`../etf-t0-analysis/references/…` 依然违规
- 下游段的 references 也因此**只引用报告所载值**（`tick`、申报单位、集合竞价时点、放量阈值、最小单笔金额），不复写 framework/calc-methods 的任何阈值；报告没载的规则数值一律写「须用户自行核实」（`ETE6`、`ETS11`），这是 `etf-t0-analysis` 附录 D 悬空问题的下游处置
- 上一条有**两个刻意的例外**，都在 `etf-t0-summary` 内、都自带唯一出处、都**只用于登记与情景映射、严禁当作交易参数**：`board-signal-review.md` §三 的「基本同步」判据 `|差| ≤ 0.10pct`，与 `next-day-outlook.md` §三 路由表的板块阈值（`±2.0%` 等）。它们不是从 framework 抄来的，也不参与任何 `W`/`L`/轮次/仓位判定
- `etf-t0-execution`（`SKILL.md` 199 行）与 `etf-t0-summary`（`SKILL.md` 198 行）是本仓库**符合 house 布局的两个参考实现**（`references/` 互引写作 `references/x.md`，只有输出模板一份略超 200 行）；与它们对照可看出 `etf-t0-analysis` 的三处既存偏差
- ⚠️ `etf-t0-summary/SKILL.md` **198 行，几乎顶满 200 行上限**（`references/` 十份，12 项参数、15 条约束 ↔ 15 条 Red Flag 1:1 绑定、7 条反合理化，砍不掉）。它已经压过一轮：STEP 1 的校验 bullet 并成 3 条（必填+格式 / 枚举+文件 / 透传+创建）、STEP 2 的十份 reference 清单两份挤一行、STEP 3/4/5 的错误处置 bullet 压回正文段落、`stderr` 字段约束三条并成一行——`ETS14`/`ETS15` 与 STEP 9 就是这么塞进去的，**不要「顺手」再把它们拆开**。下一次扩展要么把周/月度聚合拆成独立 skill，要么只改 `references/` 而不动 `SKILL.md`

## 状态文件的落盘契约（`.state.json` 同名覆盖，改动前必读）

同一交易日的 `etf-t0-{code}-{date}.state.json` 由 analysis 先写**计划态**、summary 收盘后**覆盖为结算态**，这是刻意设计：

- analysis STEP 7 ① 只查找「日期**早于**本次 `date` 的最近一个 `.state.json`」，故同名覆盖后次日命中的必然是结算态，**analysis 侧无需改动即生效**
- 计划态在覆盖前归档为 `etf-t0-{code}-{date}.plan.json`。**该后缀刻意不用 `.state.json`**——否则会被 analysis 的历史 state 查找命中，造成同一日期两份 state、「最近一个」不唯一
- `settled` 字段标出该份 state 是计划态（`false`）还是结算态（`true`）。analysis 写入时结算类字段（`account_equity`、`realized_pnl_today`/`_week`、`account_equity_week_high`）客观不可知、按 ETA10 一律为 `null`，这正是「冷启动档」与「单周档不可核查」的根因；summary 补齐这四项后，次日 `cold_start.active = false`、回撤口径 A/B 四档全部可核查
- summary 另新增 `rounds_ledger`（最近 100 轮 `{date, direction, pnl_net}` 流水），`rolling_stats` 的 `sample_n`/`p_100`/`r_100` 由它机械算出——没有这份流水，framework §7 的 n=100 策略衰减检测永远拿不到 `p_100`
- 幂等：读到的 state 已 `settled == true`、或目标 `.plan.json` 已存在时**跳过归档**，避免重跑复盘把结算态当计划态归档掉
- ⚠️ 次日前瞻（`§八之二` 的档位、观察项读数、三情景、落点）**严禁**写入 `.state.json`（`next-day-outlook.md` §一、§七 第 6 条）。state 是给 analysis 读的**已结算事实**，掺入情景推断会让 analysis 把 summary 昨天的猜测当成输入数据，形成自我确认回路。前瞻只活在复盘文档里

## 次日前瞻的双档契约与节号约定（改 `next-day-outlook.md` 或 `review-template.md` 前必读）

A 股 15:00 收盘时今夜美股还没开，所以「明天的依据」天然分两档，同一份复盘文档**跑两次、就地改写**（`§八之二`），**严禁**新建第二份文件：

- **档位判定不硬编码时区**：判据是「美股隔夜型 key 返回的**时间戳北京日期 − 1** 是否 ≥ 复盘日」。实测 `gb_$sox` 返回 `2026-08-08 05:16` 对应的是 **8/7** 美股交易日，这条机械规则自动吃掉夏令时切换与美股假日；改成按固定钟点判断会在每年两次时令切换时静默判错
- **三类 key 语义不同，不可混用**：美股隔夜型（`gb_*`/`int_dji`/`int_nasdaq`/`int_sp500`，隔夜才更新）→ 判档唯一依据；连续盘型（`hf_*`/`fx_*`/`DINIW`，24h）→ 可读但须标取数时刻；港股现货型（`rt_hk*`/`int_hangseng`）→ **前瞻严禁采用**（与 A 股同时段收盘、不含隔夜信息），港股方向的隔夜信息一律取恒指夜期 `hf_HSI`
- **追溯复盘时前瞻整节不适用**（§二 第 0 行，优先于 `outlookStage`）：判据是「最近一根已收日线日期 > 复盘日」。补做三天前的复盘时「次日」已经走完，拿一根更晚的外盘读数去推它是倒因为果
- **`BM4` 与前瞻节的同名指标是两根不同的 K**：`BM4`（昨夜外盘背景）是**已经作用在今日盘面上**的那一根，前瞻节要的是**今夜**那一根。两节都强制写「对应交易日」正是为了让这个区别可机械核对（`RF-ETS14` 的判据之一就是两处对应交易日相同）
- **模板节号用 `二之二` / `八之二`，`§一`–`§九` 一律不重编**：`period-review.md` 的 `PA1` 读各份文档的 `§四`、`PA2` 读 `§五`、`PA5` 读 `§三`，重编号会同时打断周月聚合口径与已落盘历史文档。`PA9`（信号验证率）也因此按 `PA3` 的原则处理——缺 `§二之二` 的旧文档标「该节缺载」且不并入分母

## 三个 skill 占用的编号命名空间

前缀须在**整个仓库内**唯一（约束前缀、检查项 ID、skill 内部条目 ID 三类之间也不得撞车）。这三个 skill 已占用：

- 约束：`ETA`（analysis）、`ETE`（execution）、`ETS`（summary）
- 内部条目 ID：`Q` / `U` / `X` / `R` / `EP` / `P`（execution 的问询项、成本用途、禁用清单、委托规则、错误预案、时段号）；`RV` / `DV` / `DA` / `M` / `L` / `PA` / `PT` / `BM` / `SG`（summary 的问询项、差异类别、纪律核查项、盘面核对项、沉淀条目、周月聚合项、周月趋势判据、相对强弱登记项、信号有效性项）
- ⚠️ 裸 `B` 与裸 `S` 已被 `skill-check` 的 `B1`–`B9` / `S1`–`S3` 占用，故 summary 一律用双字母（`BM`/`SG`）。新增条目类别前先核对根 `CLAUDE.md`「编号前缀登记」的三个集合

## 退出码例外（改 `SKILL.md` 正文前必读）

`etf-t0-execution` 与 `etf-t0-summary` 属「纯对话执行、无进程退出码」的 skill，须在输出末尾单独打印一行 `状态：{含义}（exitCode={N}）`。该例外的判据是「`SKILL.md` **正文**中既无 `scripts/` 调用行、也无 `basic.md` §1.1 所列反引号命令串」。

- `etf-t0-summary` 用 `Bash` 取盘后行情、对标基准与外盘指标，但三处命令串全部下沉在 `references/market-recheck.md`、`references/board-signal-review.md`、`references/next-day-outlook.md`，`SKILL.md` 正文只写「按该文件取数」——**往正文加一行 `curl` 会当场破掉这个例外**
- `etf-t0-analysis` 有 `产物文件` 落盘，走的是另一条路径，不适用本例外

## 已知偏差与悬空依赖（`etf-t0-analysis`，不要当模板抄）

`etf-t0-analysis/` 的目录嵌套已修正（现为 `SKILL.md` + `references/` 五份文件，符合 house 布局），但仍有三处既存问题：

1. **「主文档」`T0日内回转交易体系.md` 已不在仓库内**，而 `SKILL.md` 与 `references/` 下除 report-template 外的每一份文件都仍把它的**附录 B**（`.state.json` 基础字段）与**附录 D**（外部规则快照表：最小变动价位、申报单位、涨跌幅、临停阈值、集合竞价时段、印花税/过户费）声明为「唯一出处」
2. `SKILL.md` 372 行、`references/strategy-framework.md` 871 行、`references/calc-methods.md` 548 行，均超体量上限（分别为 200 / 500 行）
3. description 命中只读型词表却未声明 `allowed-tools`，而流程实际需要 `Bash`（`data-sources.md` 用公开接口取数）与 `Write`（落盘报告 + `.state.json`，`产物文件` 表齐备且路径占位符已在参数表声明，符合落盘例外）

另有一处全 skill 通用偏差：`references/` 内部互引一律写成 `./calc-methods.md` 这类同目录形式（`strategy-framework.md` 有 9 处），与 `organization.md` §4「链接基准为 skill 根目录、严禁同目录相对形式」相冲突；house style 的写法是 `references/calc-methods.md`。

### 悬空外部依赖的处置

附录 D 的交易所规则数值与附录 B 的状态文件基础字段在仓库内**没有任何定义处**。而约束 `ETA11` 要求凡引用附录 D 数值必须同时写出「该值 + 快照日期」，`ETA1` / `RF-ETA11` 又明令严禁为标「待核实」的行填猜测值。三者叠加的后果是：

- 需要这些数值时，**不要凭记忆或常识补**（`0.001 元` tick、ETF `100 份` / 可转债 `10 张` 申报单位在正文里以「附录 D 代入结果」的身份出现，不是独立定义）——按 `ETA11` 标注「规则快照可能过期，须复核」，或向用户索取主文档
- 若要根治，两条路：把附录 B / D 作为 `references/` 下的独立主题文件补回（如 `state-schema.md`、`exchange-rules.md`），或改由用户提供主文档路径。前者需同步改掉散落在四份文件里的全部「主文档附录 X」指向

## 改完怎么校验

任何结构性改动之后对改过的 `SKILL.md` 跑一次 `skill-check`（`filePath=etf-t0/<skill>/SKILL.md`、`scope=all`）。其报告检查项总数为 `57 + 16 × refCount`（analysis refCount=5、execution=6、summary=10）；通过 + 违规 + 不适用三数之和不等于该数，说明检查没跑完。指令质量另按 `karpathy-check`（`mode=instruction`）。
