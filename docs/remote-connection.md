# 远程连接说明

Remote Claude 支持通过 WebSocket 远程连接会话，实现跨网络的操作能力。

## 概述

远程连接功能允许你：
- 在远程服务器上运行 Claude/Codex 会话
- 从本地终端连接并操作远程会话
- 通过飞书客户端远程管理会话

## 架构

```
远程服务器                              本地客户端
┌─────────────────┐                   ┌─────────────────┐
│ Claude/Codex    │                   │ 本地终端        │
│ (PTY)           │                   │ (attach)        │
└────────┬────────┘                   └────────┬────────┘
         │                                     │
    ┌────┴────┐                          ┌─────┴─────┐
    │ server  │◄─── WebSocket ──────────►│  client   │
    │ (8765)  │       (--token)           │ (remote)  │
    └─────────┘                          └───────────┘
```

## 公开入口约定

远程连接的公开入口分为两类：
- `remote-claude start <session> --remote`：在远端启动并暴露可连接的会话
- `remote-claude attach ... --remote` / `remote-claude connect ...`：从另一端连接远程会话
- `remote-claude token <session>`：查看当前会话 token（支持本地与远程模式）
- `remote-claude regenerate-token <session>`：刷新当前会话 token（支持本地与远程模式）
- `remote-claude remote <action> ...`：执行远程控制动作（`shutdown` / `restart` / `update`）

其中 `remote-claude` 是公开 CLI 主入口；`cla`、`cl`、`cx`、`cdx` 仍是本地启动快捷脚本，不承担远程管理职责。

## 启动远程会话

### 基本启动

```bash
remote-claude start <session> --remote
```

启动后会输出连接所需的信息；远程连接时需要显式传入 `--token` 完成认证。

### 自定义端口和地址

```bash
remote-claude start <session> --remote --remote-port 8765 --remote-host 0.0.0.0
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--remote-port` | WebSocket 端口 | 8765 |
| `--remote-host` | 监听地址 | 0.0.0.0 |

## 连接远程会话

### 标准连接

```bash
remote-claude attach <session> --remote --host <host> --token <token>
```

### 支持 host:port 格式

```bash
remote-claude attach <session> --remote --host <host>:<port> --token <token>
```

### 省略 session 参数

```bash
remote-claude attach --remote --host <host>:<port>/<session> --token <token>
```

### 使用 connect 命令

```bash
remote-claude connect <host>:<port>/<session> --token <token>
```

也支持把会话名作为第二个位置参数传入：

```bash
remote-claude connect <host> <session> --token <token> [--port <port>]
```

## 保存连接配置

避免每次输入 host、port、token：

### 保存配置

```bash
# 保存连接配置（默认名称: default）
remote-claude attach <session> --remote --host <host> --token <token> --save

# 保存为自定义名称
remote-claude attach <session> --remote --host <host> --token <token> --save --config-name myserver
```

### 使用保存的配置

```bash
# 使用默认配置连接
remote-claude attach --remote

# 使用指定配置连接
remote-claude attach --remote --config-name myserver
```

### 管理连接配置

```bash
# 列出所有保存的配置
remote-claude connection list

# 查看配置详情
remote-claude connection show <name>

# 设置默认连接配置
remote-claude connection set-default <name>

# 删除配置
remote-claude connection delete <name>
```

## 远程管理命令

### 会话管理

```bash
# 列出会话
remote-claude list --remote --host <host> --token <token>

# 终止会话
remote-claude kill <session> --remote --host <host> --token <token>

# 查看状态
remote-claude status <session> --remote --host <host> --token <token>
```

### token 与远程控制

```bash
# 查看当前会话 token
remote-claude token <session>

# 远程模式下查看会话 token
remote-claude token <session> --remote --host <host> --token <token>

# 刷新当前会话 token
remote-claude regenerate-token <session>

# 远程控制动作
remote-claude remote <shutdown|restart|update> <host>:<port>/<session> --token <token>
```

### 飞书客户端管理

远程控制链路也支持管理目标机会话绑定的飞书客户端：

```bash
# 远程启动飞书客户端
remote-claude lark start --remote --host <host> --token <token>

# 远程停止飞书客户端
remote-claude lark stop --remote --host <host> --token <token>

# 远程查看飞书客户端状态
remote-claude lark status --remote --host <host> --token <token>
```

这些命令会通过远程控制链路转发到目标机器；本地快捷脚本 `cla`、`cl`、`cx`、`cdx` 不承担远程管理职责。

## 排障指南

### 查看启动日志

远程模式启动失败时，查看启动日志：

```bash
cat ~/.remote-claude/startup.log
```

**关键追溯字段**：
- `stage=server_spawn`：启动参数摘要
- `stage=server_start_failed`：失败阶段与原因
- `server_cmd_sanitized=...`：脱敏后的完整 server 启动命令

### 排查顺序

1. 先定位 `stage=server_start_failed` 的 `reason`
2. 再对照 `stage=server_spawn` 中的 `remote_host/remote_port`
3. 最后检查 `server_cmd_sanitized` 是否符合预期启动命令

### 常见问题

#### 连接超时

**可能原因**：
- 防火墙阻止了端口
- 服务未启动
- 网络不通

**解决方案**：
```bash
# 检查端口是否开放
telnet <host> <port>

# 检查服务是否运行
remote-claude status <session>
```

#### Token 认证失败

**可能原因**：
- 连接时使用了错误的 Token
- 保存的连接配置已过期

**解决方案**：
```bash
# 使用最新 Token 重新连接
remote-claude attach <session> --remote --host <host> --token <token>
```

#### 连接断开

**可能原因**：
- 网络不稳定
- 服务器重启
- 会话被终止

**解决方案**：
```bash
# 检查会话状态
remote-claude status <session> --remote --host <host> --token <token>

# 重新连接
remote-claude attach <session> --remote --host <host> --token <token>
```

## 安全建议

1. **连接凭证保护**：
   - 不要分享用于远程连接的 Token
   - 在远程会话重建后同步更新连接方使用的 Token
   - 使用 HTTPS/WSS 加密传输

2. **网络隔离**：
   - 使用防火墙限制访问 IP
   - 通过 VPN 或内网访问
   - 避免公网暴露

3. **权限控制**：
   - 不再使用的保存连接配置应及时删除

## 配置文件

远程连接定义存储在 `~/.remote-claude/settings.json` 的 `remote` 段中；`~/.remote-claude/remote_connections.json` 仅作为历史版本的自动迁移来源，不再是正式配置入口。

示例：

```json
{
  "version": "1.1",
  "remote": {
    "default_connection": "default",
    "connections": {
      "default": {
        "name": "default",
        "host": "example.com",
        "port": 8765,
        "token": "your_token_here"
      },
      "myserver": {
        "name": "myserver",
        "host": "192.168.1.100",
        "port": 8765,
        "token": "another_token"
      }
    }
  }
}
```

**注意事项**：
- 文件权限自动设置为 0600
- 保存的是远程连接所需凭证，建议按需更新
- 不要将此文件提交到版本控制

## 相关文档

- [CLI 命令参考](./cli-reference.md)
- [配置说明](./configuration.md)
- [飞书客户端管理](./feishu-client.md)
