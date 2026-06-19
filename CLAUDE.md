# CPR Project Instructions

This project is currently in product planning/prototype stage.

## Product direction

Build an interactive command workspace:

- Main input is always the command line.
- Normal input constructs or executes real commands.
- Slash commands such as `/ai`, `/explain`, `/fix`, `/help` provide assistance.
- UI shows current command, current layer description, next available tokens, and execution/AI results.
- Avoid turning simple commands into a heavy custom menu system.

## First prototype scope

Start with SDKMAN only:

- `sdk`
- `sdk list`
- `sdk list java`
- `sdk install java <identifier>`
- `sdk use java <installed-version>`
- `sdk default java <installed-version>`
- `sdk current java`

## Development style

- Keep real commands visible.
- Selecting an option appends a token to the command input.
- Going back deletes the last token.
- Add i18n from the beginning.
- Commit each completed issue as its own focused commit.
- Prefer prototype validation before broad migration from CUI.

## Workspace Boundaries

- 文档、规划与应用代码暂时同处 `/Users/leel/my_work/cpr_副本/`（原型阶段共存）。
- 在选定 TUI 技术栈与实现语言之前，不在该目录下铺大量代码骨架。
- 委派代码任务时，显式告诉实现 agent 工作目录就是项目根。

## CCB Collaboration

- 本项目用 CCB 多 agent 协作；topology 见 `.ccb/ccb.config`。
- 协调者：Claude（ccb_self）。最终验收：archi。
- 默认第一开发对：agent1 (claude) + agent2 (opencode)。
- 第二开发对（更大任务或独立验证）：agent3 (codex) + agent4 (kiro-cli)。
- 详细协作规约见 `.ccb/ccb_memory.md`。

## Delegation Rules

- 用 CCB `ask` 进行任务分派与协作。
- 每个委派任务包含：目标、工作目录、文件或范围、约束、期望输出、验证命令、回调需求、禁止重叠。
- 优先成对开发，避免孤立实现。
- 小任务只用 `agent1 + agent2`；文件边界与依赖清晰时再启用第二对。
- 不要让两对 agent 并发编辑同一批文件。

## Pair Development Rules

- 一对内成员有不同角色：主实现、同伴评审、测试编写、边界检查或备选探索。
- 每个 CCB 任务对应单一可验证目标，避免一对内同时做无关工作。
- 评审通过后由协调者整合，再决定是否合并。

## Project Management Loop

- 需求讨论 → `docs/04-会议记录/`。
- 规划与任务拆分 → `docs/03-项目规划/任务分解.md` + `滚动执行列表.md`。
- 接口契约与验收标准 → `docs/02-系统设计/`。
- 验收报告 → `docs/05-验收反馈/`。
- 实施 / 发布记录 → `docs/04-实施部署/`。
- 待优化项 → `docs/06-待优化/`。
- 开发日志 → `docs/08-开发日志/`。
- 任务流转：拉滚动列表 → 写/更新契约 → 派发开发对 → 测试与验收 → archi 评审 → 合并。

## Change Intake and Priority Rules

- Bug、新需求、遗漏边界、契约缺口及时记入 `docs/03-项目规划/变更与缺陷队列.md`。
- 高优先级（P0/P1）插入当前滚动列表前部；低优先级进入 backlog 或 `docs/06-待优化/`。
- 若变更使契约失效，回到需求讨论再继续实现。

## Contract, Test, and Acceptance Rules

- 契约定义：输入、输出、状态迁移、不变量、错误情况、兼容性约束、验收标准、测试义务。
- 测试与验收报告必须引用所验证的契约或需求。
- 命令树原型核心交互（token 追加/删除/导航/动态候选/slash command 解析/Executor）必须有单元测试。
- 不引入 Playwright 或浏览器自动化（MVP 是 TUI/终端 UI）。

## Branch, Release, Tag, and Version Rules

- 详见 `docs/03-项目规划/分支与发布规约.md`。
- 项目尚未 `git init`，仓库初始化后再正式启用本规约。
- 任务分支：`feat|fix|chore/T-NNN-短描述`，每任务单分支。
- 版本号格式：`YYYY.MM.<total_commit_count>`。
- 仅在最终验收通过后打 tag。

## Environment and Secrets Rules

- 真实 `.env`、API key、token、secret 不进入 git、文档、日志、prompt。
- 必需变量名通过 `.env.example` 维护。
- AI slash 命令的 LLM API key 通过环境变量读取，不写入仓库。
- 缺失 secret 时向用户索取。

## Database Migration and Data Safety Rules

- 当前 MVP 不使用数据库。
- 若后续引入持久化（如缓存命令树或会话历史），需先建立迁移与数据安全规约再写代码。

## Dependency Change Rules

- 详见 `docs/03-项目规划/环境密钥与依赖变更规约.md`。
- 任何新增 / 升级 / 删除依赖前，提供原因、影响、lockfile 评审、兼容性风险、验证命令、回滚方案。
- TUI 库（prompt_toolkit / Textual / blessed）选型确定前不引入交互框架依赖。

## Incident and Blocker Escalation Rules

- 重复测试失败、CCB 通信问题、provider 故障、发布失败、需求冲突需升级到 `docs/03-项目规划/事故阻塞升级记录.md`。
- 重启或清空上下文前先诊断 CCB 状态，避免使用清空记忆的重置路径（如 `ccb -n`）。

## Review and Verification

- 评审失败时先把具体可执行反馈发回原开发对；修复后重跑验证。
- archi 做最终验收：契约符合度、代码评审、合并就绪度。
- 通过后由协调者按用户授权合并。

## Takeover Conditions

- Claude 仅在以下情况接管实现：agent 阻塞、反复评审失败、偏离需求、紧急小修、需要集中整合、用户明确要求。
- 接管前说明：原因、范围、已知风险、保留或替换的既有工作。

## Documentation Rules

- 不主动新建说明类 Markdown，除非用户要求或被既有规约要求。
- 已有文档优先在原文件追加 / 更新，不在多处复制规约。
- 涉及阶段性决策时，在对应 `docs/` 子目录写一份带日期的记录。
