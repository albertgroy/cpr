# cpr — AI 起手式 CLI

> 让 AI 替你写命令的"起手式"。

`cpr <tool> [args …]` 抓取 `<tool> [子] --help`，让 server 端的 LLM 把它解析成"该怎么用"，再把
[1] 命令头 / [2] 一句话总结 / [3] 用法 / [4] 候选 / [5] 备注 / [6] 危险确认  这一段渲染回终端。
危险动作（`result.danger=true`）默认显示 y/N 确认提示，**默认答案为 N**，回车即取消。

形态 B 完整需求见 [`docs/01-需求分析/2026-06-19-形态-B-需求.md`](docs/01-需求分析/2026-06-19-形态-B-需求.md)，协议（schema_version `"1"` 已冻结）见 [`docs/02-系统设计/2026-06-19-AI起手式-架构与协议.md`](docs/02-系统设计/2026-06-19-AI起手式-架构与协议.md)。

## 安装

```bash
python -m pip install -e ".[dev]"
```

> 需要 Python ≥ 3.11。安装会注册控制台脚本 `cpr`，等价于 `python -m cpr.cli.main`。

## 起一个本地 mock server

官方 server 还没上线时，本地 mock 即可串通整条链路：

```bash
python scripts/mock_server.py 18888    # 监听 127.0.0.1:18888
```

正式形态 cpr **内置 server endpoint，无需配置**。开发 / 自部署期需要切换时，
在 `~/.cpr/config` 里加一段（注意：`endpoint` 是 base URL，**不带 `/resolve` 后缀**）：

```bash
mkdir -p ~/.cpr
cat > ~/.cpr/config <<'EOF'
server:
  endpoint: http://127.0.0.1:18888
  timeout_seconds: 5
client:
  help_timeout_seconds: 2
  locale: auto
  confirm_danger: always
EOF
```

> 旧版 config 里写的 `endpoint: http://.../resolve` 仍可工作：client 会自动剥掉
> 尾部 `/resolve` 并在 stderr 打一行 deprecated 提示。新配置请直接用 base URL。

mock server 还内置了 5 个特殊 tool 用来触发错误码：

| 输入 | 触发的错误码 |
| ---- | ------------ |
| `cpr __quota`            | `QUOTA_EXCEEDED` |
| `cpr __timeout`          | `LLM_TIMEOUT` |
| `cpr __server_error`     | `SERVER_ERROR` |
| `cpr __invalid_template` | `INVALID_TEMPLATE` |
| `cpr __schema_mismatch`  | `SCHEMA_MISMATCH` |

## 5 条代表性命令

```bash
cpr sdk                       # 顶层概要
cpr sdk install java          # 子命令 + 候选
cpr git status                # 跨工具
cpr unknown-tool-xxx          # 错误路径，退出码 2
cpr sdk install java <id>     # 危险确认 y/N（默认 N）
```

每条的输出形如（以 `cpr sdk install java` 为例）：

```text
$ sdk install java
Install Java with SDKMAN
用法: sdk install java <identifier>
候选:
  TOKEN        TYPE  DESCRIPTION
  ---------------------------------
  17.0.10-tem  标识  Temurin 17 LTS
备注:
  - Downloads and writes into ~/.sdkman.
危险：writes to SDKMAN directories
确认执行？(y/N)
```

直接回车 / 输入 `n` / EOF（Ctrl-D）都视为不执行，退出码 0；输入 `y` 才走 executor 跑真命令。

## `~/.cpr/config` 字段

YAML，按协议 §6 定义：

| 字段 | 默认 | 含义 |
| ---- | ---- | ---- |
| `server.endpoint`            | 内置（代码默认） | `/resolve` / `/quota` 的 base URL，**不带 `/resolve` 后缀**；正式形态无需配置，自部署或 dev 时覆盖 |
| `server.timeout_seconds`     | `5` | server 请求超时；超时 → `LLM_TIMEOUT` |
| `client.help_timeout_seconds`| `2` | `<tool> --help` 抓取超时；超时 → `HELP_TIMEOUT` |
| `client.locale`              | `auto` | `auto` / `zh-CN` / `en-US`；`auto` 时按 `CPR_LOCALE` > `LANG` > `en-US` 解析 |
| `client.confirm_danger`      | `always` | `always`（每次确认） / `once`（同会话同 `(tool, sub_path)` 仅首次确认；不持久化） / `never`（≡ `--yes`） |
| `cache.dir`                  | `~/.cpr/cache` | 本地缓存目录（sqlite） |
| `client.id`                  | 自动生成 UUIDv4 | 缺失或非法 → `INVALID_CLIENT`，删掉本字段让 cpr 重新生成 |

环境变量 `CPR_HOME` 可整体改写 `~/.cpr` 路径；`CPR_LOCALE` 一次性强制 locale；`NO_COLOR=1` 关闭 ANSI 输出。

## 退出码（协议 §2.1）

| 退出码 | 含义 | 对应错误码 |
| ------ | ---- | ---------- |
| 0 | 渲染成功 / 危险确认时选 N | — |
| 2 | 工具识别 / help 抓取失败（client-only） | `HELP_NOT_FOUND`、`HELP_TIMEOUT` |
| 3 | 暂时性故障，可重试 | `LLM_TIMEOUT`、`SERVER_ERROR`、`NETWORK_UNREACHABLE` |
| 4 | 配额耗尽 | `QUOTA_EXCEEDED` |
| 5 | 协议或模板违法（不重试） | `BAD_REQUEST`、`INVALID_CLIENT`、`INVALID_TEMPLATE`、`SCHEMA_MISMATCH`、`LLM_PARSE_FAILED` |

> 协议新增错误码会被旧 client 兜底为退出码 5。

## 开发

```bash
pytest -q                                  # 全量单测
pytest --cov=cpr.cli --cov-fail-under=85   # 覆盖门槛
bash scripts/manual_sdk_smoke.sh           # 手工冒烟（5 条命令 + mock）
```

实施部署细节见 [`docs/04-实施部署/2026-06-19-T-002b-client-实施.md`](docs/04-实施部署/2026-06-19-T-002b-client-实施.md)。
