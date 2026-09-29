# 格式选型与写法约定

本文管「字段怎么写」。文件怎么切、各文件管什么，见 `architecture.md`；
留空的边界与填充流程见 `fill-mode.md`；校验规则号的判定口径见 `consistency.md`。

---

## 1. 为什么身份模型全用 YAML

20 个文件**全部是 YAML**（`manifest.files[].format` 逐条写着 `yaml`），两个可选文件也是。
这不是省事，是三个条件同时成立的结果：

| 条件 | 具体表现 |
|---|---|
| 需要行内注释解释字段语义 | `attachment_style` 的四个值各代表什么关系模型，写在字段旁边人才填得对——**这是空白模板的主要价值**，模板去掉注释就只剩一堆空键 |
| 需要人手编辑 | 蓝本是设计态产物，由人写、进 code review、看 diff；`big_five` 五个数字得肉眼调 |
| 结构嵌套深 | `psychology` 四层、`behavior.interaction` 15 类、`relationships.entries[]` 十几个键；JSON 的括号噪声会盖过内容 |

什么情况才该引入别的格式（**身份蓝本目前不满足任何一条，不要混用**）：

| 格式 | 适用条件 | 身份模型为什么用不上 |
|---|---|---|
| JSON | 机器整体覆写、无需注释、要求解析零歧义 | 唯一高频回写的 `evolution.yaml` 是**局部**改几个数值，且必须保留注释 |
| JSONL | 仅追加且持续增长的事件流 | 这类内容是记忆，不在这 20 个文件里——由 Agent 写 `role-session.db` |
| Markdown | 内容是叙述与判断而非字段 | `narrative_voice` 的叙事片段虽是散文，但要被字段路径引用（M09），必须留在 YAML 里当字符串 |

一条硬纪律：**不要把 Markdown 表格当结构化数据源**。`validate.py` 只解析 YAML，写进 Markdown 的
字段既校验不到，也无法被 `agent_protocol` 的字段路径引用。

---

## 2. `@fill` 待补标记

```yaml
  mbti: ""                      # @fill(human) 16 型之一，须与 behavior.interaction 相称
  purpose: ""                   # @fill(human) 创建意图
```

`manifest.conventions.fill_marker` 声明的格式是 `@fill(who) 说明`，`who` 三取一：

| 标记 | 谁来填 | 为什么归它 | 该归它的字段 |
|---|---|---|---|
| `@fill(human)` | 人工确认的事实 | 编造会变成后续被引用的假事实 | `personal.name.full`、`personal.age`、`psychology.personality.mbti` / `attachment_style`（四个核心锚点）、`meta.purpose`、`family.members[].name` |
| `@fill(agent)` | 运行期观测才知道 | 设计时根本没有依据 | `skills` / `social` / `specialties` / `shadow` 里的条目、`evolution.state_history` |
| `@fill(generator)` | 填充模式下由生成器写入 | 用户描述里应当有；仍留空说明描述没覆盖 | `psychology.personality.big_five` / `cognition.cognitive_biases`、`goals.fears` |

末栏是**归属判断**，不是模板现状的清单：模板里实际只标了 `human` 与 `generator` 两类。
`agent` 一类不落成标记，因为承载它的四个文件按设计整体留空（`fill-mode.md` 第 3 节），
在空壳里逐字段标 `@fill(agent)` 只会让人误以为该去填。新增字段时按此表判断该归谁。

写法细则：

- 说明文字紧跟在括号后，同一行，不换行——换行后剥注释时容易连带删掉字段。
- 只标一次。父键标了 `@fill(generator)`，五个子键不必各标一遍——重复标记只会增加填完剥注释的成本。
- 标记本身要能被 grep 到（别写成 `@ fill` 或 `TODO`），因为**它只服务人工检索**：
  `validate.py` 不认识 `@fill`，它报的完整度是按空值叶子数出来的（`--json` 的 `completeness`）。
  换句话说，剥掉 `@fill` 不会让完整度变好看，填上值才会。

**空 ≠ 错**：空是待补，引用不上才是错。M05 只查 `required_fields` 那 8 条必填；其余字段为空是合法状态。
所以填充时不要为了"看起来完整"而编造——**宁可留空并保留 `@fill`，也不要写一个后续会被当成事实使用的假值**。
一个编出来的 `birthday` 会被角色在对话里说出口，之后再也改不回来了；一个空的 `birthday` 只会让角色
说「不想提这个」。前者是错，后者是待补。

---

## 3. 来源与置信度

被推断出来、而非明确声明的值需要标来源，否则下游分不清事实与猜测：

```yaml
  - id: "mother"
    closeness: 0.8
    source: inferred          # seed | declared | observed | inferred
    confidence: moderate      # high | moderate | low
    observed_at: "2026-09-04"
```

`source` 这个字段名**全局只表示溯源等级**，四个值由 `manifest.conventions.source_enum` 钉死。
别的语义另起名：知识的获取途径叫 `knowledge_boundaries.known.domains[].acquired_via`，
技能变更的成因叫 `skills.skill_log[].caused_by`——复用 `source` 会让下游分不清在看哪层。

同理 `confidence` 分两层，值空间不同：标注层是序数 `high / moderate / low`（生成器对这条推断有多确定），
身体字段里的 `known.domains[].confidence`、`knowledge_domains[].confidence` 是 `0.0-1.0`（**角色本人**自评的确定度）。
序数词全库统一用 `moderate`，不写 `medium`——`medium` 只保留给 `thinkingLevel` 这类外部契约和长度档。

| source | 含义 | 谁写的 |
|---|---|---|
| `seed` | 生成器按角色类型注入的行业默认值，未经确认 | `scaffold.py` 从 `data/role-types.json` 注入 |
| `declared` | 用户描述里明确说过，或有其他确凿依据 | 填充模式，可在 `provenance.allocation` 里查到原文片段 |
| `observed` | 运行期从交互中统计或揭示出来 | 身份 Agent 回写 |
| `inferred` | 由其他字段推断，未经验证 | 填充模式的推断链，`provenance.allocation[].transform` 应说明怎么推的 |

只在**可能被误当作事实**的地方标注，不必每个字段都加。需要标的三类：

1. **推断出的性格维度**——`big_five` 的数值、`temperament`、`attachment_style`。用户说「内向」
   推出 `extraversion: 0.2` 是推断，不是声明。
2. **注入的角色默认值**——凡 `source: seed` 的都要标（M17，info 级）；它是给人确认用的清单入口，
   同时进 `provenance.seeds`。人工确认后改成 `declared` 并记一条 `provenance.confirmations`。
3. **关系亲密度**——`relationships.entries[].closeness` / `trust` 这类 0–1 数字，看起来像测量结果，
   实际多半是拍的。不标来源，下游会把 0.8 当真值做阈值判断。

反过来，`enum` 类字段（`gender`、`marital_status`、`priority`）不必标——它们要么对要么错，
不存在「像事实的猜测」这种中间态。

---

## 4. 命名与取值

下表与 `data/consistency-rules.json` 的 `enums` / `ranges` / `identity_id_pattern` 一致，
以那份数据为准；改这里必须同步改那里，否则 `validate.py` 与人读的约定会分叉。

| 项 | 约定 | 依据 |
|---|---|---|
| id | `snake_case`，英文，同一文件内唯一，不含空格与中文 | `manifest.conventions.id_style` |
| `identity_id` | 必须匹配 `^id-\d{8}-[a-z_]+-[a-z]{1,8}$`，即 `id-<YYYYMMDD>-<role>-<姓名拼音首字母>` | `identity_id_pattern`，M10 |
| 时间戳 | ISO-8601 带时区：`2026-09-04T14:30:00+08:00`；用于 `evolution.state.last_updated`、`state_history[].timestamp` | `manifest.conventions.timestamp_format` |
| 日期 | `YYYY-MM-DD`：`personal.birthday`、`daily_rhythm.temporal_context.current_date` | 模板注释 |
| 时刻 | `HH:MM`，24 小时制，不写 am/pm：`daily_rhythm.temporal_context.current_time`、日程时间段 | 模板注释 |
| 比例 / 大五分值 | 0–1 小数，写 `0.2` 不写 `20%`；`ranges` 全部是 `[0.0, 1.0]` | `ranges`，M06 |
| 枚举 | 全小写英文，候选值写在同行注释里（`# gradual / sudden / event_triggered`） | `enums`，M07 |
| **MBTI** | 四字母**大写**：`INTP`。这是 `enums` 里唯一的大写例外——它是外部既有编码，不是本模型自定的取值 | `enums."psychology.personality.mbti"` |
| `severity` | 仅 `hard` / `soft` 两档，出现在 `constraints` 三段的列表项上 | `enum_fields_list_items` |
| 空标量 | `""` | `manifest.conventions.empty_scalar` |
| 空列表 | `[]` | `manifest.conventions.empty_list` |
| 显式无 | `null`（区别于「待补」：`null` 表示确认没有，`""` + `@fill` 表示还没填） | — |
| 数值型空 | 键后留空（`age:`、`height_cm:`），YAML 解析成 `null`；不要写 `0` | 模板用法 |

**不要写 `"无"` / `"N/A"` / `"暂无"` / `"未知"`**。原因具体：它们是字符串，非空，
所以 M05 的必填检查会放过去；`enums` 检查会把它判成非法值报 error；而角色在对话里
真有可能把「无」念出来。空就写空。

`identity_id` 各段的坑：日期段是 8 位纯数字无分隔符（`20260904`，不是 `2026-09-04`）；
role 段允许下划线（`middle_school_student`）；末段是姓名拼音首字母，1–8 个小写字母
（李正国 → `lzg`），不能带数字，也不能写全拼超过 8 位。

---

## 5. 文件头部的 `# 所属身份: <identity_id>`

每个模板首个注释块都有这一行：

```yaml
# ============================================================
# 心理画像 · 所属身份: {{IDENTITY_ID}}
```

它存在的理由是**文件是散的**。20 个 YAML 各自独立，除 `manifest.yaml` 外没有一个文件在正文里
提到自己属于谁。把一份 `psychology.yaml` 从 A 身份目录拷进 B 身份目录，两边根键都是 `psychology`、
结构完全一样，解析、校验、加载全都不报错——角色就直接换了个脑子，而且查不出来。
这一行是唯一的归属凭证。

`validate.py` 把它与 `manifest.meta.identity_id` 对账（M10，warn 级），不一致直接报告。
写的时候三条：

- 值是渲染后的真实 id，不是 `{{IDENTITY_ID}}` 占位符——占位符没替换掉说明脚手架没跑完。
- 位置在文件最上方的注释块内，格式照抄 `· 所属身份: ` 前缀，别改成 `# identity: xxx`。
- 剥注释压预算时（第 7 节）**这一行必须留**。它是校验依赖项，不是说明文字。

---

## 6. `writable` / `initial_state` 的语义与回写纪律

`manifest.files[]` 的这两个字段是运行期的行为开关，不是文档标签。

| `writable` | 含义 | 哪些文件 |
|---|---|---|
| `false` | 设计态，运行期只读；要改只能改蓝本再重新 create | `personal` / `academic` / `family` / `constraints` / `agent_protocol` / `psychology` |
| `true` | 运行期会被身份 Agent 回写 | 其余 13 个维度文件 |

`false` 这六个的共同点是「改了就不是同一个人」：姓名年龄、学历家庭是既成事实，
性格底层是行为的上游（改 `mbti` 要连带核对 `behavior` 与 `relationships`），
约束和协议是安全边界——如果运行期能自己改约束，约束就不存在了。

`evolution.yaml` 是**唯一高频回写**的文件：`state` 的五个数值每轮都可能变。这也是它必须冷启动常驻
的原因（每轮都读、每轮都写），以及它自成一份而不塞进 `psychology.yaml` 的原因——
把每轮回写的字段和只读的性格层放同一个文件，等于每轮重写一遍性格。

回写纪律，三条都不是可选的：

| 纪律 | 为什么 |
|---|---|
| **写前先读** | 蓝本可能已被人工改过；不读就写会把人工修订覆盖掉 |
| **保留注释与未识别字段** | 注释是下一个人的填写依据；未识别字段可能来自更新版模板，删掉就永久丢了 |
| **只改被点名的字段块** | 更新 `state.trust_level` 不要顺手重排 `growth_rules`——diff 噪声会让 code review 失效 |

`initial_state: empty` 的四个文件（`skills` / `social` / `specialties` / `shadow`）即使在填充模式下
也留空，理由、校验方式（M04，error 级）与「留空但必须建出空壳」的原因见 `fill-mode.md` 第 3 节。
本文只强调一点：**空壳文件的注释块要完整保留**——它是这四个文件在运行期回写时唯一的字段格式说明。

---

## 7. 注释与 token 预算的取舍

模板注释密到几乎每个字段一行，这是刻意的：模板的主要交付物是**脚手架**，注释就是填写说明。
代价是冷启动 6 文件在种子状态下必然超预算（具体数值与超出后的处理见 `architecture.md` 第 3 节）。
超出只产 WARN（M15）不阻塞——它是成本问题，不是正确性问题。

解法不是写少注释，而是分阶段：**种子模板注释全留（给人填），填完落地后按需剥注释（压常驻成本）**。
剥的时候按下表判断，不要一刀切删光：

| 注释类型 | 留还是剥 | 为什么 |
|---|---|---|
| `# 所属身份: <id>` | **必留** | 校验依赖项（第 5 节），不是说明 |
| 解释字段语义的 | **留** | `# 对当前对话方，非全局`——不留，下一个改这个字段的人会理解错 |
| 列候选值的 | **留** | `# gradual / sudden / event_triggered`——回写时 Agent 靠它知道能填什么，删了就要去翻 `consistency-rules.json` |
| 跨文件对账提示 | **留** | `# 与 family.finance.level 不得矛盾`——这是 M11 / M12 的人读版，删了改一处就忘另一处 |
| 讲怎么填的 | **可剥** | `# @fill(human) 整数`、`# 按优先级排序`——填完就没有读者了 |
| `@fill` 标记本身 | 填了就剥，没填就留 | 留着未填的 `@fill` 是正确行为：它是人工 grep 待补项的唯一入口 |
| 被注释掉的示例条目 | 有真条目后可剥 | `# - id: ""` 那一整段样例，正文有真数据了就是纯占位 |
| 顶部大注释块的设计说明 | 冷启动文件可剥，按需文件保留 | 冷启动每轮都付它的 token；按需文件一轮也就付一次 |

只剥冷启动那 6 个文件就能拿到绝大部分收益——按需文件的注释一轮最多付一次，剥它性价比很低，
而丢掉的可读性是永久的。

---

## 8. 隐私最小化

身份蓝本是**长期留存的 git 资产**：进版本库、被 diff、被复制成多个实例、可能被导出分享。
它跟运行期的会话数据不同——会话可以过期，git 历史不会。所以：

| 禁止 | 替代写法 |
|---|---|
| 真实身份证号、护照号、学号、工号 | 不写；确实需要唯一标识就用 `identity_id` |
| 真实手机号、邮箱、社交账号 | 不写；`social` 的网络形象只写平台类型与风格，不写账号 |
| 真实住址、学校/公司全名 | 写到区域与类型即可：`region: "杭州"`、`academic.education.school_type: "public"` |
| 生物特征（人脸、指纹、病历号） | `personal.appearance` 只写可对外描述的特征（「黑框眼镜」），`health` 只写状态不写诊断记录编号 |

两条与身份模型特有的红线：

1. **不冒充真实存在的公众人物。** 这是 `constraints.global` 里的 `severity: "hard"` 条目之一，
   不是建议。原因不止合规：真人有可被核实的言行，蓝本编出来的部分会被当成那个人的观点。
   要做「像某位物理学家的老师」，写角色特质（`INTP` + 高开放性 + 物理学背景），不写他的名字。
2. **涉及真人的关系条目用化名 + 关系类型。** `relationships.entries[].name` 与
   `family.members[].name` 写化名或称谓（「母亲」「班主任王老师」），`role` / `category` 承载
   真正有用的信息。这两个字段驱动的是角色的互动模式，模式不依赖真名；
   而真名一旦写进去，git 里就删不掉了。

需要跨条目关联同一个人时用 `entries[].id`（`snake_case`，如 `mother` / `mentor_wang`）串起来——
`network.strongest_bond` 和 `get_relationship` 引用的都是这个 id，所以真名从头到尾都不必出现。
