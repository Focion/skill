---
name: init-agents-docs
description: >
  初始化项目的 .agents 文档结构（notes 七类目录 + skills + AGENTS.md 引导文件）。
  当用户要求初始化/搭建/补齐项目文档结构、创建 .agents 目录、建立 notes（research/product/tech/review/changelog/plan/archive）
  或 skills 目录、生成 AGENTS.md 引导文档时使用。也用于检查已有 .agents 结构是否完整并补齐缺失部分。
version: 1.0.0
allowed-tools: Bash, Read, Write, Edit, Glob
---

# 初始化项目 .agents 文档结构

在目标项目根目录创建标准化的 `.agents` 文档骨架，供人和 Agent 共同读写。

## 目标结构

```
.agents/
├── AGENTS.md          # 引导文件：告诉 Agent 去哪读、往哪写
├── notes/             # 项目相关文档
│   ├── research/      # 研究类文档（调研、选型、可行性）
│   ├── product/       # 产品设计文档（PRD、交互、需求）
│   ├── tech/          # 技术设计文档（架构、方案、接口）
│   ├── review/        # CR 文档（代码评审记录与结论）
│   ├── changelog/     # 变更文档（发布、迁移、破坏性变更）
│   ├── plan/          # 计划文档（路线图、迭代计划、任务拆解）
│   └── archive/       # 归档文档（作废或已删除内容）
└── skills/            # 项目技能，一个子目录一个 skill，内含 SKILL.md
```

## 执行步骤

1. **确认目标目录**。默认当前工作目录；用户指定了路径就用它。若目录不是项目根（无 `.git`/`package.json`/`pom.xml` 等标志），向用户确认一次再继续。

2. **运行初始化脚本**：

   ```bash
   bash "$CLAUDE_SKILL_DIR/scripts/init-agents.sh" [目标目录]
   ```

   若 `$CLAUDE_SKILL_DIR` 不可用，使用本 SKILL.md 所在目录的绝对路径。

   脚本行为：
   - **幂等**：已存在的目录和文件一律跳过，绝不覆盖。适合对已有项目补齐缺失部分。
   - 每个 notes 子目录写入一份 `README.md`，说明用途、命名与模板（同时保证空目录能被 git 跟踪）。
   - 写入 `.agents/AGENTS.md` 引导文件和 `.agents/skills/README.md` 技能编写规范。
   - 结束后打印创建/跳过清单。

   常用参数：
   - `--force`：覆盖已存在的 README/AGENTS.md（重置模板时用，会丢失本地修改，执行前先向用户确认）
   - `--dry-run`：只打印将要做什么，不落盘

3. **按项目定制 AGENTS.md**。脚本产出的是通用模板，读一遍项目实际情况（语言、模块划分、已有文档位置），把 AGENTS.md 里的「项目上下文」一节补成真实内容，并把已有的散落文档归位到对应 notes 子目录。

4. **向用户汇报**：创建了哪些、跳过了哪些、以及建议后续把哪些现有文档迁进来。

## 写文档时的约定

初始化完成后，本项目内新增文档遵循 AGENTS.md 中的规范，要点：

- 文件名 `YYYY-MM-DD-<kebab-slug>.md`，日期为文档创建日期。
- 每篇文档带 frontmatter：`title` / `date` / `status` / `owner` / `tags` / `related`。
- 文档作废时移入 `notes/archive/`，并在 frontmatter 标注 `status: archived` 与原路径，不要直接删除。

## 注意

- 不要在 `.agents/notes/` 里放代码或大体积二进制文件；截图等附件放在同目录的 `assets/` 子目录。
- `.agents` 应纳入版本管理（不要加进 `.gitignore`），它是团队与 Agent 的共享上下文。
