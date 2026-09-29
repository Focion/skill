# {{FACILITY_NAME}} · 设施模型

> 本文件是这份设施模型的**常驻入口（L0）**：读取方只需常驻本文件，其余文件按下方路由表按需加载。
> 本文件只放路由与速查，内容都在下层——请勿写长。

| 键 | 值 |
|---|---|
| facility_id | `{{FACILITY_ID}}` |
| 设施类型 | `{{FACILITY_TYPE}}`（{{TYPE_ZH}}） |
| schema | `facility-model/{{SCHEMA_VERSION}}` |
| 生成时间 | {{DATE}} |
| 生成模式 | {{MODE}} |
| 时区 / 语言 | {{TZ}} / {{LANG}} |
| L0 预算 | ≤ 1800 tokens（超出即拆分到下层，见 `manifest.yaml#tiers`） |

---

## 1. 设施概述

<!-- @fill(human) 3-5 句客观描述：这是什么设施、服务对象是谁、主营的一件事、位置与归属。
     内容取自 profile/basic.yaml 的 one_liner 与 description，此处是它们的摘要副本。 -->

（待补充）

## 2. 硬约束速查

> 最多 5 条红线：不加载其他文件也必须成立的约束。每条须能在 `profile/rules.yaml` 找到对应规则 id。

<!-- @fill(generator|human) -->

1. （待补充）
2.
3.

## 3. 文件路由表

**用法**：先在「触发信号」列匹配当前任务，再只加载对应文件。不要预加载整棵树。

| 触发信号（用户/Agent 在问什么） | 加载 | 格式 | 层 | 可写性 |
|---|---|---|---|---|
| 这是什么设施、在哪、归谁管、怎么联系 | `profile/basic.yaml` | YAML | L1 | 只读 |
| 现在开不开、几点关、节假日、当前状态 | `profile/time.yaml` + `state/live.json` | YAML+JSON | L1 | 时间只读 / 状态可写 |
| 还能进多少人、满了没、要不要限流 | `profile/capacity.yaml` + `state/live.json` | YAML+JSON | L1 | 定义只读 / 占用可写 |
| 能不能进、能不能做某事、违规怎么办 | `profile/rules.yaml` | YAML | L1 | 只读 |
| 提供什么服务、怎么办、要什么条件 | `profile/services.yaml` | YAML | L1 | 只读 |
| 有多少东西、借得到吗、坏了几个 | `profile/resources.yaml` + `state/live.json` | YAML+JSON | L1 | 定义只读 / 数量可写 |
| 多少钱、押金、逾期罚多少 | `profile/pricing.yaml` | YAML | L2 | 只读 |
| 谁值班、找谁审批 | `profile/staffing.yaml` | YAML | L2 | 只读 |
| 隔壁是什么、上级设施、要不要转介 | `profile/relations.yaml` | YAML | L2 | 只读 |
| 外部如何查询与调用本设施 | `profile/protocol.yaml` | YAML | L1 | 只读 |
| 平时谁来用、什么时候忙、老规矩是什么 | `profile/usage.yaml` + `state/usage-digest.json` | YAML+JSON | L2 | 可写 |
| 刚才发生了什么、这次会话之前说过什么 | `memory/short-term.jsonl`（读尾部 N 条） | JSONL | L1 | 追加 |
| 历史上这类事怎么处理的、沉淀的经验 | `memory/long-term/INDEX.md` → 命中主题文件 | Markdown | L2→L3 | 可写 |
| 遇到具体情境（高峰/故障/冲突/应急/特例） | `scenarios/INDEX.md` → 命中剧本 | Markdown | L1→L2 | 可写 |
| 出事了、坏了、有人违规 | 追加 `state/incidents.jsonl` / `state/maintenance.jsonl` | JSONL | L2 | 追加 |
| 这个模型都有哪些文件、能不能写 | `manifest.yaml` | YAML | L1 | 只读 |

## 4. 加载层级

| 层 | 内容 | 约定 |
|---|---|---|
| L0 | 本文件 | 常驻 |
| L1 | 路由表命中的 `profile/` 单文件、`state/live.json`、两份 INDEX | 单次任务通常 1-3 个文件；先看 `scenarios/INDEX.md` 是否命中已知情境 |
| L2 | 场景剧本正文、长期记忆主题文件、计费/人员/拓扑细则 | 确认落入该主题后再加载 |
| L3 | `state/*.jsonl` 历史段、已归档记忆 | 仅复盘/统计时按窗口切片 |

`state/*.jsonl` 是仅追加的流水文件，按设计不整体读取：使用统计读 `state/usage-digest.json`，
近期上下文读 `memory/short-term.jsonl` 尾部窗口。

## 5. 文件权限矩阵

| 路径 | 可写方 | 更新方式 | 备注 |
|---|---|---|---|
| `profile/**`（除 usage） | human, generator | 覆写 | 设计态；变更须记入 `CHANGELOG.md` |
| `profile/usage.yaml` | human, generator, agent | 补丁 | 使用方可补充 `observed_*` 区块；`limits` / `procedures` 为只读 |
| `state/live.json` | agent | 覆写 | 以 `revision` 做乐观锁；写前先读并保留未识别字段 |
| `state/*.jsonl` | agent | 仅追加 | 一行一 JSON 对象；历史行不可改写 |
| `memory/short-term.jsonl` | agent | 仅追加 + 按策略截断 | 策略见 `memory/POLICY.md` |
| `memory/long-term/**` | agent | 新增/补丁 + 同步 INDEX | 晋升条件见 `memory/POLICY.md` |
| `scenarios/**` | human, generator, agent | 新增/补丁 + 同步 INDEX | 新增剧本标记 `status: 待验证` |
| `CHANGELOG.md` | 全部 | 仅追加 | — |

## 6. 完整度

> 首次生成时大量字段为空是**预期行为**。`@fill(...)` 注释标出了谁该在什么时候补。
> 运行 `scripts/validate.py <模型目录>` 可得到当前完整度与未补项清单。

| 层 | 首次生成状态 | 补充责任 |
|---|---|---|
| 基本信息 / 时间 / 容量 | 部分预填 | 人确认 |
| 服务 / 规则 / 资源 | 类型默认值 | 人校订 |
| 使用信息 | 空 | Agent 观测累积 |
| 短期 / 长期记忆 | 空 | Agent 运行中写入 |
| 场景剧本 | 骨架 | Agent 实战后补全 |
