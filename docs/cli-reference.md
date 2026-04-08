# CLI 命令参考

Remote Claude 提供完整的命令行工具，用于管理 Claude/Codex 会话。

## 快捷命令

`remote-claude` 是公开 CLI 主入口，`cla`、`cl`、`cx`、`cdx` 是面向常用场景的快捷启动脚本。

| 命令 | 说明 | 权限模式 |
|------|------|---------|
| `cla` | 启动 Claude 会话 | 默认权限模式 |
| `cl` | 启动 Claude 会话 | 跳过权限确认 |
| `cx` | 启动 Codex 会话 | 跳过权限确认 |
| `cdx` | 启动 Codex 会话 | 默认权限模式 |

```bash
cla        # 在当前目录启动 Claude 会话（会话名：当前目录路径+时间戳）
cl         # 启动 Claude，并跳过权限确认
cx         # 在当前目录启动 Codex，会跳过权限确认
cdx        # 在当前目录启动 Codex，使用默认权限模式
```

如果需要稳定的会话名、从其他终端复用同一会话，或执行远程/清理类操作，优先使用主命令。

## 主命令

### start - 启动会话

```bash
remote-claude start <会话名> [选项] [cli_args ...]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `-l`, `--launcher <name>` | 启动器名称（对应 `settings.launchers[].name`），不指定则使用第一个 |
| `--debug-screen` | 写入 pyte 屏幕快照调试日志 |
| `--debug-verbose` | 输出完整调试诊断信息 |
| `--remote` | 启用远程连接模式 |
| `--remote-port <port>` | 远程连接端口，默认 8765 |
| `--remote-host <host>` | 远程连接监听地址，默认 `0.0.0.0` |

**示例**：
```bash
# 启动本地会话
remote-claude start my-session

# 启动远程会话
remote-claude start my-session --remote --remote-port 8765

# 指定启动器
remote-claude start my-session --launcher Codex
```

### attach - 连接会话

```bash
remote-claude attach [会话名] [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `--remote` | 远程连接模式 |
| `--host <host>` | 远程服务器地址，支持 `host:port` 或 `host:port/session` |
| `--port <port>` | 远程服务器端口，默认 8765 |
| `--token <token>` | 连接 Token |
| `--save` | 保存连接配置 |
| `--config-name <name>` | 使用或保存的配置名称，默认 `default` |

**示例**：
```bash
# 本地连接
remote-claude attach my-session

# 远程连接
remote-claude attach my-session --remote --host example.com:8765 --token xxx

# 保存配置
remote-claude attach my-session --remote --host example.com:8765 --token xxx --save
```

### list - 列出会话

```bash
remote-claude list [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `--full` | 显示完整名称（不截断） |
| `--remote` | 远程连接模式 |
| `--host <host>` | 远程服务器地址 |
| `--port <port>` | 远程服务器端口，默认 8765 |
| `--token <token>` | 连接 Token |

### kill - 终止会话

```bash
remote-claude kill <会话名> [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `--remote` | 远程连接模式 |
| `--host <host>` | 远程服务器地址 |
| `--port <port>` | 远程服务器端口，默认 8765 |
| `--token <token>` | 连接 Token |

### status - 查看状态

```bash
remote-claude status <会话名> [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `--remote` | 远程连接模式 |
| `--host <host>` | 远程服务器地址 |
| `--port <port>` | 远程服务器端口，默认 8765 |
| `--token <token>` | 连接 Token |

### config - 配置管理

```bash
remote-claude config reset [选项]
```

当前公开的 `config` 子命令仅包含 `reset`。

**选项**：
| 选项 | 说明 |
|------|------|
| `--all` | 重置全部配置（`settings.json` + `state.json`） |
| `--settings` | 仅重置用户配置（`settings.json`） |
| `--state` | 仅重置运行时配置（`state.json`） |

**示例**：
```bash
# 重置用户配置
remote-claude config reset --settings

# 重置全部配置
remote-claude config reset --all

# 仅重置运行时状态
remote-claude config reset --state
```

### connection / conn - 连接配置管理

```bash
remote-claude connection <子命令>
remote-claude conn <子命令>
```

**子命令**：
| 子命令 | 说明 |
|--------|------|
| `list` | 列出所有保存的配置 |
| `show <name>` | 查看配置详情 |
| `set-default <name>` | 设置默认连接配置 |
| `delete <name>` | 删除配置 |

如果不带子命令，默认执行 `list`。

### connect - 连接远程会话

```bash
remote-claude connect <host>:<port>/<session> --token <token>
```

也支持把会话名作为第二个位置参数传入：

```bash
remote-claude connect <host> <session> --token <token> [--port <port>]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `--token <token>` | 连接 token |
| `--port <port>` | 远程端口；当 host 未内联端口时使用 |

### token - 查看会话 token

```bash
remote-claude token <session> [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `--remote` | 远程模式 |
| `--host <host>` | 远程主机 |
| `--port <port>` | 远程端口 |
| `--token <token>` | 连接 token |

### regenerate-token - 刷新会话 token

```bash
remote-claude regenerate-token <session> [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `--remote` | 远程模式 |
| `--host <host>` | 远程主机 |
| `--port <port>` | 远程端口 |
| `--token <token>` | 连接 token |

### remote - 远程控制

```bash
remote-claude remote <shutdown|restart|update> <host> [session] --token <token> [--port <port>]
```

`<host>` 支持直接写成 `host:port/session`。

### stats - 使用统计

```bash
remote-claude stats [选项]
```

**选项**：
| 选项 | 说明 |
|------|------|
| `--range <RANGE>` | 时间范围：`today`（默认）、`7d`、`30d`、`90d` |
| `--detail` | 显示详细分类 |
| `--session <NAME>` | 按会话名筛选 |
| `--reset` | 清空所有统计数据 |
| `--report` | 立即触发 Mixpanel 聚合上报 |

### update - 更新版本

```bash
remote-claude update
```

更新到最新版本。

### uninstall - 卸载清理

```bash
remote-claude uninstall [选项]
```

清理本地数据并提示后续的 npm/pnpm 卸载命令。

**选项**：
| 选项 | 说明 |
|------|------|
| `-y`, `--yes` | 跳过确认，直接执行清理 |

## 飞书客户端管理

### lark - 飞书客户端命令

```bash
remote-claude lark <子命令>
```

**子命令**：
| 子命令 | 说明 |
|--------|------|
| `start` | 启动飞书客户端 |
| `stop` | 停止飞书客户端 |
| `restart` | 重启飞书客户端 |
| `status` | 查看飞书客户端状态 |

## 飞书机器人命令

在飞书中与机器人对话时可用：

| 命令 | 说明 |
|------|------|
| `/attach <会话名>` | 连接到会话 |
| `/detach` | 断开会话连接 |
| `/list` | 列出所有会话 |
| `/help` | 显示帮助信息 |

## 全局选项

| 选项 | 说明 |
|------|------|
| `--help` | 显示帮助信息 |
| `--version`, `-V` | 显示版本号 |

## 退出码

| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 一般错误 |
| 2 | 参数错误 |
| 130 | 用户中断（Ctrl+C） |

## 相关文档

- [配置说明](./configuration.md)
- [远程连接说明](./remote-connection.md)
- [飞书客户端管理](./feishu-client.md)
