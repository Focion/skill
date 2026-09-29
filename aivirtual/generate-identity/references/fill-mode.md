# 填充模式

用户给了描述时，把描述里的每条信息分配到正确的文件与字段，再按角色类型补齐种子默认值。
两条核心纪律：**描述里没有的不要编**；**四项核心设定先定，其余文件后展开**（第 4 节）。

---

## 1. 描述 → 文件/字段 分配表

按关键词命中，命中多处时全部写、不要挑一个了事——「家里管得紧」同时落 `family.history.expectations`、
`psychology.personality.attachment_style`、`goals.want_vs_need.want`、`behavior.interaction.with_authority`。

**personal.yaml**

| 描述特征 | 落到 | 示例 |
|---|---|---|
| 岁、多大、几年级、生于 | `personal.age` / `birthday` | 「17 岁」→ `age: 17`，并连带 `academic.education.stage` |
| 叫、名字、小名、外号 | `personal.name.full` / `nickname` / `alias` | 「大家叫他老陈」→ `nickname` |
| 男女；老家、来自、常驻；已婚、有信仰 | `personal.gender` / `region` / `hometown` / `marital_status` / `religion` | 「山村手艺人」→ `hometown` |
| 方言、口音、双语；说话孩子气 / 用词讲究 | `personal.language.dialect` / `primary` / `secondary` / `vocabulary_level` | 「英语能读文献」→ `secondary: ["英语-中级"]`；词汇层级与年龄相称（第 2 节） |
| 戴眼镜、瘦高、手上有疤 | `personal.appearance.features` / `build` / `height_cm` | 「黑框眼镜」→ `features`；不写与开口方式无关的外貌台账 |
| 家里条件、出身 | `personal.socioeconomic` + `family.finance.level` | 两处措辞不得互相矛盾（M11） |

**psychology.yaml**

| 描述特征 | 落到 | 示例 |
|---|---|---|
| 内向、话少、慢热、爱独处 | `personality.mbti` 取 I + `big_five.extraversion` 低 + `behavior.interaction.with_strangers` | 「性格随和但话少」→ `extraversion: 0.35` |
| 随和、不爱争；自律、认真、爱拖 | `big_five.agreeableness` / `conscientiousness` + `behavior.language.tone` / `habits.procrastination` | 「学霸」→ `conscientiousness: 0.8` |
| 敏感、容易焦虑、想太多；好奇、点子多 | `big_five.neuroticism` / `openness` + `emotion.baseline` / `stability` | → `baseline: anxious`、`stability: volatile` |
| 一急就吵 / 就躲 / 就僵住 / 就讨好 | `emotion.stress_response`（fight / flight / freeze / fawn） | 「一被质疑就闭嘴」→ `freeze` |
| 高兴的事、受不了的事；藏不藏心事 | `emotion.triggers.positive` / `negative`、`emotional_expression` | 「解出难题就来劲」→ `triggers.positive` |
| 逻辑型、凭感觉、爱动手；谨慎 / 爱冒险 | `cognition.thinking_style` / `learning_style` / `decision_making` / `risk_tolerance` | `learning_style` 须与 `narrative_voice.sensory.dominant_channel` 对上（M12） |
| 认死理、有原则、看不起 X；自卑、要强 | `values.core` / `dealbreakers` / `moral_framework` / `worldview`、`personality.self_esteem` / `self_image` / `temperament` | 「只信手上的活」→ `values.core`；「觉得自己不行」→ `self_esteem: low` |
| 认知偏差（≥2 条，M14） | `cognition.cognitive_biases` / `attention_span` / `intelligence_type` | 由人格推，不由描述直给 |

**academic.yaml**

| 描述特征 | 落到 | 示例 |
|---|---|---|
| 高二、大三、研一、在读 | `education.stage`（+ `level` 按 stage 首字推） | 「17 岁高二」→ `stage: 高二`、`level: high`（M08）；不在读时只填 `level`、`stage` 留空 |
| 重点中学、国际学校、职校；专业、系 | `education.school` / `school_type` / `major` / `minor` / `department` | 「物理方向」→ `major: 物理` |
| 学霸、成绩好、吊车尾；偏科、跟不上某科 | `performance.overall` / `gpa_or_rank` / `strengths` / `weaknesses` / `challenges` | 「学习很好」→ `overall: excellent`；「文科记不住」→ `weaknesses` |
| 竞赛、获奖、论文；班干部、社团 | `performance.achievements`、`status.student_role` / `extracurricular` | 「带过竞赛」→ `achievements` |
| 休学、退学、已毕业、在职读；跟老师 / 同学的关系 | `status.enrollment` / `relationship_with_teachers` / `relationship_with_peers` | → `graduated` / `dropped_out`；具体某位老师另建 `relationships.entries` |

**family.yaml**

| 描述特征 | 落到 | 示例 |
|---|---|---|
| 家里管得紧、期望高、要求考上 | `history.expectations` | 连带 `goals.want_vs_need.want`（S04）与 `attachment_style` |
| 单亲、离异、跟爷奶长大、重组；几口人；家里和睦 / 冷淡 / 常吵 | `overview.structure` / `size` / `dynamics` / `atmosphere` / `core_influence` | → `single_parent` + `dynamics: conflicted` |
| 父母做什么的、学历；跟父亲不亲 | `members[]` 的 `occupation` / `education` / `relationship_quality` / `influence` / `living_together` | 「父亲是工人，话少」→ 一条 `members` |
| 家里穷 / 宽裕 / 一般 | `finance.level` / `stability` / `financial_stress` / `support` | 「条件一般」→ `moderate` |
| 搬过家、出过变故；家风、家里信奉 | `history.major_events` / `family_values` / `traditions` | — |

**health.yaml / relationships.yaml**

| 描述特征 | 落到 | 示例 |
|---|---|---|
| 熬夜、失眠、早睡早起、睡不够 | `health.physical.sleep_pattern` / `diet` | 连带 `evolution.state.energy_level`（第 2 节） |
| 体弱、近视、过敏、慢病 | `physical.overall` / `chronic_conditions` / `allergies` / `disabilities` / `medications` | 只写会影响语气与行为的，不做病历 |
| 爱运动 / 不动；抽烟、喝酒、常刷手机 | `physical.fitness_level`、`lifestyle.exercise` / `smoking` / `drinking` / `screen_time` / `hobbies_active` | 「每天打球」→ `hobbies_active` |
| 情绪低落、看过心理医生、靠 X 缓解 | `mental.overall` / `therapy_experience` / `coping_mechanisms` / `self_care_routine` | → `mild_concerns` |
| 有个好朋友、跟某老师亲、有对象 | `relationships.entries[]` 的 `id`/`role`/`category`/`strength`/`closeness`/`frequency`/`dynamic` | 「最好的朋友是同桌」→ 一条 entry + `network.strongest_bond` 指其 id（M09） |
| 独来独往、没什么朋友；闹过矛盾、断了联系 | `network.core_size` / `loneliest_aspect` / `social_satisfaction`、`entries[].conflict_style` / `status` | → `social_satisfaction: low`、`status: ended` |

**goals.yaml**

| 描述特征 | 落到 | 示例 |
|---|---|---|
| 这周要、今年想、毕业后、这辈子想 | `objectives.immediate` / `short_term` / `medium_term` / `long_term` / `dream` | 各档时间窗 0–3 / ≤12 / 12–36 / 36–120 月（M13）；`dream` 不受窗约束 |
| 为父母 / 为自己 / 不想输；累了、想放弃 | `motivation.type` / `intrinsic` / `extrinsic` / `current_level` | 「怕让家里失望」→ 外驱为主；「想放弃」→ `current_level: burnt_out` + `evolution.state.energy_level` 调低 |
| 怕、担心、最怕 | `fears[]` 的 `fear`/`intensity`/`origin`/`coping` | 「怕考不上」（≥1 条，M14） |
| 卡在、不顺、被拖住；想成为、在学着 | `obstacles[]` 的 `obstacle`/`type`/`plan`、`growth.direction` / `next_milestone` / `mentor_or_model` | → `type: internal` / `external` / `systemic` |
| 表面要的 vs 其实缺的 | `want_vs_need.want`/`need`/`tension`/`awareness` | 家庭期望常是 want 的来源（S04） |

**behavior.yaml / narrative_voice.yaml**

| 描述特征 | 落到 | 示例 |
|---|---|---|
| 温和 / 冷 / 热情 / 爱挖苦；话多、惜字如金 | `behavior.language.tone` / `verbosity` | 「严厉但护学生」→ `tone: cool` + `interaction` 各项 |
| 客气、随意、看人下菜；换场合换腔调 | `language.formality` / `code_switching` | → `adaptive` |
| 口头禅、老说某句；从不说某类话；嗯啊之类 | `language.catchphrases` / `avoids_saying` / `filler_words` | 「这个可以用…来理解」 |
| 冷幽默、爱自嘲、不开玩笑；不发表情 | `language.humor_style` / `emoji_usage` | → `dry`、`emoji_usage: never` |
| 对领导 / 同辈 / 陌生人 / 下属怎么样；被夸、被批、听不懂、无聊、激动时 | `interaction` 的 `with_authority` / `with_peers` / `with_strangers` / `when_praised` / `when_criticized` / `when_confused` 等 15 项 | 措辞须能被 MBTI 的 I/E、T/F 解释（S01）；15 类逐项填，别只填三项 |
| 一提 X 就绕开、不愿谈 | `sensitive_topics[]` 的 `topic`/`why`/`deflection` | ≥1 条（M14）；与 `psychology.values.dealbreakers` 分工见 `architecture.md` 第 6 节 |
| 桌子乱、总迟到；每天固定做某事、工作方式 | `habits.organization` / `punctuality` / `procrastination` / `daily` / `work_style` | 「不爱写材料」→ `work_style` |
| 压力大就、失败后、不爱求人、决定多了就烦 | `coping.under_pressure` / `after_failure` / `seeking_help` / `decision_fatigue` | → `seeking_help: reluctant` |
| 短句 / 长句、爱用某类比喻、少用数字 | `narrative_voice.fingerprint` 的 `metaphor_domains` / `abstraction_level` / `punctuation_style` / `number_style` | 「用物理模型类比」→ `metaphor_domains: [物理]` |
| 爱动手 / 听讲 / 看图记东西；注意细节还是整体 | `narrative_voice.sensory.dominant_channel` / `noticing_pattern` / `body_awareness` | 须与 `psychology.cognition.learning_style` 有交集（M12） |
| 内心话多、爱复盘、爱打比方；激动时脸红 | `narrative_voice.default_mode` + `modes.inner_monologue` / `reflective` / `explanatory` / `emotional` | 五模式共享同一 `fingerprint`（S06） |

**knowledge_boundaries.yaml / daily_rhythm.yaml / scene_presets.yaml / evolution.yaml / constraints.yaml / agent_protocol.yaml**

| 描述特征 | 落到 | 示例 |
|---|---|---|
| 懂 X、专业是 X、看过很多 X | `knowledge_boundaries.known.domains[]` 的 `domain`/`level`/`acquired_via`/`confidence` | 「物理竞赛水平」→ `level: proficient`、`acquired_via: formal_education` |
| 不懂 X、没接触过；想学 X | `unknown.domains[]` 的 `awareness` / `attitude`、`learning_queue[]` | 「不碰新技术」→ `attitude: indifferent` |
| 老观念、以为、还按老办法；信息停在某年 | `misconceptions[]` 的 `what_they_think`/`what_is_true`/`origin`、`temporal_context.knowledge_cutoff` / `outdated_areas` | → `origin: outdated_education` |
| 几点起几点睡、一天怎么过、周末干什么 | `daily_rhythm.typical_day[]` 的 `time`/`activity`/`location`/`availability`、`weekly_rhythm.weekday` / `weekend` / `special_days` | 与 `health.physical.sleep_pattern` 对齐 |
| 期末、开学、放假、季节；最近出了件事 | `daily_rhythm.temporal_context.is_exam_period` / `is_holiday` / `season` / `recent_event` | 近期事件会压住或抬高情绪基线；`current_*` 三项由运行期刷新（第 3 节） |
| 在课堂 / 家里 / 朋友面前不一样 | `scene_presets.scenes[]` 的 `behavior_override` / `emotional_tendency` / `role_in_scene` | 只写与常态不同的项，其余继承 `behavior` |
| 怕上台、人多就紧张、独处才自在 | `scenes[].comfort_level` + `behavior.interaction.in_group` / `alone` | → `comfort_level: anxious` |
| 现在心情；慢热、熟了才敞开；什么事会让他变 | `evolution.state.current_mood` / `mood_intensity` / `trust_level`、`growth_rules[]` | 数值 0.0–1.0（M06）；`trust_level` 默认 0.3，无依据不改 |
| 职业身份（老师、医生、律师…） | `constraints.role` —— **由 scaffold 按 `data/role-types.json` 注入，不手写** | 见第 2 节 |
| 这个角色额外不能做的事 | `constraints.instance[]` 的 `rule`/`reason`/`severity` | `severity` 仅 `hard`/`soft`（M07） |
| 别的 Agent 需要能查它的什么 | `agent_protocol.queries` / `actions` | 只写字段路径不写文件名；扩展时照骨架加，别改现有 id |

**四个 `empty_by_design` 文件：描述命中了也不写进去**

| 描述特征 | 不落 | 改落到 |
|---|---|---|
| 精通、会做、技能等级、几年经验 | `skills.yaml` | `academic.performance.strengths`、`knowledge_boundaries.known.domains` |
| 人脉广、圈子、社会地位、名声 | `social.yaml` | `personal.socioeconomic`、`relationships.entries` / `network` |
| 天赋、钢琴十级、爱好、有潜力 | `specialties.yaml` | `health.lifestyle.hobbies_active`、`academic.performance.achievements` |
| 创伤、说不出口的、其实很想 | `shadow.yaml` | `goals.fears`、`goals.want_vs_need.awareness`、`behavior.sensitive_topics` |

---

## 2. 推断规则

推断值必须标来源（`inferred` / `seed`，标法见 `conventions.md`）。**年龄是最强的推断源**，一处决定三处：

| 由 `personal.age` 推 | 依据 | 例 |
|---|---|---|
| `academic.education.stage` / `level` | `consistency-rules.json#tables.stage_to_age`（含 ±1 岁容差）与 `stage_to_level`；不在读时改用 `level_min_age` 只校验下限 | 17 岁 → 高二/高三，不可能是初中（M08 error） |
| `personal.language.vocabulary_level` | 分档：≤12 岁具体名词为主、少用抽象词；13–18 岁开始用学科术语但滥用流行语；19–25 岁术语准确、句式变长；26+ 依职业分化 | 10 岁写「元认知」就破了 |
| `meta.extends` 分档 | 由 `scaffold.py --age` 按 `data/role-types.json` 定，人不手写；分档表见 `role-types.md` | 17 岁学生 → `high_school_student` |

**MBTI 与 big_five 必须互相自洽**（S01/S02 的常见破绽处）。四个字母各对一维，`neuroticism` 不由 MBTI 决定：

| 字母 | big_five 取值 | 反向也成立 |
|---|---|---|
| I / E | `extraversion` ≤0.45 / ≥0.55 | 定了 `extraversion: 0.3` 就不能写 ENFP |
| N / S | `openness` ≥0.6 / ≤0.45 | S 型配 `cognition.thinking_style: practical` |
| T / F | `agreeableness` ≤0.5 / ≥0.6 | F 型配 `emotion.empathy_level: high` |
| J / P | `conscientiousness` ≥0.6 / ≤0.45 | J 型不能配 `habits.procrastination: frequent` |
| （不对应） | `neuroticism` 由描述里的情绪词定 | 「敏感易焦虑」→ 高；此时 `emotion.baseline` 不能写「稳定平和」 |

| 其余推断 | 依据 |
|---|---|
| 家庭结构 → `attachment_style` | 和睦完整 → `secure`；管得紧、成绩换认可 → `anxious`；情感缺位、留守、父母忙 → `avoidant`；家庭冲突加反复无常 → `fearful_avoidant`。定完回头核对每条 `relationships.entries[].dynamic`（S03） |
| `health.physical.sleep_pattern` → `evolution.state.energy_level` | 规律 7–8h → 0.7（模板默认）；常熬夜、睡 5–6h → 0.4–0.5，且 `emotion.stability` 下调一档；失眠 → ≤0.4 |
| 成绩词、经济词 → 枚举值 | `performance.overall` 只能取五个枚举值（别写「很好」）；`finance.level` 与 `personal.socioeconomic` 不得命中 `tables.finance_vs_socioeconomic` 的矛盾词表（M07 / M11） |
| `learning_style` ↔ `dominant_channel`；目标四档 ↔ 时间表达 | 前者按 `tables.channel_synonyms` 取交集（「爱做实验」→ `kinesthetic`，M12）；后者落在 `tables.goal_horizons.windows` 各档窗口内且四档文本不重复（M13） |
| 情绪基线与 `shadow` | `shadow` 按设计为空，所以**不要把「压抑」「创伤后遗」写进 `emotion.baseline` 当替代品**；`want_vs_need.awareness: unaware` 时 `need` 要写成外部观察者视角，不能写得像角色自己已想通（S05 留待运行期） |
| 职业/身份词 → `constraints.role` | **不手写**。scaffold 按 `data/role-types.json` 的 `types.<角色>.role_constraints` 注入，回落 `custom` 时该段为空，只留 `constraints.global`；不要拿「最像」的角色套 |
| 立体度 | 认知偏差 ≥2、恐惧 ≥1、敏感话题 ≥1（M14 查数量，S12 查是否与人格相称）。`skills.weak_areas` 那条最低量在授权期不适用——该文件按设计为空 |

跨文件引用关系的全表在 `architecture.md` 第 6 节，改任一上游字段就照它回头核对，本节不重复。

---

## 3. 不推断的

**四个 `empty_by_design` 文件：`skills.yaml` / `social.yaml` / `specialties.yaml` / `shadow.yaml`
即使在填充模式下也留空。** 描述里明说了「学霸」「精通物理」也不写进 `skills.yaml`——
它落 `academic` 与 `knowledge_boundaries`（第 1 节末表）。

理由是**编造出来会成为错误依据**：这四类内容会被后续每一次检索、自省与协议查询当成事实，
而它们恰好最容易被对话当场戳破。预设「精通 X」，对方一追问就把整个身份一起否掉；预设一段创伤，
角色一开口就在表演创伤；预设「人脉广」，会和之后每一次具体交往对不上——它们只有**被交互揭示**才可信。
落地不靠 prompt 自觉：`validate.py` **主动断言这四个文件为空**（M04，**ERROR** 级），填了就是错。
但空壳文件必须建在磁盘上并登记进 manifest，否则 `identity_read` 拿到的是「文件不存在」而不是「本人还没显露」。

**同样不推断的观测类内容**（必须来自真实运行）：

| 不填 | 为什么 |
|---|---|
| `evolution.state_history` | 情绪轨迹是运行期回写的账本，编出来的历史会被成长规则当作真实基线 |
| `daily_rhythm.temporal_context.current_date` / `current_time` / `day_of_week`、`daily_rhythm.current.*` | 由运行期按虚拟时间刷新、从 `typical_day` 推出；写死等于把角色钉在生成那一天 |
| `relationships.entries[].closeness` / `trust` 的漂移、`knowledge_boundaries.known.domains[].last_updated` | 初值可给，变化过程与知识时效是运行期事实 |
| 记忆（short_term / long_term） | 不在这 20 个文件里，由 Agent 经工具写入 `role-session.db` |

---

## 4. 种子模式 vs 填充模式

两种模式的差别只在「值从哪来」，文件数、结构、manifest 登记完全相同。

| | 种子模式 | 填充模式 |
|---|---|---|
| 值字段 | 留空（`""` / `[]`），保留 `@fill` 标记 | 按第 1 节分配表写入 + 第 2 节推断 |
| 核心设定四项 | **注定为空** | **必须最先固化** |
| 角色默认值 | `constraints.global` / `role`、`evolution.state`、`agent_protocol` 骨架预填 | 同样预填，另加角色种子值（标 `source: seed`） |
| 四个 empty 文件 | 空 | 仍然空 |

`required_fields` 八项里有四项就是核心设定锚点：`personal.name.full`、`personal.age`、
`psychology.personality.mbti`、`psychology.personality.attachment_style`；其余四项中
`evolution.state` 与 `agent_protocol.queries` 由 scaffold 预填，`big_five` 与 `narrative_voice.fingerprint` 展开时补。

种子模式下这四项为空**是设计不是缺陷**：模板本身不是某个人，姓名与年龄是实例差异，
按 `architecture.md` 第 7 节应交给 `agents.create({ overlay })` 或名册注入；`@fill` 标记就是「待补」的显式声明。

填充模式下必须**先定这四项再展开其余文件**，因为两种失败方式各堵一半：

- **一次性生成 20 个文件**：写到第 15 个文件时已经忘了第 3 个文件里的年龄，
  于是 `personal.age: 17` 配 `academic.education.stage: 初二`（M08 直接 error）。
- **逐个生成而不给共同锚点**：每个文件单独看都合理，合起来是另一个人——psychology 写了 INTP，
  behavior 却写「主动跟陌生人搭话」；家庭写「管得紧」，relationships 却写「对回应无所谓」。

之所以是这四项：姓名年龄锁住事实层（连带学历、词汇层级、`extends`），MBTI 与依恋类型锁住行为层
（连带 15 类交互反应与每条关系的 `dynamic`）。一致性靠**共享输入**——每个文件展开时输入里都要重复带上这四项。

---

## 5. 自检清单

左栏别手查（`scripts/validate.py` 查得比人准），右栏机器判不了、必须人或 LLM 过一遍。
每条的逐项解读与修复顺序在 `consistency.md`，本节只给指针。

**`scripts/validate.py` 能自动查（machine 级 M01–M17）**

| 查什么 | 规则 | 级别 |
|---|---|---|
| 文件契约：登记与磁盘一一对应、条目字段完整、冷启动集合恰好那 6 个 | M01–M03 | error |
| 四个 `empty_by_design` 文件真为空 | M04 | error |
| YAML 可解析、8 项必填字段非空；数值在 0.0–1.0；枚举取值合法 | M05–M07 | error |
| `personal.age` 与 `academic.education.stage` / `level` 对账 | M08 | error |
| `agent_protocol` 引用的字段路径在目标文件中存在 | M09 | error |
| `identity_id` 格式与各文件头部所属身份一致 | M10 | warn |
| 经济矛盾词（M11）、感官↔学习风格交集（M12）、目标四档的显式时间落在各档窗口内且四档文本不重复（M13，**不查跨度递增**） | M11–M13 | warn |
| 立体度最低数量：偏差 ≥2、恐惧 ≥1、敏感话题 ≥1（`skills.weak_areas` 那条属主文件按设计为空，代码跳过） | M14 | warn |
| 冷启动预算（M15）、on_demand 有 keywords（M16）、seed 标注（M17） | M15–M17 | warn / info |

**需人工 / LLM 判断（semantic 级 S01–S12）**

| 查什么 | 规则 | 级别 |
|---|---|---|
| MBTI 与 `behavior.interaction` 措辞一致 | S01 | warn |
| `big_five` 与 `psychology.emotion` / `cognition` 描述一致；五种叙事模式共享同一 fingerprint | S02 / S06 | warn |
| `attachment_style` 与每条 `relationships[].dynamic` 一致；`goals.want_vs_need.want` 与 `objectives` 构成因果 | S03 / S04 | warn |
| 描述逐条都有落点，漏了就补 | S10 | warn |
| 没有编造：数字、姓名、时间可追溯到描述或标了 `seed`；角色立体、缺点与人格相称不是凑数 | S11 / S12 | warn |
| `awareness` 与 `shadow`、`dealbreakers` 与 `core_conflicts`、`knowledge_boundaries` 与 `skills`、学历与技能等级 | S05 / S07 / S08 / S09 | info，**授权期挂起**（依赖按设计为空的文件，留待运行期回写后复核） |

S10 / S11 无法由蓝本自身判断，必须留下原始描述与分配清单才能对账——这是 `--with-provenance`
落地 `provenance.yaml` 的唯一理由。校验-修复循环最多 3 轮、每轮只改被点名的文件。

---

## 6. 汇报格式

按九项逐条输出，缺项比写错更糟——用户据此决定还要不要人工改。

| # | 字段 | 要写成什么样 |
|---|---|---|
| 1 | 输出目录与文件数 | 绝对路径 + `20 个文件`，并注明可选文件是否落地（`model_defaults.yaml` / `provenance.yaml`） |
| 2 | 角色类型与模式 | 解析后的英文 key + **是否回落 `custom`**（回落了必须明说，因为此时 `constraints.role` 为空）；模式 `seed` / `filled` |
| 3 | 核心设定四项 | 姓名、年龄、MBTI、依恋类型，四项并排列出——这是全部一致性的锚点 |
| 4 | **描述分配明细** | 用户说的每一条 → 落到了哪个文件的哪个字段。按描述片段分行，不要按文件分行（用户要核对的是自己那句话有没有被听懂） |
| 5 | **未落点的描述** | 显式列出。宁可承认没安置，也不要塞进某个字段后不提；空清单也要写「无」 |
| 6 | 注入的 seed 项 | 哪个文件的哪个字段、注入了什么值，提示**待确认**——它们没有描述依据，只是角色类型的行业常见值 |
| 7 | 仍为空的部分及原因 | **两类分开写**：①设计留空（四个 `empty_by_design` 文件、观测类字段）；②描述未覆盖（可补，等人给信息）。混在一起写等于让用户以为前者是漏的 |
| 8 | 校验结论 | ERROR / WARN 各多少条、修复了几轮；3 轮未收敛的原样列出，不要粉饰 |
| 9 | 需人工复核清单 | 未落点片段 + 语义级 S 类 WARN（S01–S04、S06、S10–S12）+ 超预算项（M15）+ 待确认的 seed 项 |

字段路径一律写全（`psychology.personality.mbti`），不写「心理文件里的性格」——用户要能直接拿去改文件。
身份属于某个组织时，附带提示设置 `manifest.meta.valid_scenes` 关联对应的准则模板 ID。
