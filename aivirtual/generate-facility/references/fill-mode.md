# 填充模式

用户给了描述时，把描述里的每条信息分配到正确的层，并补齐该设施类型的行业默认值。
核心纪律：**描述里没有的不要编**。

---

## 1. 描述 → 层 的分配表

按关键词命中，一条描述可命中多处（例如"借书押金 50 元"同时进 `services` 与 `pricing`）。

| 描述特征 | 落到 | 示例 |
|---|---|---|
| 容纳、容量、座位、车位、人数 | `capacity.totals` | 「容纳 200 人」→ `design_capacity: 200` |
| 面积、平方米、几层 | `basic.location` | 「2000 平方米」→ `area` |
| 分区、区域、几个场地 | `capacity.zones` | 「篮球场 4 个」→ zones + `resources.categories` |
| 开门、关门、几点、营业 | `time.regular` | 「9 点到 18 点」→ `weekday.open/close` |
| 周一闭馆、节假日、暑假、寒假 | `time.closed_days` / `holidays` / `seasonal` | 「周一闭馆」→ `closed_days: [monday]` |
| 高峰、饭点、忙、人多 | `time.semantic_periods` | 「中午最忙」→ 一条 `semantic_periods` |
| 预约、提前、预订 | `time.slots` + `services.prerequisites.booking_required` | 「需提前一天预约」→ `advance_booking_window: 1d` |
| 最长、限时、几小时内 | `time.slots.max_booking` + `usage.limits` | 「每次最长 4 小时」→ 两处都写 |
| 不能、禁止、不得、不允许 | `rules.rules`（phase 视内容） | 「不能带宠物」→ phase `entry` |
| 穿、着装、拖鞋、运动鞋、泳帽 | `rules.access_control.entry_requirements.dress_code` | 「必须穿运动鞋」 |
| 安静、喧哗、噪音、静音 | `rules.rules`（phase `inside`）+ `capacity.zones.noise_level` | 「保持安静」 |
| 需要证、凭卡、刷卡、登记 | `rules.access_control.entry_requirements.credentials` | 「凭借阅证」 |
| 会员、办卡、月卡、年卡 | `rules.access_control.membership` + `pricing` | 「月卡 300 元」 |
| 儿童、未成年、家长陪同、年龄 | `rules.access_control.entry_requirements.age` | 「儿童须家长陪同」→ `exceptions` |
| 借、还、租借、领用 | `services.catalog`（一条 core 服务）+ `resources.categories` | 「器材可租借」 |
| 每人最多、限、几本、几个 | `usage.limits.per_user` + `services.limits` | 「每人最多借 3 本」 |
| 收费、元、押金、免费 | `pricing` | 「借书押金 50 元」→ `deposits` |
| 折扣、半价、优惠、学生价 | `pricing.discounts` | 「学生半价」 |
| 逾期、超时、迟还 | `pricing.penalties.overdue` + 对应剧本第 2、3 节 | 「逾期每天 1 元」 |
| 损坏、赔偿、丢失、照价 | `pricing.penalties` + `resources.damage_handling` | 「损坏照价赔偿」 |
| 数量、多少台、多少册 | `resources.categories[].total` | 「藏书 5 万册」 |
| 耗材、纸、墨、用完 | `resources.consumables` | 「打印纸每月 500 张」 |
| 维护、检修、保养、清洁 | `resources.wear.maintenance_plan` | 「每月设备检修」 |
| 安全、消防、急救、救生员 | 对应 A6 剧本 + `staffing.roles` | 「配备 AED」 |
| 值班、管理员、前台、几个人 | `staffing.roles` | 「两名管理员」 |
| 隔壁、附近、旁边、去 X 办 | `relations.neighbors` / `substitutes` | 「满了可以去自习室」 |
| 归属、属于、XX 学院的 | `basic.ownership` | 「属于图书馆管理」 |
| 无障碍、轮椅、电梯 | `basic.environment.accessibility` | 「有无障碍坡道」 |
| 无法归类 | `basic.identity.description` 或对应剧本 | 不要塞进 `custom_extensions` 后就忘了 |

---

## 2. 推断规则

**severity**（后果轻重）

| 描述涉及 | severity |
|---|---|
| 人身安全、消防、危化品、传染、资格造假 | `critical` |
| 明显损害他人权益或秩序（抢占、破坏、拒付、越权操作） | `serious` |
| 影响他人体验（噪音、超时、占而不用） | `moderate` |
| 礼仪与整洁 | `minor` |

**enforcement**（当场力度）

| severity | enforcement | 例外 |
|---|---|---|
| critical / serious | `block` | 无 |
| moderate | `warn` | 反复发生可升级 |
| minor | `log` | — |

其他推断：

- 描述中出现价格 → `pricing.model` 不能留 `free`
- 出现"预约" → `services.prerequisites.booking_required: true` 且 `time.slots` 至少填 `advance_booking_window`
- 出现"押金" → `services.prerequisites.deposit_required: true` 且 `pricing.deposits` 有对应条目
- 出现资格/证件 → `protocol.queries.check_eligibility` 的判断依据要能对上 `rules.access_control`
- 出现某项可数物 → 同时建 `resources.categories` 条目，并在需要时进 `capacity.bottlenecks`
- 涉及人身风险的设施 → A6 剧本优先级设 P0，`staffing.roles` 至少一名持证人员

**不推断的**：`usage.observed_patterns`、`frequent_requests`、`friction_points`、
长期记忆、剧本第 4 节（决策取舍）——这些必须来自真实运行，编造出来会成为错误依据。

---

## 3. 行业默认值的用法

`facility-types.md` 提供各类型的行业默认值。注入时：

1. 先注入类型默认值，再用用户描述**覆盖**冲突项（用户描述优先）
2. 所有注入的默认值标 `source: seed`，让人知道哪些还需确认
3. 用户描述明确否定某默认值时删掉它，不要两条都留（例如说"不用押金"就删掉押金条目）
4. 类型未知 → `type: custom`，只注入通用安全与通用协议骨架，其余留空

---

## 4. 自检

生成后按顺序检查。前 8 项 `scripts/validate.py` 能自动查，后 4 项需要人工判断：

**机器可查**

1. 所有 `service_id` / `zone` / `resource` / `state` / `role` 引用都能解析
2. 分区容量之和 ≤ 安全容量；舒适容量 ≤ 安全容量
3. `pricing.service_fees` 的服务都存在
4. 状态机 transitions 的状态都已定义
5. JSON / JSONL 格式合法
6. `manifest.yaml` 登记与磁盘文件一致（无缺失、无孤儿）
7. `scenarios/INDEX.md` 与剧本文件互相对得上
8. L0 未超预算、无单文件超预算

**需人工判断**

9. 服务的可用时段落在开放时间内（不能在闭馆时段标记服务可用）
10. 描述里的每条信息都能在生成物里找到落点——逐条对照，漏了就补
11. 没有编造：所有具体数字、价格、时间都能追溯到用户描述或标了 `source: seed`
12. 硬约束速查（`MODEL.md` 第 2 节）的每条都能在 `rules.yaml` 里找到对应规则

---

## 5. 汇报格式

生成后向用户汇报，包含：

1. 输出目录与文件数
2. 设施类型（含是否回落 `custom`）、模式、启用/裁剪的可选层
3. **描述分配明细**：用户说的每一条 → 落到了哪个文件的哪个字段
4. **注入的行业默认值**：哪些是 `seed`、需要确认
5. **仍为空的部分**及原因（首次为空是设计，不是遗漏）
6. 校验结果（ERROR / WARN 数、各层完整度）
7. 建议的下一步：需人工确认的字段清单
