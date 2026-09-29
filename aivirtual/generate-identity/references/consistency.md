# 一致性规则解读

29 条规则的逐条说明：每条查什么、为什么这么定、报错了怎么修。
规则本体在 `../data/consistency-rules.json`，执行器是 `../scripts/validate.py`。
**本文以执行器的实际实现为准**——规则文本是意图的概述，代码判的往往更窄。

---

## 1. 两级分工：machine 与 semantic

| | machine（M01–M17） | semantic（S01–S12） |
|---|---|---|
| 谁判 | `scripts/validate.py` | 人或 LLM 复核 |
| 最高严重级 | error（M01–M09）→ 可阻塞落地 | warn（S05/S07/S08/S09 为 info） |
| 出现在输出的哪一段 | ERROR / WARN / INFO 三段 | 「代码判不了的」一段，只列条目与 `review_hint` |
| 影响退出码 | error → 1；`--strict` 下 warn → 1 | **永不影响**，`rep.review` 不参与结论 |

machine 一级判的是**可判定的形状**：文件在不在、枚举合不合法、数值在不在区间、
引用的路径解不解得开。semantic 一级判的是**是不是一个人**：MBTI 与措辞是否相称、
缺点是否与人格匹配。后者没有可执行判据，硬做只会得到假阳性，所以 `validate.py`
把它们原样列出交人工，永远不因它们判不通过（脚本开头的注释就是这个承诺）。

### 为什么规则是数据而不是代码

`consistency-rules.json` 里的 `files` / `root_keys` / `required_fields` / `enums` /
`ranges` / `tables` / `quality_minimums` / `budgets` / `identity_id_pattern` 都是查表，
`validate.py` 只是**它的一个执行器**——脚本里没有硬编码的字段清单，全部从 JSON 读。
理由有两条：

1. **避免分叉。** 运行时的 TS 校验器读同一份 JSON。若两边各写一遍枚举，
   加一个 MBTI 别名就要改两处，迟早出现「本技能通过、运行时拒绝」。
2. **落地即可加载。** `agents.create()` 复用同一份规则重跑校验，失败即拒绝创建。
   所以 **`python3 scripts/validate.py <dir>` 通过 ≈ 下游能加载**（DESIGN §25.6，
   另见 `./architecture.md` 第 7 节）。

推论：**改规则要改 JSON，不要改 Python**。往 `enums` 加一个值、往 `required_fields`
加一条路径，执行器与运行时同时生效；把判断写进 `validate.py` 只有本地生效。

---

## 2. M01–M17 逐条

每条 machine 规则在 JSON 里有一个 `check` 名，对应 `validate.py` 里的一段实现；
报告里的每行都以 `[规则 ID]` 开头，照 ID 回本节查即可。下表的「实际查什么」写的是
**代码真正判的范围**，与规则文本的差异已逐条标出——差异都是同一个方向：
代码判得比文本窄，因为只判可判定的部分。

规则自身声明的 `severity` 决定它落进 ERROR / WARN / INFO 哪一段（`Report.by`），
但**部分子检查绕过 severity 直接降级**，下表在相应位置注明。

### error 级（M01–M09）：不修则不落地

| 规则 | 实际查什么 | 为什么这么定 | 报错怎么修 |
|---|---|---|---|
| **M01** `manifest_disk_parity` | 三件事：①注册项的 `path` 在磁盘存在；②磁盘上的 `*.yaml`（除 manifest）都在注册表里，命中 `files.optional` 的只记 INFO；③`files.base` 13 + `files.extended` 6 全部注册 | manifest 是唯一文件契约，运行时的写路径白名单从它推导。孤儿文件运行期永远读不到，等于不存在 | 缺失→建文件；孤儿→补登记或删文件。注册了 `initial_state: empty` 也**必须建出空壳**，否则 `identity_read` 拿到「文件不存在」而不是「本人还没显露」，报错信息会直接点明这句 |
| **M02** `manifest_entry_schema` | 每个条目的 `description` / `initial_state` / `writable` / `format` 非空（`writable: false` 不算空）、`load_trigger.priority ∈ {cold_start, on_demand}`、`initial_state ∈ {filled, empty}`；`load_trigger` 不是映射也报 | 条目字段缺一项，运行时就少一个决策依据；`priority` 拼错会让文件静默永不加载 | 按 `templates/manifest.yaml` 的既有条目补齐四个字段与 `load_trigger` |
| **M03** `cold_start_set` | 把「所有 `priority: cold_start` 的注册项」与 `files.cold_start`（personal / constraints / evolution / narrative_voice / agent_protocol）做**集合相等**比较，多出与缺少分别报 | 冷启动集合每轮都进 system prompt：多一个是永久成本，少一个是角色开口没依据 | 只改 `load_trigger.priority`，不要改 JSON 里的集合。要新增常驻文件是架构决策，见 `./architecture.md` 第 3 节 |
| **M04** `empty_by_design` | **主动断言** `skills.yaml` / `social.yaml` / `specialties.yaml` / `shadow.yaml` 四个文件为空：manifest 里必须标 `initial_state: empty`，且 `flatten` 后**没有任何非空叶子**（会举出前 3 个路径）。反向也查：manifest 声明 `empty` 的其它文件同样必须真空 | 深层心理与技能须由交互揭示，授权期预设进去会成为错误依据。只写在 prompt 里靠不住，必须由校验断言 | 删掉这四个文件里填的值，只留结构与注释。填充模式**也不例外**——见 `./fill-mode.md` 第 3 节 |
| **M05** `required_fields` | `required_fields` 八条路径在**跨文件拼成的模型**上非空：`personal.name.full`、`personal.age`、`psychology.personality.mbti`、`psychology.personality.big_five`、`psychology.personality.attachment_style`、`narrative_voice.fingerprint`、`evolution.state`、`agent_protocol.queries` | 这八项是下游引用最密的锚点，缺任一项后面全套推导无从展开 | 补齐字段。**注意**：YAML 解析告警（缩进异常、无法解析的行）也挂在 M05 名下但只产 WARN；缺根键（如 `psychology.yaml` 里没有 `psychology:`）在文件非空时产 ERROR |
| **M06** `ranges` | `ranges` 十条路径落在 0.0–1.0：big_five 五项、`evolution.state` 的 mood_intensity / energy_level / trust_level / engagement、以及 **`evolution.mood_decay.intensity_decay_rate`**（规则文本没提但确实在查）。非数值（含 bool）也报 | 这些值直接进运行时算术，`0.8` 写成 `80` 会让衰减逻辑失控 | 改成 0–1 小数。空值会被跳过而不报——空的责任在 M05 |
| **M07** `enums` | `enums` 十一个标量字段 + `enum_fields_list_items` 三个列表项字段（`constraints.global[]` / `role[]` / `instance[].severity` 仅 `hard`/`soft`）。除 MBTI 16 型、attachment_style 4 型外还查 `self_esteem`、`academic.education.level` / `school_type`、`academic.performance.overall`、`family.finance.level` / `stability` / `financial_stress`、`narrative_voice.sensory.dominant_channel`、`evolution.mood_decay.baseline_restoration` | 枚举是运行时分支的输入，自由文本会让分支落空 | 照报错里列出的合法值改。空值跳过 |
| **M08** `age_vs_education` | `personal.age`（字符串数字会先转 int）分两路：**stage 非空**时按 `tables.stage_to_age` 查年龄区间（含 ±1 岁跳级/复读容差），并用 stage 首字经 `stage_to_level` 反查 `level`；**stage 为空**时只按 `level_min_age` 查年龄下限 | 在读阶段与年龄是最容易露馅的一处硬事实；不在读时 `level` 是已取得学历，只能校下限 | 改年龄或改阶段。stage 不在表内（如「预科」）只产 WARN 并跳过对账 |
| **M09** `protocol_refs` | 把 `agent_protocol` 整棵子树的字符串拼起来，用 `\b(根键)((?:\.[a-z_]+)+)` 抽出所有点分路径逐个 `dig`；解不开的报 error 并指出「断在哪个前缀之后」。**同时把 `[a-z_]+\.yaml` 也当引用解析**，未注册且非 optional 的文件名直接判 error。指向 `skills` / `social` / `specialties` / `shadow` 四个留空根键的路径降为 **INFO**（运行期回写后才存在）。`agent_protocol.actions` 为空另产 WARN | 协议是其他 Agent 的调用面，路径写错等于对外承诺了一个不存在的接口 | 改路径拼写，或补上被引用的字段。**`agent_protocol` 只写字段路径、不写文件名**——写 `evolution.state.trust_level`，不要写 `evolution.yaml` |

### warn / info 级（M10–M17）：提示，不阻塞

| 规则 | 级 | 实际查什么 | 为什么只是提示 | 怎么处理 |
|---|---|---|---|---|
| **M10** `identity_id` | warn | `manifest.meta.identity_id` 非空且匹配 `^id-\d{8}-[a-z_]+-[a-z]{1,8}$`；再用 `所属身份[:：]\s*(\S+)` 扫**所有**文件头部，与 manifest 值不符即报。**未替换的 `{{IDENTITY_ID}}` 占位符同样会报**——那说明脚手架没跑完，正是要暴露的 | 命名不影响加载，只影响追溯 | 统一改 manifest 与各文件头部。id 里的日期是生成日、末段是姓名拼音首字母 |
| **M11** `finance_vs_socioeconomic` | warn | 仅当 `family.finance.level` 是表内五档之一且 `personal.socioeconomic` 非空：在后者文本里搜该档的矛盾词表（如 `affluent` 撞「贫困/拮据/困难」）。**只查明显矛盾，不查相等** | `socioeconomic` 是自由文本，等价表述无穷多，能可靠判的只有对撞 | 改措辞或改档位。命中词会原样列在报错里 |
| **M12** `channel_vs_learning_style` | warn | `narrative_voice.sensory.dominant_channel` 的同义词表在 `psychology.cognition.learning_style` 文本里**找不到任何一个**即报，并提示 learning_style 实际指向哪个通道（同义词表额外含 `reading` 一档，它不是 `dominant_channel` 的合法枚举值，只用于这个反向提示） | 自由文本的印证是弱信号，用词不同不等于矛盾 | 二者对齐；确实是「视觉主导但靠动手学」的人，忽略此条并在报告里说明 |
| **M13** `goal_horizons` | warn | 三件事，都不是「递增」：①某档文本里出现明确时间表达（`literal_months` 的本周/本月/半年/明年/今年，或 `\d+(年\|个月\|月\|周\|天)`）时，取**最大值**看是否落在该档名义窗口（immediate 0–3、short_term 0–12、medium_term 12–36、long_term 36–120 个月）；②两档文本**完全相同**说明没分层；③四档只填了一部分另产 WARN | 「跨度递增」是语义判断，文本自由；代码只能判显式时间与重复 | 给各档写出不同的、时间尺度相称的内容。窗口本身有重叠（immediate ⊂ short_term），不必强凑 |
| **M14** `quality_minimums` | warn | `psychology.cognition.cognitive_biases` ≥2、`goals.fears` ≥1、`behavior.sensitive_topics` ≥1。`skills.weak_areas` ≥2 **在授权期实际不查**——其属主文件 `skills.yaml` 在 `empty_by_design` 里，代码显式跳过；字段缺失与数量不足分两种报错文本 | 只在填充模式下有意义，空白模式下模板本就为空 | 补齐条数。这是数量线，质量由 S12 人工看 |
| **M15** `cold_start_budget` | warn | 冷启动 6 文件（manifest + `files.cold_start` 五个）逐个与 `single_file_tokens: 1200` 比、合计与 `cold_start_total_tokens: 1600` 比。token 用 `est_tokens` 估：**CJK 约 1 token/字，其余约 1 token/4 字符**。按需文件只统计进 `budget.on_demand` 报告，**不产任何告警** | **成本问题不是正确性问题**，且注释密的模板注定超（种子模板实测 5698/1600，数字随模板注释变动，以报告实测值为准） | 剥注释再压。处理办法见 `./conventions.md` 第 7 节；背景见 `./architecture.md` 第 3 节 |
| **M16** `on_demand_keywords` | warn | 每个 `priority: on_demand` 条目：`load_trigger.keywords` 为空按规则严重级报（=warn）；**非空但少于 3 个只产 WARN「命中面偏窄」**；`load_trigger.context` 为空另产 WARN | 触发词缺失确实等于文件不存在，但它不破坏结构完整性 | 补到 3 个以上关键词，并写 `context` 作为关键词未命中时的语义依据 |
| **M17** `seed_markers` | info | 全量文件正则数 `source:\s*["']?seed["']?` 的出现次数，汇总成一条 INFO，并按文件列进「注入的默认值」小节 | 它是待办清单不是错误 | 人工逐条确认后去掉 `source: seed` 标记。与 S11（没有编造）配套使用 |

补充三点实现细节，影响你读报告的方式：

- `flatten` **跳过所有以 `_` 开头的键**，所以模板里的 `_note` / `_why` 不计入完整度、不参与 M04 的空值断言。
- 报告末尾「机检 17 条规则 · 命中 N 条」的 N 是**命中过的规则 ID 数**，不是问题条数；
  一条规则报 20 处也只算命中 1 条。
- 「各文件完整度」按叶子非空比例算，与规则无关，`empty_by_design` 的四个文件会标注
  「← 按设计留空」并从平均值里剔除。**它们的 0% 是正确状态，不是待补项。**

---

## 3. S01–S12 逐条

| 规则 | 级 | 为什么代码判不了 | 人该看什么 | 典型不一致 |
|---|---|---|---|---|
| **S01** mbti ↔ `behavior.interaction` | warn | 要把 `INTP` 的 I/T 维度翻译成「搭话时会怎样」，中间隔着一层人格心理学推断，没有查表可依 | mbti 的 I/E 与 T/F 两维，对照 `behavior.interaction` 的 `with_strangers` / `with_peers` / `when_criticized` 三处措辞 | MBTI 写 `INTP`，`with_strangers` 却写「热情主动搭话、迅速熟络」；或 T 型写「被批评后先安慰对方情绪」 |
| **S02** big_five ↔ `emotion` / `cognition` | warn | 0.8 这个数与「稳定平和」四个字之间没有阈值可定——0.6 算高还是中，取决于其余四维的相对关系 | `neuroticism` 高则 `emotion.baseline` 不应是「稳定平和」；`conscientiousness` 高则 `cognition` 不应「随性发散、想到哪写到哪」 | MBTI 写 `INTJ`（内倾）但 `big_five.extraversion` 给 `0.8`；`neuroticism: 0.85` 配 `emotion.baseline: 情绪稳定、少有波动` |
| **S03** attachment_style ↔ `relationships[].dynamic` | warn | 每条 `dynamic` 是自由叙述，「不在乎对方是否回应」这种反向信号有无穷多种写法 | 逐条读 `relationships.entries[].dynamic`，找与依恋类型相反的行为描述 | `attachment_style: anxious`，某条关系的 `dynamic` 写「对方几天不回也无所谓，自己有节奏」；或 `avoidant` 型写「每天主动汇报行程求确认」 |
| **S04** `goals.want_vs_need.want` ↔ `goals.objectives` | warn | 要判断的是「动机能否解释行为」这种因果关系，两段文本之间没有词面重合可依 | `objectives` 是行为层、`want` 是动机层，两者应能连成一句「因为想要 X，所以近期要做 Y」 | `want` 写「想被父亲认可」，四档 objectives 全是「提升英语口语流利度」，中间缺一环；或 objectives 里的重头戏在 want 里完全没有对应驱动力 |
| **S05** `want_vs_need.awareness` ↔ `shadow` | info | 同上，且 **`shadow.yaml` 授权期按设计为空**，此条只能在运行期回写后复核。代码用 `applies_when: shadow_not_empty` 门控：shadow 为空时**这条根本不会列进复核清单** | `awareness: unaware` 时，`shadow.repressed_needs` 应有一条与之对应的压抑需求 | 运行期回写后：`awareness: unaware` 但 `shadow.repressed_needs` 为空，等于说「他没意识到，但也没有被压抑的东西」 |
| **S06** `narrative_voice.modes` 内部一致 | warn | 「句长、标点习惯、比喻取材是否同源」是文体判断，机器统计句长也判不出比喻来源 | 对比 `modes` 五段的句长分布、标点偏好、比喻取材，应共享同一 `fingerprint` | 内心独白全是三五字短句，对话模式却写成带从句的长复合句；或语言指纹用了成年职场用语（「对齐一下」「颗粒度」）但 `personal.age` 是 12 岁 |
| **S07** `shadow.core_conflicts` ↔ `values.dealbreakers` | info | 「底线与核心矛盾对撞」需要理解两段叙述的指向，且 shadow 授权期为空。门控条件同 S05（`shadow_not_empty`） | 每条核心矛盾是否踩了自己声明的底线——踩了不一定错（人本就矛盾），但要是**刻意设计的**矛盾 | 运行期：`dealbreakers` 有「绝不撒谎」，`core_conflicts` 有「靠隐瞒维持关系」，却没有任何一处说明这个撕扯如何表现 |
| **S08** `knowledge_boundaries.known` ↔ `skills.knowledge_domains` | info | 领域名称的自由表述无法做集合比较（「编程」vs「Python」）。门控 `skills_not_empty`，授权期 `skills.yaml` 为空故不列出 | 声称已知的领域，技能侧是否有对应支撑，反之亦然 | 运行期：`knowledge_boundaries.known` 有「机械原理」，`skills` 侧却把它列在 `weak_areas` |
| **S09** `academic` 学历 ↔ `skills` 等级 | info | 学历与技能等级之间没有可写死的映射（自学者、跳级者都正常）。门控同 S08 | 学历水平与硬技能等级是否落在同一量级 | 运行期：`education.level: primary`，`skills` 里出现「熟练使用 SQL 做多表连接优化」 |
| **S10** 描述逐条有落点 | warn | **判据不在蓝本里**——要拿用户原始描述逐句核对，校验器只看得到生成物 | `provenance.yaml` 的 `allocation` / `unallocated` 清单，确认原始描述每句都有归属 | 描述里说「父母去年离婚」，`family.overview.structure` 只写了「三口之家」，这条信息在 20 个文件里没有任何落点 |
| **S11** 没有编造 | warn | 无法区分「用户说的」与「模型补的」，除非有留痕。这正是 `provenance.yaml` 存在的理由 | 对照 `provenance.yaml` 的原始描述与 `seeds` 清单；具体数字、姓名、时间三类最易编造。数量线由 M17 给 | 生成物写「月考排名第 14」「母亲在市三院工作」，描述里没有、也没标 `source: seed` |
| **S12** 角色立体 | warn | M14 只数条数，「缺点是否与人格相称」是质量判断 | 缺点/偏差/矛盾是否与 MBTI、大五、成长环境相称，还是随手凑数 | `cognitive_biases` 凑了两条「有时会拖延」「偶尔粗心」——满足 M14 的 ≥2，但与 `conscientiousness: 0.9` 打架，且对任何角色都成立，等于没写 |

`applies_when` 的门控是可依赖的：**授权期跑 `validate.py`，复核清单只出现 8 条**
（S05/S07 被 shadow 为空挡掉，S08/S09 被 skills 为空挡掉）。若这四条出现在清单里，
说明对应文件已非空——授权期见到它们，先回头查 M04。

---

## 4. 跨文件高频坑与修复顺序

高频坑集中在六处，前三处机检能抓、后三处只能人工：

| 坑 | 表现 | 抓手 |
|---|---|---|
| 年龄改了、学业没跟 | 把 17 岁改成 15 岁，`stage: 高二` 没动 | M08 |
| `agent_protocol` 写了文件名 | 写 `见 evolution.yaml` 而不是 `evolution.state.trust_level` | M09（把 `*.yaml` 当引用解析） |
| 留空文件被顺手填了 | 填充模式下把 `skills` 一起填了 | M04 |
| MBTI 与大五各写一套 | `INTJ` 配 `extraversion: 0.8` | S02（机检不管数值与字母的关系） |
| 语言层与年龄脱节 | 12 岁的角色说「颗粒度」「对齐一下」 | S06 + 人工 |
| 场景写全量而非增量 | `scene_presets` 把 `behavior` 整段复制一遍 | 人工（见 `./architecture.md` 第 6 节的纪律条目） |

**修复顺序（自上而下，不要反序）：**

1. **核心设定四项**：`personal.name.full` → `personal.age` →
   `psychology.personality.mbti` → `psychology.personality.attachment_style`。
2. **心理层**：`big_five` 五维 → `psychology.emotion` → `psychology.cognition` → `psychology.values`。
3. **语言层**：`narrative_voice.fingerprint` 与 `modes` → `behavior.language` → `behavior.interaction`。
4. **关系与场景**：`relationships.entries[].dynamic` → `family` → `goals` → `scene_presets` → `daily_rhythm`。

理由只有一条：**越靠前的字段被越多下游字段引用。** `personal.age` 一改，学业阶段、
词汇层级、语言指纹、日程、关系称呼全要跟着动；`attachment_style` 一改，所有关系条目的
`dynamic` 都要重读。反序修——先把二十条 `dynamic` 措辞调顺，再发现依恋类型本身该换——
等于把同一批文本改两遍，而第二遍往往改不干净，留下一半旧口吻。

完整的上下游对照表在 `./architecture.md` 第 6 节（标了规则号的由本文对应条目负责），
修每一处前先在那张表里查它的下游列。

---

## 5. `validate.py` 用法与收敛纪律

```bash
python3 scripts/validate.py <身份目录>            # 人读的报告
python3 scripts/validate.py <身份目录> --json     # 机读，给上层流程消费
python3 scripts/validate.py <身份目录> --strict   # 有 WARN 也返回非 0
python3 scripts/validate.py --rules               # 只打印 17+12 条规则清单，不校验
```

| 参数 | 作用 |
|---|---|
| `<model_dir>` | 含 `manifest.yaml` 的目录。位置参数，`--rules` 时可省 |
| `--json` | 输出 `errors` / `warnings` / `infos` / `completeness` / `budget` / `seed_markers` / `needs_human_review` / `rules_fired` / `passed`。**`needs_human_review` 就是 semantic 清单**，带 `hint` |
| `--strict` | 只改退出码，不改报告内容。适合 CI；日常修复别开，注释密的模板必然有 M15 |
| `--rules` | 打印规则清单后**直接返回 0**，不读 `model_dir` |

**退出码**（以实现为准）：

| 码 | 含义 |
|---|---|
| `0` | 无 ERROR（可能有若干 WARN / INFO）；`--rules` 也返回 0 |
| `1` | 有 ERROR；或 `--strict` 且有 WARN。**目录不存在、缺 `manifest.yaml`、`files` 为空都走这里**——它们被记成 M01 的 ERROR 后正常出报告 |
| `2` | 用法错误：既没给 `model_dir` 也没给 `--rules`；或 `consistency-rules.json` 读不到 / 不是合法 JSON |

脚本不依赖第三方库，内置 YAML 解析器只覆盖本模板族用到的子集（缩进映射、序列、行内
flow、引号标量、块标量、注释）。**解析不了的行记 WARN 而不中断**，所以看到成片的
「无法解析的行 / 缩进异常」时，先怀疑缩进而不是内容——那批 M05 WARN 背后可能藏着
一整棵没进文档树的子树，后续所有引用检查都会跟着误判。

### ≤3 轮代码驱动修复

一轮 = 跑一次 `validate.py` → 只改被点名的文件 → 重跑。纪律三条：

1. **每轮只改规则点名的文件和字段。** 顺手重写没被点名的段落，会把上一轮的通过项打回。
2. **改完必须重跑。** 不重跑就不知道修复引入了什么——改 `age` 修 M08，很容易撞出新的 M12。
3. **3 轮仍不收敛就停手**，把剩余项按规则 ID 列进汇报交人工，不再自动修。

第 3 条是硬性的。无界修复循环有个固定的坏结局：模型改到第四五轮开始**改规则而不是改内容**——
放宽 `enums`、删掉一条 `required_fields`、把 `budgets` 调大。那样校验会通过，
但 `agents.create()` 读的是同一份 JSON，问题只是被搬到了下游，而且从此没人知道它被放宽过。
剩三条 WARN 交人工，比自动放宽一条 error 便宜得多。

WARN 与 INFO **本来就不必清零**：M15（预算）、M17（seed 待确认）、M13 的档位提示
在正常交付物里长期存在。收敛的判据是 **ERROR 为 0**，以及剩余 WARN 每条都能说清为什么保留。
