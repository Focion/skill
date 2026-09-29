# 设施模型架构

本文说明生成物的结构：分几层、为什么这样切、层与层之间靠什么对齐。
**生成物是一个多文件的数据模型**，交付给设施 Agent 作为身份蓝本；它不包含 Agent 的行为指令（行为由 FacilityCompiler 编译时注入）。

---

## 1. 第一原则：按「变化速率 + 加载时机」切文件

单文件模型的问题不是长，而是**把不同变化速率的东西糊在一起**：开放时间一年改两次，实时人数一分钟改一次，
两者放在同一文件里，就必须每次全量读写。多文件的价值在这里，而不只是"分开好看"。

因此第一刀切在**可变性**上：

| | `profile/` 设计态 | `state/` 运行态 | `memory/` 记忆 | `scenarios/` 场景 |
|---|---|---|---|---|
| 变化速率 | 月/季 | 秒/分 | 小时/天 | 周/月 |
| 写入方 | 人、生成器 | 设施 Agent | 设施 Agent | 双方 |
| 更新方式 | 覆写 | 覆写 / 追加 | 追加 | 补丁 |
| 格式 | YAML（带注释） | JSON / JSONL | JSONL + Markdown | Markdown |
| 首次生成 | 有骨架，部分预填 | 初始值 | 空 | 骨架 |

第二刀切在**加载时机**上（L0–L3），由 `manifest.yaml` 声明、`MODEL.md` 路由。
判断标准很直接：**回答一个典型问题需要几个文件？** 若某文件几乎每次都要读 → L0/L1；
若只在特定主题下需要 → L2；若只在复盘时需要 → L3。

---

## 2. 层清单与文件映射

需求给出的 7 个核心维度全部保留，其中 3 个按可变性拆成了多个文件：

| 核心维度 | 落到哪些文件 | 说明 |
|---|---|---|
| 基本信息 | `profile/basic.yaml` | 身份、定位、位置、归属、联系、无障碍 |
| 时间信息 | `profile/time.yaml` + `state/live.json` | 定义（作息/时段语义/状态机）与当前时点分离 |
| 容量信息 | `profile/capacity.yaml` + `state/live.json` | 定义（上限/阈值/瓶颈/降级梯度）与当前占用分离 |
| 使用信息 | `profile/usage.yaml` + `state/usage.jsonl` + `state/usage-digest.json` | 规律 / 原始流水 / 聚合，三段式 |
| 短期记忆 | `memory/short-term.jsonl` | 滚动窗口，仅追加 |
| 长期记忆 | `memory/long-term/INDEX.md` + 主题文件 | 索引常读、正文按需 |
| 场景信息 | `scenarios/INDEX.md` + 剧本 | 按类型推导，见 `scenario-derivation.md` |

在此之上补充的层（补充理由在右列）：

| 补充层 | 文件 | 为什么必要 |
|---|---|---|
| 入口路由 | `MODEL.md` | 多文件模型若无路由表，设施 Agent 只能全读，按需加载就落空了 |
| 文件契约 | `manifest.yaml` | 声明格式、层级、可写性、预算，让校验与加载可自动化 |
| 服务能力 | `profile/services.yaml` | 「能被要求做什么」是设施的主干，`service.id` 是全模型的连接键 |
| 规则约束 | `profile/rules.yaml` | 准入与行为规则；含冲突裁决顺序，否则规则打架时无从判断 |
| 资源库存 | `profile/resources.yaml` | 容量的真实瓶颈通常是某项稀缺资源，不是面积 |
| 计费经济 | `profile/pricing.yaml` | 可选层；免费设施可整层删除 |
| 人员角色 | `profile/staffing.yaml` | 升级路径的落点，`rules.exemptions` 等引用它 |
| 关联拓扑 | `profile/relations.yaml` | 转介能力的来源：办不了时能说出去哪儿 |
| 交互协议 | `profile/protocol.yaml` | 其他 Agent 的调用契约（queries / actions / events / errors） |
| 事件与维护 | `state/incidents.jsonl`、`state/maintenance.jsonl` | 违规、故障、损耗的事实底账；长期记忆的证据来源 |
| 记忆规格 | `memory/POLICY.md` | 两级记忆的字段、保留期、晋升门槛、衰减规则 |
| 变更留痕 | `CHANGELOG.md` | 设计态改动可追溯，避免模型静默漂移 |

---

## 3. 连接键

跨文件一致性靠少量 id 维系。改名时必须全量替换，`scripts/validate.py` 会检查这些引用。

| 键 | 定义处 | 被引用处 |
|---|---|---|
| `service.id` | `services.catalog[].id` | `pricing.service_fees`、`capacity.zones.services_available`、`usage.usage_modes`、`protocol.actions`、`staffing.self_service` |
| `zone.id` | `capacity.zones[].id` | `services.available_in_zones`、`rules.scope`、`state/live.json#occupancy.by_zone` |
| `resource id` | `resources.categories[].id` 等 | `services.consumes`、`capacity.bottlenecks`、`resources.wear.by_category`、`state/live.json#resources` |
| `state id` | `time.state_machine.states[].id` | `services.available_in_states`、`state/live.json#facility_state`、`protocol.actions` |
| `role id` | `staffing.roles[].id` | `rules.by_role`、`rules.exemptions`、`resources.maintenance`、剧本升级路径 |
| `rule.id` | `rules.rules[].id` | `state/incidents.jsonl#rule_id`、剧本的处置依据 |
| `period id` | `time.semantic_periods[].id` | `services.available_periods`、`pricing.peak_surcharge`、`usage.observed_patterns` |
| `facility_id` | `basic.identity.id` | `relations.*`、其他设施模型的交叉引用 |

---

## 4. 两处容易做错的设计

### 4.1 容量不是一个数字

一个数字（"容纳 200 人"）无法支撑任何有用的判断。模型里容量是四件事：

1. **多档上限**：设计容量 / 安全容量（硬上限，通常等于消防核定）/ 舒适容量（体验拐点）
2. **阈值梯度**：占用率落在哪一档 → 照常、提示、限流、拒绝，各档带 hysteresis 防抖
3. **瓶颈资源**：先饱和的往往不是座位，而是某项稀缺资源；写清可观测信号才能提前预警
4. **降级梯度**：压力下按顺序牺牲什么、无论如何保住什么

缺第 4 项的后果最明显：模型只能表达"正常"和"全部拒绝"两种状态。

### 4.2 两级记忆之间是「整合」，不是「搬运」

短期记忆记**发生了什么**（具体、带时间戳、易失）；长期记忆记**因此我们知道了什么**（抽象、去时间化、稳定）。
直接把短期条目搬进长期，会得到一堆无法检索、迅速过期的碎片。

因此长期条目必须带三样东西，缺一不可：

- **成立条件**：在什么范围内成立，越界即不适用
- **证据**：≥2 处独立来源（短期记忆 id / incident event_id / digest 窗口）
- **复核周期**：到期需重新验证；设施会改造、会调价、会换人，过期的记忆比没有记忆更危险

完整规格在生成物的 `memory/POLICY.md`。

---

## 5. 首次生成的预期状态

首次生成后大量字段为空，这是设计意图，不是缺陷：

| 层 | 首次状态 | 谁来补 |
|---|---|---|
| 时间、协议、状态机 | 结构完整，多为固定骨架 | 人确认少量参数 |
| 基本、容量、规则、服务、资源 | 有骨架 + 类型默认值 | 人校订 |
| 使用信息 | **空** | 设施 Agent 运行中观测累积 |
| 短期、长期记忆 | **空** | 设施 Agent 运行中写入 |
| 场景剧本 | 骨架（9 节结构） | 设施 Agent 实战后补全正文 |

`@fill(who)` 注释标出了每个空位由谁在什么时候补。`scripts/validate.py` 统计完整度与未补项。
把"空"和"错"区分开是这套模型的一个要点：空是待补，错是引用不上——校验器对两者的处理不同。
