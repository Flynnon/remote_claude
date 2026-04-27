# 飞书机器人配置教程

本教程介绍如何通过配置向导完成 Remote Claude 的飞书端接入，并按当前实现所需的最小权限集完成开放平台配置。

## 前提条件

- 已安装并配置好 Remote Claude
- 本机可运行 `remote-claude` 命令
- 具备目标飞书应用的配置权限

## 推荐方式：使用配置向导

推荐直接运行：

```bash
remote-claude lark init
```

向导会依次完成以下流程：

1. 扫码创建飞书应用
2. 校验 App ID / App Secret 是否有效
3. 打开应用身份权限开通页面
4. 通过 OAuth device flow 引导用户身份授权
5. 引导创建版本并发布应用
6. 将凭证写入 `~/.remote-claude/.env`

完成后可使用以下命令复查配置状态：

```bash
remote-claude lark init --check
```

## 向导外你需要确认的开放平台配置

虽然向导会帮助打开关键页面，但以下配置仍需要你在飞书开放平台中确认。

### 1. 启用机器人能力

在应用后台启用「机器人」能力。

### 2. 配置事件订阅

当前实现使用**长连接接收事件**模式，不需要公网 webhook 地址。

需要开启以下事件：

- `im.message.receive_v1`
- `card.action.trigger`

### 3. 开通最小权限集

在「权限管理」页面申请以下最小权限：

- `cardkit:card:write`
- `contact:contact.base:readonly`
- `contact:user.base:readonly`
- `contact:user.employee_id:readonly`
- `contact:user.id:readonly`
- `im:chat.managers:write_only`
- `im:chat.members:read`
- `im:chat.members:write_only`
- `im:chat.tabs:read`
- `im:chat.tabs:write_only`
- `im:chat.top_notice:write_only`
- `im:chat:create`
- `im:chat:delete`
- `im:chat:operate_as_owner`
- `im:chat:read`
- `im:chat:update`
- `im:message.group_at_msg:readonly`
- `im:message.group_msg`
- `im:message.p2p_msg:readonly`
- `im:message.reactions:read`
- `im:message.reactions:write_only`
- `im:message.urgent`
- `im:message.urgent.status:write`
- `im:message:readonly`
- `im:message:recall`
- `im:message:send_as_bot`
- `im:message:update`
- `im:message:urgent_app`
- `im:resource`

其中：

- OAuth 用户授权会预选其中用于 device flow 的权限，并额外申请 `offline_access`
- 应用身份权限开通链接会包含 tenant scope 所需权限
- 手工 checklist 以当前实现实际依赖的最小权限集为准

### 4. 创建版本并发布应用

应用未发布前，飞书侧无法正常搜索和使用该机器人。

## 检查配置是否生效

运行：

```bash
remote-claude lark init --check
```

检查逻辑包括：

1. `~/.remote-claude/.env` 中是否存在 `FEISHU_APP_ID` 与 `FEISHU_APP_SECRET`
2. 应用凭证是否能正常换取 `tenant_access_token`
3. 是否能够获取机器人信息

如果检查失败，向导会重新打印需要补齐的开放平台配置项。

## 启动飞书客户端

```bash
remote-claude lark start
```

常用辅助命令：

```bash
remote-claude lark status
remote-claude lark stop
```

## 常见问题

### `remote-claude lark init --check` 失败

优先检查：

1. `.env` 中的 App ID / App Secret 是否正确
2. 机器人能力是否已启用
3. 事件订阅是否已切换为长连接模式并添加所需事件
4. 应用是否已经发布
5. 权限是否覆盖了上面的最小权限集

### 飞书里搜不到机器人

通常是因为应用尚未发布，或者发布流程未完成。

### 消息或卡片能力异常

通常是权限不完整，或事件订阅未正确配置。建议重新执行：

```bash
remote-claude lark init --check
```

## 安全建议

1. 不要将 `FEISHU_APP_SECRET` 提交到代码仓库
2. 仅申请当前实现实际需要的最小权限
3. 如需轮换凭证，重新执行 `remote-claude lark init`

## 相关文档

- [飞书客户端管理](./feishu-client.md)
- [配置说明](./configuration.md)
- [历史权限清单（扩展范围参考）](./feishu-permissions.json)
