# CPR

CPR 是当前工作代号：Command Prompt Runner / Command Path Recommender / Command Pilot Runtime。

项目目标是做一个面向命令行工具的交互式命令工作台：用户始终在一个主输入区里构造或执行真实命令，界面在同一窗口内根据当前命令层级展示说明、可选下一段、执行结果和 AI 辅助。

## MVP（T-001）使用说明

> 当前阶段为 SDKMAN MVP 原型。仅在 macOS / Linux 上验证；Windows 暂不支持，启动时会直接拒绝。

### 安装

```bash
python -m pip install -e ".[dev]"
```

要求 Python 3.11+。本仓库只引入 prompt_toolkit / pyyaml / pytest / pytest-asyncio，不依赖 textual / rich / click / pty。

### 启动

```bash
python -m cpr                       # 进入交互式命令工作台
python -m cpr --check-tree          # 仅校验 data/sdkman.yaml 结构
python -m cpr --slash-parse "/ai 帮我安装 Java 17 LTS"
```

启动时会在 `stderr` 打印日志路径 `~/.cpr/logs/cpr.log`（按 archi 评审约束 warn 起记）。

### 界面分区

```
cpr> sdk list java                ← 输入区（始终聚焦）
──────────────────────────────────
CPR 命令工作台                     ← 内容区（说明 + 执行结果）
...
──────────────────────────────────
候选 :: sdk list java              ← 候选区（不接管焦点）
▶ <下一段 token>  说明  [static]
locale=zh-CN  node=sdk.list.java  log=~/.cpr/logs/cpr.log   ← 状态栏
```

### 键位

| 键位 | 行为 |
| --- | --- |
| 字符输入 | 在主输入区构造 token 或 slash 命令 |
| Enter | 当前节点可执行 → 执行；否则若有候选选中 → 追加 token |
| Backspace | 输入区为空时弹出最末 token；非空走普通字符删除 |
| Esc | 输入区非空 → 清空；输入区为空 → 弹出最末 token |
| Tab | 接受当前选中候选（追加为 token） |
| ↑ / ↓ | 在候选区上下移动选中项（不切换焦点） |
| Ctrl+C / Ctrl+D | 退出 |

Slash 命令（MVP 内置）：`/help` `/back` `/clear` `/ai` `/explain` `/fix`。其中 `/ai` `/explain` `/fix` 在 MVP 走 mock provider，留待 T-003 接真实 LLM。

### 多语言

启动时按以下顺序解析 locale：

1. 环境变量 `CPR_LOCALE`（推荐：`zh-CN` 或 `en-US`）
2. 用户配置（后续阶段引入）
3. 系统 `LANG`
4. 默认 `en-US`

```bash
CPR_LOCALE=zh-CN python -m cpr
CPR_LOCALE=en-US python -m cpr
```

缺失的节点文案会在日志中告警并 fallback 到 `en-US` 或 `zh-CN`。当前 `data/sdkman.yaml` 中 zh-CN 文案已完整，en-US 仍是占位文案，将在 T-002 完成。

### 平台支持

- ✅ macOS（ARM64 / x86_64）
- ✅ Linux（Ubuntu ARM64 / x86_64）
- ❌ Windows：MVP 不支持，启动时会以非零退出码拒绝。

### SDKMAN 注意事项

- `sdk` 是 shell function，不是普通二进制。
- 所有 SDKMAN 命令通过 `bash -lc 'source ~/.sdkman/bin/sdkman-init.sh && <command>'` 调用；`SDKMAN_DIR` 环境变量优先于默认路径。
- 没有安装 SDKMAN 的环境下，构造与回退仍可工作，仅执行步骤会失败并保留 stderr。

### 验证

```bash
pytest -q
pytest --cov=cpr.core --cov-fail-under=85
python -m cpr --check-tree
bash scripts/manual_sdk_smoke.sh   # 手工 SDKMAN 冒烟（macOS / Ubuntu ARM64）
```

## 文档索引

- [产品功能详细描述](docs/01-需求分析/产品功能详细描述.md)
- [接口契约](docs/02-系统设计/2026-06-19-接口契约.md)
- [契约逻辑与验收标准](docs/02-系统设计/2026-06-19-契约逻辑与验收标准.md)
- [契约评审 - archi](docs/02-系统设计/2026-06-19-契约评审-archi.md)
- [任务规划](docs/03-项目规划/任务规划.md)
- [角色分工](docs/03-项目规划/角色分工.md)
- [循环验证方案](docs/05-验收反馈/2026-06-19-循环验证方案.md)
- [命名讨论](docs/01-需求分析/命名讨论.md)
