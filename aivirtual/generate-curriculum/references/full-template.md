# 完整课程设计模板（10 维度）

当用户使用 `/generate-curriculum --full` 时执行此模板。输入格式、解析规则、输出要求与 SKILL.md 中范围卡保持一致，但输出结构按以下 10 维度生成。

---

## 模板结构

```yaml
# ============================================================
# 课程定义模板
# 学科: <subject>
# 生成时间: <timestamp>
# ============================================================

# ------ 维度一：元信息 ------
meta:
  id: ""                              # 模板唯一标识，格式: curriculum-<YYYYMMDD>-<subject>-<slug>
  version: "1.0.0"
  subject: ""                         # 学科名称
  subject_category: ""                # 学科大类: 文科/理科/体艺/技术/综合
  curriculum_type: ""                 # 必修/选修/拓展/竞赛/社团/校本
  textbook_version: ""                # 教材版本（如"人教版""北师大版"）
  author: ""
  created_at: ""
  purpose: ""                         # 本课程模板的设计意图
  tags: []

# ------ 维度二：课程定位 ------
positioning:
  education_stage: ""                 # 学段: 小学/初中/高中/大学
  grade: ""                           # 年级: 一年级~高三/大一~大四
  semester: ""                        # 学期: 上学期/下学期/全学年
  difficulty:
    level: ""                         # 低/中低/中/中高/高
    description: ""                   # 难度的具体含义说明
  prerequisites: []                   # 先修知识/先修课程要求
  target_students: ""                 # 面向学生画像（如"普通班""重点班""体育特长生"）

# ------ 维度三：教学范畴（核心约束维度） ------
scope:
  # 必学内容：Agent 必须覆盖的核心知识和技能
  required_topics:
    - topic: ""                       # 知识点/技能名称
      category: ""                    # 所属单元或模块
      depth: ""                       # 了解/理解/掌握/运用/创造
      key_points: []                  # 核心要点
      hours: ""                       # 建议课时

  # 选学内容：Agent 可以涉及但不强制的拓展内容
  optional_topics:
    - topic: ""
      category: ""
      condition: ""                   # 在什么条件下引入（如"学有余力时""学生主动提问时"）

  # 明确禁止涉及的内容：Agent 绝对不能主动教授或深入讨论的内容
  excluded_topics:
    - topic: ""
      reason: ""                      # 为什么排除（超纲/不适合该年龄段/课程定位外）
      handling: ""                    # 当学生问到时如何处理: redirect(引导回本课范畴)/brief_mention(简要提及后引回)/hard_refuse(明确说明不在范畴内)

  # 跨学科关联：可以借用但不深入的其他学科知识
  cross_disciplinary:
    - subject: ""                     # 关联学科
      topics: []                      # 可借用的知识点
      depth: ""                       # 仅类比/可简要解释/可展开讨论

# ------ 维度四：教学目标 ------
objectives:
  # 知识目标：学生应该"知道"什么
  knowledge:
    - description: ""
      measurable: ""                  # 可衡量的指标

  # 能力目标：学生应该"能做到"什么
  skills:
    - description: ""
      measurable: ""

  # 核心素养目标：对应学科核心素养
  literacy:
    - dimension: ""                   # 素养维度名称
      description: ""

  # 情感态度目标：学生应该形成的态度和价值观
  affective:
    - description: ""

# ------ 维度五：教学策略 ------
strategy:
  teaching_methods: []                # 主要教学方法: 讲授法/讨论法/探究法/项目式/示范法/翻转课堂/游戏化
  interaction_mode: ""                # 互动模式: 讲授为主/问答为主/讨论为主/实操为主
  questioning:
    style: ""                         # 提问风格: 引导式/苏格拉底式/开放式/阶梯式
    wait_time: ""                     # 给学生的思考时间要求
    follow_up: ""                     # 追问策略
  feedback:
    positive: ""                      # 正面反馈方式
    corrective: ""                    # 纠正性反馈方式
    frequency: ""                     # 反馈频率
  scaffolding:
    when_stuck: ""                    # 学生卡住时的脚手架策略
    when_wrong: ""                    # 学生答错时的引导策略
    when_exceeding: ""                # 学生超前时的引导策略

# ------ 维度六：评估体系 ------
assessment:
  formative:                            # 过程性评价（日常）
    - method: ""                        # 课堂观察/口头提问/随堂练习/小组展示/实操演示/作品集
      frequency: ""                     # 每节课/每周/每单元
      weight: ""                        # 占总评比重
      criteria: []                      # 评价标准
  summative:                            # 终结性评价（阶段性）
    - method: ""                        # 笔试/实操考核/项目答辩/作品展示/体能测试
      frequency: ""                     # 期中/期末/每学期
      weight: ""
      criteria: []
  rubric:                               # 评分标准模板
    levels:
      - level: ""                       # 优秀/良好/合格/待提高
        description: ""
        score_range: ""
  special_rules: []                     # 特殊评估规则（如"体育免测条件""残障学生替代评估"）

# ------ 维度七：Agent 行为约束（教师 Agent 核心约束） ------
agent_constraints:
  communication:
    tone: ""                            # 沟通语气: 亲切鼓励/严谨专业/轻松活泼/严肃认真
    language_level: ""                  # 用语水平: 与学生年龄匹配的词汇和句式复杂度
    formality: ""                       # 正式程度: 口语化/半正式/正式
    max_response_depth: ""              # 回答深度上限: 点到为止/适度展开/深入讲解
    encourage_style: ""                 # 鼓励方式: 具体表扬/过程性肯定/成长型反馈

  boundary_rules:
    # 当学生提问超出 scope.required_topics 和 scope.optional_topics 范围时
    out_of_scope:
      default_action: ""                # redirect/brief_mention/hard_refuse
      response_template: ""             # 回复模板，如"这个问题很好，不过超出了我们目前的学习范围。我们先聚焦在..."
      log_for_review: true              # 是否记录超范畴提问供教师复盘

    # 当学生提问触及 scope.excluded_topics 时
    excluded_topic_hit:
      response_template: ""             # 如"这属于更高阶段的内容，等你到了XX阶段会系统学习"
      escalate: false                   # 是否上报给人类教师

    # 当学生持续偏离主题时
    off_topic:
      tolerance: ""                     # 容忍次数或轮数
      redirect_strategy: ""             # 自然过渡/直接引回/提出关联问题引回

  difficulty_adaptation:
    # 难度等级如何影响 Agent 的具体行为
    vocabulary: ""                      # 用词复杂度说明
    example_abstraction: ""             # 举例抽象程度: 生活化具体/半抽象/学术抽象
    expected_student_depth: ""          # 对学生回答深度的期望
    error_tolerance: ""                 # 容错空间: 高(多次引导)/中(适度纠正)/低(严格要求)

  prohibited_behaviors:
    - behavior: "不对学生做人格层面的负面评价"
      severity: "hard"
    - behavior: "不直接给出完整答案，优先引导思考"
      severity: "soft"
    - behavior: "不使用超出学生认知水平的术语而不解释"
      severity: "soft"
    - behavior: "不在学科范畴外给出专业建议（如医疗、心理诊断）"
      severity: "hard"

# ------ 维度八：资源与环境 ------
resources:
  textbooks:
    - name: ""                          # 教材名称
      publisher: ""                     # 出版社
      edition: ""                       # 版次
      chapters: []                      # 使用的章节范围
  supplementary: []                     # 补充材料: 练习册/阅读材料/视频/在线资源
  equipment:                            # 器材与设备
    - name: ""
      quantity: ""
      purpose: ""                       # 用于哪些教学内容
      safety_notes: ""                  # 使用安全注意事项
  venues:                               # 场地要求
    - name: ""                          # 教室/实验室/操场/体育馆/机房
      requirements: []                  # 场地具体要求
  digital_tools: []                     # 数字工具: 软件/平台/App

# ------ 维度九：教学进度 ------
pacing:
  total_hours: ""                       # 总课时数
  hours_per_week: ""                    # 每周课时
  units:
    - name: ""                          # 单元/模块名称
      topics: []                        # 包含的知识点（对应 scope.required_topics）
      hours: ""                         # 分配课时
      sequence: ""                      # 教学顺序编号
      milestone: ""                     # 单元结束时学生应达到的里程碑
  key_checkpoints:
    - week: ""                          # 第几周
      event: ""                         # 检查点事件: 单元测试/期中考/阶段展示/模拟赛
      covers: []                        # 覆盖哪些单元

# ------ 维度十：差异化教学与安全 ------
differentiation:
  tiers:
    - level: "基础层"
      target: ""                        # 面向哪些学生
      strategy: ""                      # 教学调整策略
      adjusted_objectives: []           # 调整后的目标
    - level: "进阶层"
      target: ""
      strategy: ""
      adjusted_objectives: []
    - level: "拔尖层"
      target: ""
      strategy: ""
      adjusted_objectives: []
  special_needs:
    - condition: ""                     # 特殊情况（如身体残疾、学习障碍）
      accommodation: ""                 # 适应性调整方案

safety:
  physical:                             # 身体安全（体育/实验等学科重点）
    warmup_required: false              # 是否必须热身
    warmup_duration: ""
    prohibited_actions: []              # 禁止的危险动作
    injury_protocol: ""                 # 受伤应急流程
    medical_check: ""                   # 体检/健康确认要求
  psychological:                        # 心理安全
    sensitive_content_handling: ""      # 敏感内容（如历史事件、文学作品中的争议）处理方式
    anti_bullying: ""                   # 防止课堂霸凌的措施
    stress_management: ""               # 学业压力管理建议
  equipment_safety: []                  # 器材安全规范（实验/体育/技术课）
```

---

## 填充模式的生成规则

当用户提供了课程描述时，按以下规则填充：

### 通用规则

1. **内部一致性**：所有维度之间必须自洽。难度等级决定 scope 的深度、agent_constraints 的用语水平、assessment 的评分标准、strategy 的互动方式。
2. **由描述推理**：用户给出的描述是种子信息，从中推导出合理的完整课程设计。例如"高三,难度中低"→ 目标是夯实基础、查漏补缺，而非拔高冲刺。
3. **禁止内容必须明确**：根据学段和难度，自动推断哪些内容超纲或不适合，填入 `scope.excluded_topics`，并为每条配上合理的 `handling` 策略。
4. **id 生成**：格式为 `curriculum-<YYYYMMDD>-<subject>-<slug>`。
5. **难度联动**：难度等级必须传导到以下字段：
   - `agent_constraints.communication.language_level`
   - `agent_constraints.difficulty_adaptation` 全部子字段
   - `scope.required_topics` 中每个 topic 的 `depth`
   - `assessment.rubric.levels` 的评分标准
   - `strategy.questioning.style` 和 `strategy.scaffolding`

### 描述关键词智能分配

解析用户输入的描述，按关键词自动分配到对应维度：

| 关键词/模式 | 分配到维度 | 示例 |
|------------|-----------|------|
| 年级、学段、高一~高三、初一~初三 | positioning | "高三" → positioning.grade |
| 难度、难度等级 | positioning.difficulty | "难度中低" → positioning.difficulty.level |
| 重点、侧重、核心、必学 | scope.required_topics | "重点古诗文" → required_topics 权重提升 |
| 不涉及、不学、不教、排除、禁止 | scope.excluded_topics | "不涉及文学批评理论" → excluded_topics |
| 拓展、选学、了解即可 | scope.optional_topics | "拓展了解宋元话本" → optional_topics |
| 项目名、运动名、技能名 | scope.required_topics | "装备橄榄球" → required_topics |
| 大力发展、重点发展 | scope.required_topics（高优先级） | "大力发展腰旗橄榄球" → required_topics + hours 加大 |
| 兼顾、辅助、适当 | scope.required_topics（低优先级） | "兼顾足球篮球" → required_topics + hours 较少 |
| 教材、版本 | resources.textbooks | "人教版" → resources.textbooks |
| 课时、每周 | pacing | "每周3课时" → pacing.hours_per_week |
| 考试、测试、评价 | assessment | "注重过程性评价" → assessment.formative 权重提高 |
| 其他未匹配 | 根据语义就近分配 | 兜底由 AI 判断最合适的维度 |

### 学科类型特化规则

根据学科类别，自动注入合理的默认内容和约束：

#### 语文 (chinese)

- `subject_category`: "文科"
- scope.required_topics 默认模块：现代文阅读、古诗文阅读、文言文、写作、语言文字运用、名著阅读
- scope.excluded_topics 根据难度自动填充：
  - 难度低/中低 → 排除：文学批评理论、比较文学、语言学专业分析、学术论文写作
  - 难度中/中高 → 排除：文学批评理论、比较文学
  - 难度高 → 排除：比较文学（仅排除大学级内容）
- agent_constraints 默认：
  - tone: "亲切鼓励，注重文学感受力的培养"
  - prohibited_behaviors 追加："不以标准答案否定学生的合理文学解读"(soft)
- assessment 默认侧重：阅读理解 + 写作 + 古诗文默写
- safety.psychological.sensitive_content_handling: "文学作品中涉及的战争、死亡、爱情等主题，以文学审美和人文关怀视角引导，不回避但注意年龄适配"

#### 数学 (math)

- `subject_category`: "理科"
- scope.required_topics 默认模块：根据年级自动匹配（如初二→ 一次函数、全等三角形、数据分析；高三→ 函数、导数、解析几何、概率统计）
- scope.excluded_topics 根据学段严格限定：
  - 初中 → 排除所有高中及以上内容（如导数、极限、微积分）
  - 高中 → 排除大学内容（如实分析、抽象代数、拓扑）
- agent_constraints 默认：
  - tone: "严谨专业，注重逻辑推理过程"
  - scaffolding.when_wrong: "引导学生检查每一步推理，定位错误环节，而非直接指出"
  - prohibited_behaviors 追加："不跳步骤给结论"(soft)、"不使用未教授的定理或公式"(hard)
- assessment 默认侧重：计算准确性 + 推理过程完整性 + 应用题建模能力

#### 英语 (english)

- `subject_category`: "文科"
- scope.required_topics 默认模块：听力理解、阅读理解、语法与词汇、写作、口语表达
- scope.excluded_topics 根据难度：
  - 难度低/中低 → 排除：学术英语写作、文学原著精读、语言学理论
  - 难度中/中高 → 排除：语言学理论、专业翻译技巧
- agent_constraints 默认：
  - tone: "鼓励开口，对语法错误先肯定表达意愿再温和纠正"
  - communication 特殊：可根据设定在教学中适当使用英文交流
  - prohibited_behaviors 追加："不嘲笑发音和语法错误"(hard)

#### 物理 (physics)

- `subject_category`: "理科"
- scope.required_topics 默认模块：根据年级匹配（如高一→ 运动学、力学；高二→ 电磁学、光学）
- scope.excluded_topics：未教授的高阶数学工具对应的物理内容（如未学微积分则排除微积分形式的物理推导）
- agent_constraints 默认：
  - scaffolding.when_stuck: "引导从物理情景建模开始，先画受力分析图/电路图/运动示意图"
  - prohibited_behaviors 追加："不使用学生未学的数学工具"(hard)
- safety：实验课相关安全规范（电路实验、力学实验）
- resources.equipment：常见实验器材

#### 体育 (pe)

- `subject_category`: "体艺"
- scope.required_topics 结构特化为"项目制"：
  - 每个 topic 代表一个运动项目
  - 增加字段：skill_levels（基础技术/战术配合/比赛应用）、equipment_needed、venue_required
- scope.excluded_topics 默认：
  - 极限运动（攀岩、跑酷等无安全保障的项目）
  - 高对抗格斗类（拳击、摔跤等，除非明确指定）
  - 超出学生体能的专业训练方法
- agent_constraints 默认：
  - tone: "积极鼓励，注重运动乐趣和团队精神"
  - prohibited_behaviors 追加："不以体能差异歧视或羞辱学生"(hard)、"不强迫带伤训练"(hard)
- safety 重点填充：
  - physical.warmup_required: true
  - physical.warmup_duration: "不少于15分钟"
  - physical.injury_protocol: "立即停止运动→初步评估→校医处理→通知家长→记录"
  - physical.medical_check: "学期初体检合格方可参加对抗性项目"
  - physical.prohibited_actions: 根据具体项目填充（如橄榄球禁止头部冲撞）
- assessment 特化：体能测试 + 技术动作评估 + 比赛表现 + 体育精神
- differentiation.special_needs 重点：伤病学生替代方案、体能弱势学生的渐进计划

#### 化学 (chemistry)

- `subject_category`: "理科"
- safety 重点：实验安全（防护装备、化学品存储、废液处理、应急处理）
- resources.equipment：实验器材和化学药品清单
- agent_constraints.prohibited_behaviors 追加："不提供危险化学反应的详细配方"(hard)

#### 生物 (biology)

- `subject_category`: "理科"
- safety.psychological：涉及人体、生殖等敏感话题时的年龄适配处理策略
- agent_constraints：科学严谨，区分"科学事实"和"科学假说"

#### 历史 (history)

- `subject_category`: "文科"
- agent_constraints 默认：
  - tone: "客观中立，引导多角度思考"
  - prohibited_behaviors 追加："不对历史人物做非学术性的道德审判"(soft)、"不传播未经学术界广泛认可的历史观点"(hard)
- safety.psychological.sensitive_content_handling: "涉及战争、屠杀、政治运动等内容时，以史实为基础，引导理性思考，注意学生情绪"

#### 音乐 (music)

- `subject_category`: "体艺"
- scope.required_topics 结构特化：音乐鉴赏、乐理基础、演唱/演奏、音乐创作
- agent_constraints：鼓励创造性表达，不以"标准"否定学生的音乐感受

#### 美术 (art)

- `subject_category`: "体艺"
- scope.required_topics 结构特化：美术鉴赏、绘画/设计/手工、创意表达
- agent_constraints：尊重个人审美差异，评价注重创意过程而非仅看成品

#### 信息技术 (it)

- `subject_category`: "技术"
- scope.required_topics 结构特化为"技术栈"：编程语言、工具平台、项目实践
- scope.excluded_topics 明确技术边界：如"Python入门"课程排除C++、算法竞赛、底层系统编程
- agent_constraints.prohibited_behaviors 追加："不提供可能用于网络攻击或作弊的代码"(hard)
- resources.digital_tools：IDE、在线平台、教学沙盒环境

#### 自定义学科

如果学科不在上述列表中：
- `subject_category` 由 AI 推断最接近的大类
- 不注入特化默认内容，只保留通用结构
- `agent_constraints.prohibited_behaviors` 保留全局默认项
- 其余字段根据描述合理推断

---

## 空白模式的生成规则

当用户仅提供学科名称、没有描述时：

1. 输出完整的 10 维度 YAML 骨架
2. 所有值字段留空（字符串为 `""`，数字为空，列表为 `[]`）
3. 每个字段保留中文注释说明用途
4. `meta.subject` 填入学科名称
5. `meta.subject_category` 根据学科填入对应大类
6. `meta.created_at` 填入当前日期
7. `agent_constraints.prohibited_behaviors` 填入默认的全局禁止行为（这些不留空）
8. `safety` 根据学科类型填入基本安全规则（体育填身体安全、理科填实验安全、文科填心理安全）
9. `scope.excluded_topics` 留空但注释中给出该学科常见的排除方向提示

---

## 输出要求

1. 保存到 `curriculums/` 目录。
2. 文件名格式：`<subject>-<grade>-<slug>.yaml`（如 `pe-g10-football-rugby.yaml`、`chinese-g12-poetry-writing.yaml`）
3. 向用户展示生成结果的摘要，包含：学科、学段、难度、必学内容概要、明确排除的内容、Agent 核心约束。
4. 告知用户可以手动编辑 YAML 文件进行微调。
5. 提示用户此模板可与 `generate-identity`（教师身份）和 `generate-guideline`（学校准则）组合使用。