# 飞书客户端管理指南

本指南介绍如何使用 Remote Claude 的飞书客户端管理功能。

## 快速开始

### 启动飞书客户端

```bash
remote-claude lark start
```

如需在某个会话中使用 Codex 启动器，可先这样启动会话：

```bash
remote-claude start my-session --launcher Codex
```

**输出示例：**
```
正在启动飞书客户端...
✓ 飞书客户端已启动
  PID: 12345
  日志: ~/.remote-claude/lark_client.log

使用 'remote-claude lark status' 查看状态
使用 'remote-claude lark stop' 停止
```

**特性：**
- 后台运行，关闭终端后进程继续运行
- 日志默认写入 `~/.remote-claude/lark_client.log`
- 进程异常会记录到日志，便于排障

## 运行状态与文件

### 查看运行状态

```bash
remote-claude lark status
```

### 状态文件

飞书客户端运行时会使用以下运行时文件：

| 文件路径 | 说明 | 格式 |
|---------|------|------|
| `/tmp/remote-claude/lark.pid` | 进程 PID | 纯文本，一行 |
| `/tmp/remote-claude/lark.status` | 状态信息 | JSON 格式 |
| `~/.remote-claude/lark_client.log` | 运行日志 | 纯文本，追加写入 |

## 日志查看

```bash
tail -f ~/.remote-claude/lark_client.log
tail -50 ~/.remote-claude/lark_client.log
grep ERROR ~/.remote-claude/lark_client.log
```

## 职责边界

- `lark_client/` 只负责飞书卡片展示、交互和共享状态消费。
- Lark 侧不做 ANSI 清理；ANSI 解析、富文本渲染、终端输出整理由服务端输出链路负责。
- 若飞书显示异常，优先检查 `server/` 输出链路，而不是在 Lark 侧打补丁。

## 常见操作

### 停止飞书客户端

```bash
remote-claude lark stop
```

优先使用该命令完成优雅停止与清理；不要把手工删除 `/tmp/remote-claude/lark.pid` 或 `/tmp/remote-claude/lark.status` 作为常规操作。

### 重启飞书客户端

```bash
remote-claude lark restart
```

### 重新查看状态

```bash
remote-claude lark status
```

## 常见问题

### 启动失败

```bash
tail -20 ~/.remote-claude/lark_client.log
remote-claude lark status
```

重点检查：
- `~/.remote-claude/.env` 是否存在且配置正确
- 飞书应用权限是否已按 `docs/feishu-setup.md` 完成配置
- 当前 Python/uv 依赖是否安装完整

### 进程异常退出

```bash
cat ~/.remote-claude/lark_client.log
uv run python3 -m lark_client.main
```

### 日志过大

```bash
remote-claude lark stop
mv ~/.remote-claude/lark_client.log ~/.remote-claude/lark_client.log.$(date +%Y%m%d_%H%M%S)
remote-claude lark start
```

## 获取帮助

- 仓库说明：[`README.md`](../README.md)
- 飞书配置：[`feishu-setup.md`](./feishu-setup.md)
- 开发边界：[`developer.md`](./developer.md)
