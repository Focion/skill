# 身份模型架构

本文说明生成物的结构：20 个文件各管什么、为什么切成这样、文件之间靠什么对齐。
**生成物是一份数据模型**，交付给身份 Agent 作为蓝本；它不含 Agent 的行为指令——
行为由 `IdentityCompiler` 编译时注入（DESIGN §4）。

---

## 1. 第一原则：一个身份不是一份大 prompt

v1.0 是 9 个维度挤在一份 YAML 里。把现在的 19 个维度照那个路子写下去只有一个好处：
读起来是一整个人。代价有四条：

| 代价 | 具体后果 |
|---|---|
| 无法按需加载 | 问「你几点睡」也要把家庭史、目标、阴影一起读进上下文 |
| 无法回写 | Agent 成长要改一处，得整文件重写，注释与未识别字段全丢 |
| 无法分级校验 | 「技能必须留空」这类断言没有文件边界可依附 |
| 无法版本化 | 一次 diff 全是噪声，code review 看不出改了什么 |

拆分后各文件的加载成本是可算的。在种子模板（注释最密的状态）上实测：
冷启动 6 文件合计约 5700 tokens，按需 14 文件合计约 8000 tokens、单文件最大约 2500 tokens（`scene_presets.yaml`）。
（这几个数随模板注释变动，改过模板就以 `validate.py` 报告里的实测值为准，不以本文为准。）
也就是说：**一次典型问答只需付冷启动 + 一两个按需文件**，而不是每轮付全部一万多 tokens。
这才是拆分的实际收益，不是「分开好看」。

拆分的刀口有两处：

1. **按维度**——`personal` / `psychology` / `academic` 是身份的不同侧面，各自被不同话题触发；
2. **按可写性**——`personal` / `academic` / `family` / `constraints` / `agent_protocol` / `psychology` 是设计态（`writable: false`），
   其余在运行期会被回写。`evolution.yaml` 是唯一高频回写的文件，所以它自成一份而不是塞进 psychology。

> 记忆（short_term / long_term）**不在这 20 个文件里**。记忆是运行时行为，由 Agent 经工具写入
> `role-session.db`。模板只管「我是谁」，记忆只管「我经历了什么」。

---

## 2. 20 文件总览

清单权威来源：`templates/manifest.yaml`（运行时契约）与 `data/consistency-rules.json`
（`files.base` 13 + `files.extended` 6 + manifest = 20）。表格顺序即 manifest 中的登记顺序。

| 文件 | 根键 | 管什么 | 加载 | writable | initial_state |
|---|---|---|---|---|---|
| `manifest.yaml` | `meta` / `files` | 文件契约与元信息，唯一入口 | 冷启动 | — | — |
| `personal.yaml` | `personal` | 姓名、年龄、籍贯、语言、词汇层级 | 冷启动 | false | filled |
| `constraints.yaml` | `constraints` | 全局 / 角色 / 实例三段约束与优先序 | 冷启动 | false | filled |
| `evolution.yaml` | `evolution` | 当前情绪、精力、信任度、衰减与成长规则 | 冷启动 | **true** | filled |
| `narrative_voice.yaml` | `narrative_voice` | 五种叙事模式 + 语言指纹 + 感官画像 | 冷启动 | true | filled |
| `agent_protocol.yaml` | `agent_protocol` | 其他 Agent 的 queries / actions / events | 冷启动 | false | filled |
| `psychology.yaml` | `psychology` | MBTI、大五、情绪、认知、价值观 | 按需 | false | filled |
| `health.yaml` | `health` | 身体、心理、作息与生活方式 | 按需 | true | filled |
| `academic.yaml` | `academic` | 学历、在读阶段、学校、成绩 | 按需 | false | filled |
| `skills.yaml` | `skills` | 硬技能、软技能、短板、元技能 | 按需 | true | **empty** |
| `social.yaml` | `social` | 社会地位、社交圈、社群与网络形象 | 按需 | true | **empty** |
| `relationships.yaml` | `relationships` | 具体关系条目与关系网概览 | 按需 | true | filled |
| `family.yaml` | `family` | 家庭结构、成员、经济、家族史 | 按需 | false | filled |
| `specialties.yaml` | `specialties` | 天赋、兴趣、未开发潜能 | 按需 | true | **empty** |
| `behavior.yaml` | `behavior` | 语气、15 类交互反应、敏感话题、习惯、应对 | 按需 | true | filled |
| `goals.yaml` | `goals` | 四档目标 + dream、want_vs_need、动机、恐惧 | 按需 | true | filled |
| `knowledge_boundaries.yaml` | `knowledge_boundaries` | 已知域 / 盲区 / 误区 / 待学 / 知识时效 | 按需 | true | filled |
| `shadow.yaml` | `shadow` | 压抑需求、否认特质、创伤、核心矛盾、嫉羡、羞耻 | 按需 | true | **empty** |
| `scene_presets.yaml` | `scene_presets` | 场景清单与行为覆盖、切换规则 | 按需 | true | filled |
| `daily_rhythm.yaml` | `daily_rhythm` | 时间上下文、典型日程、周节律、此刻状态 | 按需 | true | filled |

四个 `initial_state: empty` 的文件（skills / social / specialties / shadow）**即使在填充模式下也留空**，
理由与校验方式见 `fill-mode.md` 第 3 节、`consistency.md` 的 M04。
它们仍必须在磁盘上建出空壳文件——否则 `identity_read` 拿到的是「文件不存在」而不是「本人还没显露」。

---

## 3. 冷启动 6 文件与 token 预算

`priority: cold_start` 的 5 个文件加 `manifest.yaml` 共 6 个，**每轮都进 system prompt**。
这个集合由 `consistency-rules.json#files.cold_start` 钉死，M03 是 error 级：多一个就每轮多付一次常驻成本，
少一个则角色开口就没有依据。选它们的理由各不相同：

| 文件 | 为什么必须常驻 |
|---|---|
| `manifest.yaml` | 不读它就不知道还有哪些文件、什么条件下读 |
| `personal.yaml` | 一开口就要自称，姓名年龄不能按需 |
| `constraints.yaml` | 约束不可跳过；按需加载等于给了绕过的机会 |
| `evolution.yaml` | 情绪与信任度每轮都要读、也每轮都要写 |
| `narrative_voice.yaml` | 每句话的声音质感，不是某个话题下才需要 |
| `agent_protocol.yaml` | 别的 Agent 随时可能发起查询，协议要随时可答 |

预算写在 `consistency-rules.json#budgets`：冷启动合计 1600 tokens、单文件 1200 tokens。
`single_file_tokens` 只施加于冷启动文件——按需文件超线只是那一次问答多付一点，统计但不告警。
超出只产 **WARN（M15），不阻塞落地**——因为它是成本问题不是正确性问题，
而且注释密的模板本来就注定超（种子模板实测 5698 / 1600，manifest 1995、agent_protocol 1360 均超单文件线）。
处理办法在 `conventions.md` 第 7 节：模板注释是给人填的脚手架，填完可剥注释再压预算。

---

## 4. 按需加载的触发机制

manifest 里每条登记项都有 `load_trigger`，三个字段各有分工：

```yaml
  - path: "psychology.yaml"
    description: "MBTI、大五、情绪、认知、价值观"
    load_trigger:
      keywords: ["性格", "MBTI", "价值观", "情绪", "怎么看"]
      context: "问及性格、心理反应或价值判断"
      priority: "on_demand"
```

- `keywords`：字面命中，快而糙。M16 要求 on_demand 文件必须有；少于 3 个只是 WARN（命中面偏窄）。
- `context`：关键词没命中时的语义判断依据。缺了它 Agent 无从判断该不该读，M16 同样 WARN。
- `priority`：只有 `cold_start` / `on_demand` 两个合法值（M02，error 级）。

**新增文件必须登记进 `manifest.files`**，否则两件事同时发生：运行时永远读不到它，
`validate.py` 把它判为孤儿文件（M01，error）。反之，登记了但磁盘没有也是 error。
这条对扩展的意义是：manifest 是唯一的文件契约，新增维度的动作是「建文件 + 登记 + 补 root_keys」三件套，
只做前一件等于什么都没做。

DESIGN §25.4 还有一层：蓝本生成 Agent 的写路径白名单是**从 manifest 推导**的，不从模型输出推导。
所以「模型自己声明要新增一个文件」这条路是关着的——新增文件走 scaffold 阶段的类型目录。

---

## 5. 两个不进 manifest 的可选文件

`model_defaults.yaml` 与 `provenance.yaml` 在 `templates/` 里存在，但按设计**不进 `manifest.files`**
（见 manifest 末尾 `conventions.optional_unregistered`，以及 `consistency-rules.json#files.optional`）。
`validate.py` 见到它们只记 INFO，不判孤儿。

| 文件 | 内容 | 为什么不登记 |
|---|---|---|
| `model_defaults.yaml` | 对话/自省的 `modelId` 与 `thinkingLevel`、token 预算、采样参数、`realign_order` | 它是「用什么参数说话」，不是「是谁」，不参与编译 system prompt；由 DESIGN §4.4 的解析链消费 |
| `provenance.yaml` | 原始描述全文、`allocation` / `unallocated` / `seeds` / `confirmations` | 它是生成过程的留痕，运行期不加载；登记进 manifest 会让运行时每次都看见一份与身份无关的账本 |

`model_defaults.yaml` 值得跟蓝本一起版本化的原因：同一个身份换了 `thinkingLevel` 会明显换个人。
**推理档位在这里是人格参数，不只是成本参数**——给学生配和专家一样的深推理，
它会演成「装成学生的专家」（DESIGN §4.4）。解析链是：
运行时内置默认 → 蓝本 `model_defaults.yaml` → 名册 `defaults` → `create()` 入参 → 场景级临时覆盖，后者覆盖前者。

`provenance.yaml` 存在的唯一理由是 S10（描述逐条有落点）与 S11（没有编造）
无法由蓝本自身判断，必须留下原始描述与分配清单才能对账。

---

## 6. 文件间的引用关系

跨文件一致性靠少量字段互指维系。改其中任何一处，右列全部要回头核对。
标了规则号的由 `consistency.md` 对应条目负责检查。

| 上游字段 | 下游字段 | 关系 | 规则 |
|---|---|---|---|
| `personal.age` | `academic.education.stage` / `level` | 在读阶段与年龄按阶段年龄表对账 | M08 |
| `personal.age` | `personal.language.vocabulary_level` | 用词复杂度须与年龄相称 | 人工 |
| `personal.socioeconomic` | `family.finance.level` | 不得出现明显矛盾词 | M11 |
| `psychology.personality.mbti` | `behavior.interaction.*` | I/E、T/F 维度解释 15 类交互反应 | S01 |
| `psychology.personality.big_five` | `psychology.emotion` / `cognition` | 神经质高则情绪不稳、尽责性高则认知不随性 | S02 |
| `psychology.personality.attachment_style` | `relationships.entries[].dynamic` | 依恋类型是所有关系行为的底层模型 | S03 |
| `psychology.cognition.learning_style` | `narrative_voice.sensory.dominant_channel` | 主导感官与学习风格互相印证 | M12 |
| `psychology.values.dealbreakers` | `shadow.core_conflicts` | 底线不应与核心矛盾对撞 | S07 |
| `family.history.expectations` | `goals.want_vs_need.want` | 家庭期望常是 want 的来源 | S04 |
| `health.physical.sleep_pattern` | `evolution.state.energy_level` | 作息决定精力基线 | 人工 |
| `goals.want_vs_need.awareness` | `shadow.repressed_needs` | `unaware` 时应有对应压抑需求 | S05 |
| `goals.want_vs_need.want` | `goals.objectives.*` | 动机层与行为层须构成因果 | S04 |
| `behavior.language.*` | `scene_presets.scenes[].behavior_override` | 场景只写与常态不同的项，其余继承 | 人工 |
| `behavior.language.verbosity` | `model_defaults.reply_length_hint` | 回复长度倾向对齐 | 人工 |
| `behavior.language.emoji_usage` | `model_defaults.allow.emoji` | 表达手段受行为设定约束 | 人工 |
| `daily_rhythm.typical_day[].location` | `scene_presets.scenes` | 场景应覆盖日程里出现的主要地点 | 人工 |
| `social.status.social_mobility` | `scene_presets.transition_rules` | 影响公共场景中的自在程度 | 人工 |
| `relationships.entries[].id` | `relationships.network.strongest_bond`、`get_relationship` | 关系 id 是唯一连接键 | M09 |
| `evolution.state.trust_level` | `agent_protocol.actions[].effects`、`events.trust_milestone` | 协议按状态字段路径引用 | M09 |
| `knowledge_boundaries.known` / `unknown` / `misconceptions` | `agent_protocol` 的 `check_knowledge`、`ask_question` | 三分知识地图决定作答姿态 | M09 |
| `data/role-types.json` 的 `types.<角色>.role_constraints` | `constraints.role` | 角色约束由 scaffold 注入 | 人工 |

两条纪律：

- **`agent_protocol` 只写字段路径，不写文件名。** 写 `evolution.state.trust_level`，不写 `evolution.yaml` ——
  M09 会把 `*.yaml` 当引用解析，未注册的文件名直接判 error。
- **`behavior.sensitive_topics` 与 `psychology.values.dealbreakers` 不是一回事。**
  前者是「不想聊」（行为层的回避表现，M14 要求 ≥1 条），后者是「不能碰」（价值层的底线）。
  v2.0 之前 `sensitive_topics` 挂在 `psychology.values` 下，迁移旧蓝本时要挪位置；
  现在的权威位置只看 `templates/behavior.yaml`，M14 也只在那里数。

---

## 7. 与三支柱、与身份编译器的关系

身份模型是 Agent 世界模型三支柱之一：

- **Identity** ← 本技能：角色 Agent 是谁——人格、心理、能力、行为
- **Guideline**：组织规则是什么——制度、流程、约束（`manifest.meta.valid_scenes` 关联其准则模板 ID）
- **Facility**：设施 Agent 是什么——设施实体、服务能力、规则、资源（`generate-facility`）

设施模型按**变化速率**切层（profile / state / memory / scenarios），身份模型按**维度 + 可写性**切；
两者形态不同是刻意的，不要互相套用。但生成过程的形状相同：分配描述 → 定核心 → 逐文件展开 → 校验 → 修复。

本技能的产物处在 DESIGN §3 三步流水线的**第一步**，它与后两步的关系决定了几条硬约束：

1. **蓝本按角色类型立意，不按具体人立意。** scaffold 产出的目录名就是 `identity_id`
   （`id-<YYYYMMDD>-<role>-<后缀>`，如 `identities/id-20260904-teacher-lmt`）；
   归档进蓝本库时按 `<role>-<变体>` 重命名（DESIGN §3 的 `teacher-generic`）。
   两处命名都以角色类型为主语——姓名/年龄这类实例差异应尽量交给
   `agents.create({ overlay })` 或名册，把「李正国」焊进蓝本，第二个教师实例就无法复用它。
2. **蓝本永不被回写。** 运行期的成长只回写到 `agents/<agent_id>/identity/` 下的实例副本；
   要把成长固化成新蓝本，走 `exportAsBlueprint()`。所以本技能产物在运行期是只读的 git 资产。
3. **创建时会重跑校验，失败即拒绝创建。** `agents.create()` 用的是同一份
   `data/consistency-rules.json`，所以本技能的 `scripts/validate.py` 通过 ≈ 步骤 2 能加载
   （承诺见 DESIGN §25.6）。这是把生成放进同一个环里换来的东西。
4. **模型档位在 `create()` 时解析**，蓝本只提供一层默认值（第 5 节）。

哪些内容一律不推断（四个 `empty_by_design` 文件与观测类字段）见 `fill-mode.md` 第 3 节
——DESIGN §25.3 验收项里的 `neverInfer` 指的就是这条，本技能落地成
`consistency-rules.json#empty_by_design` 加 M04 断言（外加 manifest 里各自的 `initial_state: empty`），
不另设 `neverInfer` 这个名字。种子/填充两模式的差别见第 4 节，汇报的九项字段见第 6 节。
