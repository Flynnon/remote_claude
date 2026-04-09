# 配置说明

本文档只覆盖配置文件、环境变量与配置重置。命令用法请看 [CLI 参考](cli-reference.md)，飞书接入与远程连接请看对应专题文档。

## 配置文件位置

| 文件 | 用途 |
|------|------|
| `~/.remote-claude/settings.json` | 用户设置（启动器、卡片、会话等） |
| `~/.remote-claude/state.json` | 运行时状态（会话映射、飞书绑定） |
| `~/.remote-claude/.env` | 环境变量（飞书凭证等） |
| `~/.remote-claude/remote_connections.json` | 远程连接配置（host、port、token） |
| `~/.remote-claude/tokens/<session>.json` | 会话 Token（远程模式，权限 0600） |

## 配置放置原则

### 按文件职责

- `settings.json` 保存用户可长期保留的行为配置与默认值。
- `state.json` 保存运行时状态与可重建数据。
- `.env` 保存部署环境、外部系统接入和敏感配置入口。
- `remote_connections.json` 保存远程连接入口信息。
- `tokens/<session>.json` 保存单会话敏感 token。

### 按生命周期判断

- 需要随默认模板分发、并允许用户长期调整的配置，放 `settings.json`。
- 只在运行过程中产生、重启后可重新生成的内容，放 `state.json`。
- 依赖环境注入或不应直接写入通用配置文件的值，放 `.env`。
- 远程连接与会话令牌保持独立存储，不与通用用户配置混放。

## 配置文件结构（v1.1）

配置采用扁平化结构，层级不大于 2：

```json
{
  "version": "1.1",
  "launchers": [...],
  "card": { ... },
  "session": { ... },
  "notify": { ... },
  "ui": { ... }
}
```

### launchers - 启动器配置

定义可用的 CLI 启动器，用于启动会话。

```json
{
  "launchers": [
    {"name": "Claude", "cli_type": "claude", "command": "claude", "desc": "Claude Code CLI"},
    {"name": "Codex", "cli_type": "codex", "command": "codex", "desc": "OpenAI Codex CLI"}
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 启动器名称，用于 `--launcher` 参数 |
| `cli_type` | string | CLI 类型（claude/codex） |
| `command` | string | 实际执行的命令 |
| `desc` | string | 描述（可选） |

### card - 卡片展示配置

控制飞书卡片的展示行为。

#### 快捷命令配置

```json
{
  "card": {
    "quick_commands": [
      {"label": "清空对话", "value": "/clear", "icon": "🗑️"},
      {"label": "压缩上下文", "value": "/consume", "icon": "📦"},
      {"label": "退出会话", "value": "/exit", "icon": "🚪"},
      {"label": "帮助", "value": "/help", "icon": "❓"}
    ],
    "expiry_sec": 3600
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `quick_commands` | array | 快捷命令列表 |
| `quick_commands[].label` | string | 按钮显示文本 |
| `quick_commands[].value` | string | 点击后发送的命令（必须以 `/` 开头） |
| `quick_commands[].icon` | string | 按钮图标（emoji） |
| `expiry_sec` | number | 卡片过期时间（秒），默认 3600（1小时） |

卡片过期后自动创建新卡片，避免飞书卡片内容过长。

### session - 会话配置

控制会话启动和行为。

```json
{
  "session": {
    "bypass": false,
    "auto_answer_delay_sec": 10,
    "auto_answer_vague_patterns": [
      "继续执行", "继续", "开始执行", "开始", "执行",
      "continue", "确认", "OK"
    ],
    "auto_answer_vague_prompt": "[系统提示] 请使用工具执行下一步操作。如果不确定下一步，请明确询问需要做什么。不要只返回状态确认。"
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `bypass` | boolean | 是否绕过权限确认（默认 false） |
| `auto_answer_delay_sec` | number | 自动应答延迟时间（秒） |
| `auto_answer_vague_patterns` | array | 模糊指令列表，触发时使用 vague_prompt |
| `auto_answer_vague_prompt` | string | 模糊指令的系统提示 |

**自动应答策略：**
1. 优先选择标记为 `(recommended)` 或 `推荐` 的选项
2. 确认类选项回复"继续"
3. 兜底选择第一项

### notify - 通知配置

```json
{
  "notify": {
    "ready": true,
    "urgent": false
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `ready` | boolean | 是否启用就绪通知 |
| `urgent` | boolean | 是否启用紧急通知 |

### ui - UI 配置

```json
{
  "ui": {
    "show_builtin_keys": true,
    "enabled_keys": ["up", "down", "ctrl_o", "shift_tab", "esc", "shift_tab_x3"]
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `show_builtin_keys` | boolean | 是否显示内置快捷键 |
| `enabled_keys` | array | 启用的快捷键列表 |

## 环境变量配置

在 `~/.remote-claude/.env` 中配置：

```bash
# === 必填 ===
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret

# === 可选（默认样例只列主变量名，旧变量名仍兼容） ===
ENABLE_USER_WHITELIST=false
ALLOWED_USERS=user1,user2
GROUP_NAME_PREFIX=【Remote-Claude】
LARK_LOG_LEVEL=WARNING
MAX_CARD_BLOCKS=50
LARK_NO_PROXY=0

# 兼容旧变量名：
# USER_WHITELIST / GROUP_PREFIX / LOG_LEVEL / NO_PROXY
```

默认模板只展示当前主变量名；旧变量名（如 `USER_WHITELIST`、`GROUP_PREFIX`、`LOG_LEVEL`、`NO_PROXY`）仅作为兼容读取别名保留。

| 配置项 | 说明 |
|--------|------|
| `FEISHU_APP_ID` | 飞书应用 ID（必填） |
| `FEISHU_APP_SECRET` | 飞书应用密钥（必填） |
| `ENABLE_USER_WHITELIST` | 是否启用用户白名单（true/false） |
| `ALLOWED_USERS` | 用户白名单（逗号分隔） |
| `GROUP_NAME_PREFIX` | 群聊名称前缀 |
| `LARK_LOG_LEVEL` | 飞书客户端日志级别（DEBUG/INFO/WARNING/ERROR） |
| `MAX_CARD_BLOCKS` | 单张卡片最大 block 数 |
| `LARK_NO_PROXY` | 检测到 SOCKS 代理时是否绕过（0/1） |

## 配置重置

```bash
# 交互式重置
remote-claude config reset

# 重置所有配置（包括运行时状态）
remote-claude config reset --all

# 仅重置用户配置
remote-claude config reset --settings

# 仅重置运行时状态
remote-claude config reset --state
```

## 配置示例

### 完整配置示例

```json
{
  "version": "1.1",
  "launchers": [
    {"name": "Claude", "cli_type": "claude", "command": "claude", "desc": "Claude Code CLI"},
    {"name": "Codex", "cli_type": "codex", "command": "codex", "desc": "OpenAI Codex CLI"}
  ],
  "card": {
    "quick_commands": [
      {"label": "清空对话", "value": "/clear", "icon": "🗑️"},
      {"label": "压缩上下文", "value": "/consume", "icon": "📦"},
      {"label": "退出会话", "value": "/exit", "icon": "🚪"},
      {"label": "帮助", "value": "/help", "icon": "❓"}
    ],
    "expiry_sec": 3600
  },
  "session": {
    "bypass": false,
    "auto_answer_delay_sec": 10,
    "auto_answer_vague_patterns": [
      "继续执行", "继续", "开始执行", "开始", "执行",
      "continue", "确认", "OK"
    ],
    "auto_answer_vague_prompt": "[系统提示] 请使用工具执行下一步操作。如果不确定下一步，请明确询问需要做什么。不要只返回状态确认。"
  },
  "notify": {
    "ready": true,
    "urgent": false
  },
  "ui": {
    "show_builtin_keys": true,
    "enabled_keys": ["up", "down", "ctrl_o", "shift_tab", "esc"]
  }
}
```

### 最小配置示例

```json
{
  "version": "1.1",
  "launchers": [
    {"name": "Claude", "cli_type": "claude", "command": "claude"}
  ]
}
```
