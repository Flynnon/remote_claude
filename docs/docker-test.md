# Docker 测试

本目录包含 Docker 测试配置，用于验证 npm 包在不同环境下的完整性和功能可用性。

## 目录结构

```
docker/
├── Dockerfile.test              # Docker 测试镜像定义
├── docker-compose.test.yml      # Docker Compose 配置
├── scripts/
│   ├── docker-test.sh           # 主测试脚本
│   └── docker-diagnose.sh       # 失败诊断脚本
└── README.md                    # 本文档
```

## 快速开始

### 构建镜像

使用 BuildKit 加速构建（推荐）：

```bash
# 启用 BuildKit（Linux/macOS）
export DOCKER_BUILDKIT=1

# 构建镜像（使用缓存）
docker-compose -f docker/docker-compose.test.yml build

# 或使用 docker buildx 获得更好的缓存性能
docker buildx build --cache-to type=local,dest=.docker-cache --cache-from type=local,src=.docker-cache -f docker/Dockerfile.test -t remote-claude-npm-test .
```

### 运行测试

当修改 npm 打包、安装脚本、shell 入口、启动链路或 Docker 逻辑时，优先运行：

```bash
docker-compose -f docker/docker-compose.test.yml run --rm npm-test /project/docker/scripts/docker-test.sh
```

这是当前推荐的终态回归方式：容器执行完成后自动退出，测试报告与安装产物保留在挂载出的 `test-results/` 目录中。

如需进入容器排障，可改为不带 `--rm` 运行，或直接启动交互 shell：

```bash
docker-compose -f docker/docker-compose.test.yml run npm-test /project/docker/scripts/docker-test.sh
docker-compose -f docker/docker-compose.test.yml run npm-test /bin/bash
```

### 环境清理

```bash
docker-compose -f docker/docker-compose.test.yml down --remove-orphans
```

### 查看结果

```bash
ls -lh test-results/
cat test-results/test_report.md
```

## 宿主机使用 Docker 产物安装

Docker 测试完成后，`test-results/` 目录包含完整的安装产物，可直接在宿主机上使用：

### 产物说明

```
test-results/
├── npm-install/                 # npm 安装目录
│   ├── .venv/                   # Python 虚拟环境（便携式）
│   └── node_modules/
│       └── remote-claude/       # 完整项目代码
│           └── bin/             # 可执行脚本（remote-claude, cla, cl, cx, cdx）
├── test_report.md               # 测试报告
└── version.txt                  # 版本号
```

### 宿主机快速使用

```bash
# 方式一：直接运行快捷命令（推荐）
cd test-results/npm-install/node_modules/remote-claude
./bin/cla  # 启动 Claude 会话

# 方式二：使用公开入口查看帮助
cd test-results/npm-install/node_modules/remote-claude
./bin/remote-claude --help

# 方式三：激活虚拟环境后使用（传统方式）
source test-results/npm-install/node_modules/remote-claude/.venv/bin/activate
remote-claude --help
```

### 可执行脚本

`bin/` 目录下提供公开 CLI 主入口和常用快捷命令：

| 脚本 | 说明 |
|------|------|
| `remote-claude` | 公开 CLI 主入口 |
| `cla` | 启动 Claude 会话 |
| `cl` | 快速启动 Claude 会话（跳过权限确认） |
| `cx` | 快速启动 Codex 会话（跳过权限确认） |
| `cdx` | 启动 Codex 会话 |

### 前置要求

宿主机使用 Docker 产物需要：

1. **必需工具**：tmux、git
2. **CLI 工具**：Claude CLI 或 Codex CLI（至少一个）
3. **可选**：飞书企业自建应用（用于飞书客户端）

**指定启动器示例：**

```bash
remote-claude start demo --launcher Codex
```

> **注意**：产物中已包含便携式 Python 虚拟环境（`.venv`），宿主机无需预装 Python。

### 验证安装

```bash
# 验证 Python 环境
test-results/npm-install/node_modules/remote-claude/.venv/bin/python3 --version

# 验证依赖
test-results/npm-install/node_modules/remote-claude/.venv/bin/python3 -c "import lark_oapi; print('✓ 依赖完整')"

# 验证命令可用
test-results/npm-install/node_modules/remote-claude/bin/cla --help
test-results/npm-install/node_modules/remote-claude/bin/remote-claude --help
```

## 测试流程

Docker 测试模拟真实用户从 npm 安装 remote-claude 的当前终态流程：

1. **环境检查** - 验证 Python、uv、tmux、npm、Claude CLI、Codex CLI
2. **打包 npm 包** - 执行 `npm pack` 生成 `.tgz` 文件
3. **模拟用户安装** - 在临时目录执行 `npm install <packaged_file>`
4. **验证 postinstall** - 检查 `.venv`、`pyproject.toml`、Python 依赖
5. **会话启动验证** - 验证 `remote-claude start` 与 `remote-claude start --launcher Codex` 能创建 socket，且会话可被 `remote-claude list` 看到
6. **测试基本命令** - 验证主入口、列表命令、快捷脚本语法与关键行为
7. **文件完整性检查** - 验证关键文件（含 `resources/defaults/` 模板文件）是否存在
8. **验证卸载钩子** - 验证 uninstall hook 可在非交互模式下执行
9. **生成测试报告** - 汇总测试结果，生成 Markdown 报告
10. **清理** - 测试脚本结束后直接退出容器；如需保留容器调试，请改用不带 `--rm` 的运行方式

步骤 5、6、7、8 会继续执行并写入最终报告；但任一步骤失败时，脚本最终仍会以非零状态退出，便于 CI 正确判定失败。

## 独立单元测试

以下单元测试不需要活跃的会话：

**核心测试**（失败终止整个测试流程）：
- `test_session_truncate.py` - 会话名称截断测试
- `test_runtime_config.py` - 运行时配置与环境变量兼容测试
- `test_biz_enum.py` - CLI 类型枚举测试
- `test_custom_commands.py` - 自定义命令、卸载入口与 completion 行为测试
- `test_history_buffer.py` - 历史缓冲区测试
- `test_auto_answer_analyzer.py` - 自动应答选项分析器测试
- `test_auto_answer_integration.py` - 自动应答集成测试
- `test_base_client.py` - 客户端基类测试
- `test_local_client.py` - 本地客户端测试
- `test_entry_lazy_init.py::test_entry_script_skips_feishu_prompt_and_executes_remote_claude_when_optional` - 飞书未配置时本地启动不阻塞
- `test_entry_lazy_init.py::test_check_env_allows_skip_when_feishu_not_required` - 跳过飞书配置检查
- `test_entry_lazy_init.py::test_lazy_init_failure_surfaces_log_hint_and_stage_details` - lazy init 失败信息可见
- `test_entry_lazy_init.py` - 入口脚本与 lazy init 全量回归
- `test_cli_help_and_remote.py` - CLI 行为、无副作用与 remote 参数回归
- `test_startup_trace_logging.py` - 启动 tracing 日志回归

**非核心测试**（失败继续执行，记录警告）：
- `test_stream_poller.py` - 流式卡片模型测试
- `test_card_interaction.py` - 卡片交互优化测试
- `test_list_display.py` - List 命令展示测试
- `test_disconnected_state.py` - 断开状态提示测试
- `test_renderer.py` - 终端渲染器测试
- `test_auto_answer_block.py` - 自动应答块渲染测试
- `lark_client/test_mock_output.py` - 飞书客户端输出模拟测试
- `lark_client/test_cjk_width.py` - CJK 字符宽度测试
- `lark_client/test_full_simulation.py` - 完整模拟测试

## 调试失败

### 进入容器

```bash
docker exec -it remote-claude-npm-test /bin/bash
```

### 重新运行测试

```bash
cd /project
/project/docker/scripts/docker-test.sh
```

### 手动执行失败的测试

```bash
cd /home/testuser/test-results/npm-install/node_modules/remote-claude
uv run pytest -q tests/test_cli_help_and_remote.py
```

### 收集诊断信息

```bash
/project/docker/scripts/docker-diagnose.sh
```

诊断脚本通常会收集以下信息，具体内容可能随排障需求调整：

- 系统与依赖版本
- npm / Python 安装信息
- 安装后目录结构
- `remote-claude list` 输出
- socket / tmux / startup log 状态
- `test-results/` 下的日志与错误摘要
