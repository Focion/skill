---
name: generate-facility
description: >
  生成设施模型模板（多文件架构，按需加载）。输入 /generate-facility <设施类型> [自定义描述] 即可生成完整的设施模型目录。
  提供描述时进入填充模式——根据设施类型注入行业默认值，并将用户描述分配到对应文件。
  不提供描述时进入种子模式——生成空白模板骨架，由 Agent 后续填充。
  多文件架构让设施 Agent 按需加载：L0 常驻 MODEL.md 路由表，L1/L2 按触发信号加载对应 profile/state/scenarios 文件。
  支持 22 种设施类型（图书馆、体育馆、食堂、实验室、宿舍、游泳池、停车场、医务室、会议室、剧院、自习室、仓库、快递驿站、洗衣房、咖啡吧、母婴室、展厅、充电站、机房、打印服务、算力资源池），也支持自定义类型。
version: 2.0.0
author: null
tags:
  - facility
  - template
  - world-building
  - multi-agent
  - multi-file
  - on-demand-loading
---

## 概述

本技能生成**设施模型**——一个多文件目录，作为设施 Agent 的身份蓝本。这是世界模型三支柱之一：

- **Identity**（generate-identity）：角色 Agent 是谁——人格、心理、能力
- **Guideline**：组织规则是什么——制度、流程、约束
- **Facility** ← 本技能：设施 Agent 是什么——设施实体、服务能力、规则、资源

**本技能生成的是设施 Agent 的身份蓝本**。产出物经 `FacilityCompiler` 编译为 `FacilitySpec`，
用于创建 `FacilityAgent` 实例。设施 Agent 是独立 Agent，有自己的 observe session，
不主动发言，只响应查询和事件。

### 多文件架构

单文件 YAML 的问题：Agent 每次加载设施上下文必须全量读入，不管当前对话是否只需要"开放时间"或"容量信息"。

v2.0 将设施模型拆分为**按需加载的多文件架构**：

```
facilities/<type>-<name>/
├── MODEL.md                     # L0 常驻入口：路由表 + 硬约束速查 + 文件索引
├── manifest.yaml                # 文件契约：每个文件的路径、格式、层、可写性、更新方式
│
├── profile/                     # L1 设计态（YAML，慢变，人+生成器写）
│   ├── basic.yaml               #   基本信息：名称、位置、归属
│   ├── time.yaml                #   时间：开放时段、节假日、状态机
│   ├── capacity.yaml            #   容量：多级上限、分区、瓶颈资源
│   ├── rules.yaml               #   规则：准入、行为、执行矩阵
│   ├── services.yaml            #   服务：目录、前置条件、限制
│   ├── resources.yaml           #   资源：分类、库存、损耗
│   ├── protocol.yaml            #   交互协议：查询/操作/事件接口
│   ├── pricing.yaml             #   L2 计费：价格、押金、罚款、优惠
│   ├── staffing.yaml            #   L2 人员：角色、班次、自主权限
│   ├── usage.yaml               #   L2 使用信息：限制、观测规律
│   └── relations.yaml           #   L2 拓扑：邻居、替代设施、转介
│
├── state/                       # 运行时（JSON/JSONL，快变，Agent 写）
│   ├── live.json                #   即时状态：当前人数、可用资源、revision 乐观锁
│   ├── usage.jsonl              #   使用流水（仅追加）
│   ├── usage-digest.json        #   使用统计摘要
│   ├── incidents.jsonl          #   事件流水（仅追加）
│   └── maintenance.jsonl        #   维护记录（仅追加）
│
├── memory/                      # 两级记忆
│   ├── POLICY.md                #   记忆策略：晋升条件、衰减、冲突裁决
│   ├── short-term.jsonl         #   短期记忆（仅追加，尾部窗口读取）
│   └── long-term/               #   长期记忆（按主题文件，从短期晋升）
│       └── INDEX.md
│
├── scenarios/                   # 场景剧本（10 轴推导，按需加载）
│   ├── INDEX.md                 #   剧本索引 + 覆盖状态
│   ├── _TEMPLATE.md             #   九节剧本骨架
│   ├── A1_routine_service.md    #   常规服务
│   ├── A2_peak_load.md          #   高峰满载
│   ├── A4_rule_violation.md     #   违规冲突
│   ├── A6_emergency.md          #   应急疏散
│   ├── A9_out_of_scope.md       #   越界请求
│   └── ...                      #   按设施特征选配的其余轴
│
└── CHANGELOG.md                 # 变更日志
```

### 按需加载机制

`MODEL.md`（L0）是唯一常驻文件。Agent 根据当前任务匹配路由表中的触发信号，只加载对应文件：

| 用户在问 | 加载文件 |
|---------|---------|
| 这是什么设施、在哪、归谁管 | `profile/basic.yaml` |
| 现在开不开、几点关门 | `profile/time.yaml` + `state/live.json` |
| 还能进多少人、满了没 | `profile/capacity.yaml` + `state/live.json` |
| 能不能进、能不能做某事 | `profile/rules.yaml` |
| 提供什么服务、怎么办 | `profile/services.yaml` |
| 多少钱、押金、逾期罚多少 | `profile/pricing.yaml` |
| 出事了、坏了、有人违规 | `scenarios/INDEX.md` → 命中剧本 |
| 刚才发生了什么 | `memory/short-term.jsonl`（读尾部窗口） |

L0 预算 ≤ 1800 tokens，L1 单文件 ≤ 2500 tokens，L2 单文件 ≤ 4000 tokens。

---

## 使用方式

```
/generate-facility <设施类型> [自定义描述]
```

示例：

- `/generate-facility 图书馆` → 种子模式：生成空白图书馆模型
- `/generate-facility 图书馆 藏书5万册，借书需押金50元，每人最多借3本，逾期每天1元，不能带宠物，容纳200人` → 填充模式
- `/generate-facility 体育馆 篮球场4个，器材可租借，每小时30元，必须穿运动鞋` → 填充模式
- `/generate-facility 自习室 24小时开放，需预约座位，每次最长4小时，保持安静` → 自定义类型
- `/generate-facility 算力资源池 100张GPU，项目授权使用，按用量内部划账` → 虚拟资源

---

## 执行流程

### 1. 解析输入

从 args 提取：
- **facility_type**：第一个词，查 `data/types.json` 的 aliases 解析为英文 key
- **description**：剩余文本，可能为空

### 2. 判断生成模式

- **有描述** → **填充模式 (filled)**：按 `references/fill-mode.md` 的规则，将描述分配到对应文件，并注入 `references/facility-types.md` 的行业默认值
- **无描述** → **种子模式 (seed)**：生成空白模板骨架，所有值字段留空，保留 `@fill` 标记

### 3. 调用 scaffold.py 生成文件

```bash
python3 scripts/scaffold.py \
  --type <resolved_type> \
  --id <facility_id> \
  --name <facility_name> \
  --out <output_dir> \
  --mode seed|filled \
  [--minimal] [--force]
```

`scaffold.py` 做确定性操作：
- 解析类型（查 aliases → 命中 `data/types.json` 或回落 `custom`）
- 复制 `templates/` 下的全部文件，替换 `{{VARIABLES}}`
- 按类型元数据决定启用/裁剪哪些可选层（resources/pricing/staffing）
- 按类型元数据 + 通用五轴生成场景剧本文件
- 从 `manifest.yaml` 中移除未启用层的注册项
- 注入默认分区到 `profile/capacity.yaml`

### 4. 填充模式：注入内容

如果是填充模式，在 scaffold 生成的文件基础上：

1. 按 `references/fill-mode.md` 第 1 节的分配表，将用户描述的每条信息写入对应文件的对应字段
2. 按 `references/fill-mode.md` 第 2 节的推断规则，设置 severity、enforcement 等派生字段
3. 按 `references/facility-types.md` 的类型知识库，注入行业默认值（标 `source: seed`）
4. 用户描述与默认值冲突时，用户描述优先
5. 用户明确否定某项时（如"不用押金"），删除该默认值而非并存
6. 用户描述涉及的情境（如"逾期每天 1 元"），在对应场景剧本中填入已知事实（第 2、3 节），但**不编造第 4 节决策取舍**
7. 类型未命中时（`type: custom`），只注入通用骨架，不套用最像类型的默认值

### 5. 场景推导

按 `references/scenario-derivation.md` 的方法：

- **通用五轴**（A1/A2/A4/A6/A9）对任何设施都必须有剧本
- **特征剧本**按设施特征选配（如：有借还行为 → A3；有预约机制 → A2/A4；涉及人身风险 → A6/P0）
- 首次生成只铺骨架（九节标题 + `@fill`），不编造正文
- `scenarios/INDEX.md` 列出全部剧本，未覆盖的轴显式标记为「建议补充」

### 6. 运行校验

```bash
python3 scripts/validate.py <output_dir> [--strict]
```

校验项（详见 `references/fill-mode.md` 第 4 节）：
- 机器可查：引用完整性、容量自洽、格式合法、manifest 与磁盘一致、场景 INDEX 对称、token 预算
- 需人工判断：服务时段 ⊆ 开放时间、描述逐条落点、无编造值、硬约束速查可追溯

### 7. 汇报

按 `references/fill-mode.md` 第 5 节的格式向用户汇报：
1. 输出目录与文件数
2. 设施类型、模式、启用/裁剪的可选层
3. 描述分配明细：每条描述 → 哪个文件的哪个字段
4. 注入的行业默认值（`source: seed` 标记）
5. 仍为空的部分及原因
6. 校验结果（ERROR/WARN 数、各层完整度）
7. 建议的下一步

---

## 种子模式（无描述）

生成完整的空白模板骨架：
- 所有值字段留空，保留 `@fill(human|agent|generator)` 标记
- `profile/time.yaml` 填入完整状态机定义（6 状态 + 转移规则，这是固定结构）
- `profile/protocol.yaml` 填入标准查询/操作/事件接口骨架
- 通用安全规则（消防、急救联系方式）预填
- `scenarios/` 下生成 8–10 个骨架剧本
- 空 ≠ 错：`@fill` 标记的字段是待补，不是遗漏

---

## 参考文件路由

本技能需要读取以下参考文件，按需加载：

| 文件 | 何时读 | 内容 |
|------|-------|------|
| `data/types.json` | 始终（scaffold.py 读取） | 22 种类型的元数据、中文别名、分区/场景配置 |
| `references/facility-types.md` | 填充模式 | 各类型的行业默认值（时间、准入、规则、服务、资源、计费、风险） |
| `references/fill-mode.md` | 填充模式 | 描述→字段分配表、severity 推断、自检清单、汇报格式 |
| `references/scenario-derivation.md` | 填充模式 | 10 轴推导方法、特征→轴映射、九节剧本结构、优先级 |
| `references/conventions.md` | 始终 | 格式选型、`@fill` 标记、来源标注、命名约定、写入方式、隐私规则 |
| `references/architecture.md` | 需要理解设计意图时 | 架构原则、层映射、关联键、容量模型、记忆管道 |

---

## 关键参考

### 格式选型

| 格式 | 用在 | 为什么 |
|------|------|-------|
| **YAML** | `profile/**` | 需要注释解释字段语义，需要人手改，结构嵌套深 |
| **JSON** | `state/live.json`、`state/usage-digest.json` | 机器整体覆写，无需注释，解析零歧义 |
| **JSONL** | `state/*.jsonl`、`memory/short-term.jsonl` | 仅追加事件流：O(1) append，读尾部窗口 |
| **Markdown** | `MODEL.md`、`memory/POLICY.md`、`memory/long-term/**`、`scenarios/**` | 内容是叙述、判断、流程 |

### 来源标注

被推断的值需标注来源，否则下游无法区分事实与猜测：

```yaml
source: seed        # 生成器按设施类型预置的行业默认值，未经确认
source: declared    # 人明确声明或有公告依据
source: observed    # 从 state/*.jsonl 统计出来
source: inferred    # 由其他字段推断，未经验证
```

### 首次生成的状态

| 层 | 首次生成状态 | 补充责任 |
|---|------------|---------|
| 基本信息 / 时间 / 容量 | 部分预填 | 人确认 |
| 服务 / 规则 / 资源 | 类型默认值 | 人校订 |
| 使用信息 | 空 | Agent 观测累积 |
| 短期 / 长期记忆 | 空 | Agent 运行中写入 |
| 场景剧本 | 骨架 | Agent 实战后补全 |

---

## 版本历史

### v2.0.0（当前）

从 v1.0 的单文件 14 维度 YAML 重构为多文件按需加载架构：

- **L0 路由入口**：`MODEL.md` 常驻，≤ 1800 tokens
- **11 个 profile 文件**：按触发信号独立加载（YAML + 注释）
- **5 个 state 文件**：运行时状态，JSON/JSONL，Agent 写入
- **两级记忆**：短期（JSONL 追加）+ 长期（Markdown 主题文件，按晋升条件从短期整合）
- **10 轴场景推导**：通用五轴 + 按设施特征选配，九节剧本结构
- **22 种设施类型**：含虚拟类型（打印服务、算力资源池）
- **格式按用途选型**：YAML/JSON/JSONL/Markdown 各有明确适用面
- **确定性脚本**：`scaffold.py`（生成）+ `validate.py`（校验），无第三方依赖

### v1.0.0

单文件 14 维度 YAML，全量加载。已废弃。