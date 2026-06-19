# CCB Project Memory

本项目（CPR — Command Prompt Runner）使用 CCB 进行多 agent 可见协作。

## Collaboration

- 你是 CCB 项目团队中的一个 agent。
- 通过 CCB `ask` 与已配置的其他 agent 进行项目级协作。
- 委派任务时给出：目标、范围/文件、假设、期望输出、验证需求。
- 回复时给出：发现、变更、验证、阻塞、风险。

## Ask Communication

优先形式：

```text
/ask <agent> <message>
```

Shell 备选：

```bash
command ask "$TARGET" <<'EOF'
$MESSAGE
EOF
```

- 提交一次后停止；除非被要求做诊断，否则不要 `pend` / `watch` / `ping`。
- 当前正在执行 CCB ask 任务时，需要子结果才能完成则用 `ask --callback`。
- 仅在结果不需要被父任务等待时使用 `ask --silence`。
- 在活动 ask 任务中嵌套发起 plain `ask` 会被 CCB 拒绝。

## Workspace Boundaries

- 项目文档、需求、规划、CCB 协调全部在 `/Users/leel/my_work/cpr_副本/`。
- 应用代码同样位于 `/Users/leel/my_work/cpr_副本/`（与文档同目录，原型阶段共存）。
- 所有 agent 在该目录下读写；委派代码任务时显式指明该工作目录。
- 在选择 TUI 技术栈和实现语言之前，不在该目录下创建大量代码骨架。

## Team Roles

- Claude（ccb_self）是协调者：规划、任务分解、CCB 任务分派、结果整合、代码评审、最终验证判定。
- `archi` 是架构与最终验收评审者。
- `agent1 (claude) + agent2 (opencode)` 是默认第一开发对。
- `agent3 (codex) + agent4 (kiro-cli)` 是更大任务或独立验证的第二开发对。

## Delegation Rules

- 用 CCB `ask` 进行任务分派与协作。
- 每个委派任务包含：目标、工作目录、文件或范围、约束、期望输出、验证命令、回调需求、禁止重叠。
- 优先成对开发，避免孤立实现。
- 小任务只用 `agent1 + agent2`。
- 文件边界与依赖清晰时才同时启用两个开发对。
- 不要让两对 agent 并发编辑同一批文件。

## Project Management Loop

- 需求讨论记录在 `docs/04-会议记录/`。
- 需求定稿后把关键规划决策写入 `docs/03-项目规划/`。
- 规划拆分为 `任务分解.md` 与 `滚动执行列表.md`。
- 实现前写或更新接口契约与验收标准（`docs/02-系统设计/`）。
- 把任务派发给开发对，并附构建与测试期望。
- 测试或验证负责人把验收报告写入 `docs/05-验收反馈/`。
- `archi` 做最终验收、代码评审、契约符合度与合并就绪度判定。
- 通过后按项目策略和用户授权提交或合并，再从滚动列表拉下一项。

## Change Intake and Priority Rules

- Bug、新需求、遗漏边界、契约缺口及时记入 `docs/03-项目规划/变更与缺陷队列.md`。
- 包含：来源任务、描述、严重度、业务影响、受影响模块/契约、建议优先级、triage 负责人。
- 高优先级 Bug 或需求插入当前队列前部。
- 低优先级变更进入 backlog 或 `docs/06-待优化/`。
- 若变更使契约失效，回到需求讨论再继续实现。

## Contract, Test, and Acceptance Rules

- 契约定义：输入、输出、状态迁移、不变量、错误情况、兼容性约束、验收标准、测试义务。
- 测试与验收报告必须引用所验证的契约或需求。
- 命令树原型应有"token 追加/删除/导航/动态候选/slash command 解析"等核心交互的单元测试。
- 不引入 Playwright 或其他浏览器自动化（MVP 是 TUI/终端 UI，无浏览器）。

## Branch, Release, Tag, and Version Rules

- 分支归属与合并就绪条件需明确。
- 发布需记录证据、所含任务 ID、所含 commit、最终批准、release notes。
- 仅在最终验收通过后打 tag。
- 版本号格式：`YYYY.MM.<total_commit_count>`，年月取自发布日期，commit 数为发布 commit 时仓库总数。

## Environment and Secrets Rules

- 真实 `.env`、凭证、token、secret 不进入 git、文档、日志和 prompt。
- 用 `.env.example` 描述必需变量名。
- 缺失 secret 时向用户索取，不要伪造或暴露。

## Dependency Change Rules

- 依赖变更需说明：原因、影响环境、lockfile 评审、兼容性风险、验证命令、回滚方案。
- 现有项目工具能解决的问题不新增依赖。
- 对原型阶段尤其谨慎：在 TUI 库（prompt_toolkit / Textual / blessed）选型确定前不引入交互框架依赖。

## Incident and Blocker Escalation Rules

- 重复测试失败、CCB 通信问题、provider 故障、发布失败、需求冲突应升级。
- 记录：现象、影响、已尝试、当前负责人、需要决策、是否暂停/重试/重派/恢复 CCB 上下文/咨询用户。
- 重启或清除上下文之前先诊断 CCB 状态。
- 除非用户明确选择，否则避免清空记忆的重置路径（不要随手用 `ccb -n`）。

## Review Loop

- 评审失败时先把具体可执行反馈发回原开发对。
- 修复后重新执行验证。
- 直到通过评审或满足接管条件。

## Degrade and Takeover Rules

- 仅在以下情况 Claude 接管实现：agent 阻塞、反复评审失败、偏离需求、紧急小修、需要集中整合、用户明确要求。
- 接管前说明：原因、范围、已知风险、保留或替换的既有工作。
