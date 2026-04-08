# Remote Claude

**让终端里的 Claude Code / Codex CLI 会话，同时可在飞书中查看与操作。**

Remote Claude 通过 tmux 承载真实 CLI 会话，服务端负责 PTY + Socket / WebSocket 输出共享，让你可以在电脑终端继续工作，也能在手机飞书里查看进度、发送指令和接管会话。

## 核心能力

- **同一会话，多端共享**：终端与飞书共用同一 Claude/Codex 会话
- **本地 + 远程接入**：既支持本机 attach，也支持远程连接与控制
- **非侵入式集成**：基于 tmux、PTY 与 Socket 链路，不改 CLI 本身

## 快速开始

### 安装

```bash
npm install -g remote-claude
# 或
pnpm add -g remote-claude
# 或
curl -fsSL https://raw.githubusercontent.com/yyzybb537/remote_claude/main/scripts/install.sh | bash
```

首次运行会自动完成环境初始化；公开入口统一是 shell launcher（`remote-claude`、`cla`、`cl`、`cx`、`cdx`），项目 `.venv` 仅作内部运行时。

### 本地启动

```bash
cla
# 或
remote-claude start demo
remote-claude attach demo
```

- `remote-claude`：公开 CLI 主入口
- `cla` / `cl`：Claude 快捷启动
- `cx` / `cdx`：Codex 快捷启动

完整命令与参数见 [docs/cli-reference.md](docs/cli-reference.md)。

### 远程连接

```bash
remote-claude start demo --remote
remote-claude connect host:8765/demo --token <TOKEN>
```

远程连接、token、远程控制与保存连接配置，见 [docs/remote-connection.md](docs/remote-connection.md)。

## 飞书客户端

配置飞书机器人后，可在飞书中远程查看输出、发送命令和管理会话。

```bash
remote-claude lark start
remote-claude lark status
```

- 配置说明见 [docs/feishu-setup.md](docs/feishu-setup.md)
- 使用说明见 [docs/feishu-client.md](docs/feishu-client.md)

## 文档导航

- [CLI 参考](docs/cli-reference.md) — 完整命令、参数与示例
- [远程连接](docs/remote-connection.md) — 远程启动、attach、connect、token 与远程控制
- [配置说明](docs/configuration.md) — `settings.json`、`.env` 与连接配置
- [飞书配置](docs/feishu-setup.md) — 飞书机器人创建、权限与回调配置
- [飞书客户端](docs/feishu-client.md) — 飞书客户端启动、状态、日志与排障
- [Docker 测试](docs/docker-test.md) — npm 安装链路与容器回归测试
- [开发者指南](docs/developer.md) — 项目结构、开发命令、测试入口与约束

## 系统要求

- **操作系统**：macOS 或 Linux
- **依赖工具**：`tmux`
- **CLI 工具**：Claude CLI 或 Codex CLI
- **可选**：飞书企业自建应用
