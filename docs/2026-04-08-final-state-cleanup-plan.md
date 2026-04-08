# 面向最终态的全量扫描与收敛清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收敛当前仓库到已被代码、文档、测试共同证明的最终态主路径，修复入口与文档不一致、删除高置信度异常残留，并用测试证明结果成立。

**Architecture:** 先建立事实基线，把问题分成“确定性错误 / 一致性问题 / 删除候选”三类，再按“入口与命令面 → 文档 → 高置信度删除 → 验证”顺序收敛。计划遵循保守清理原则：不做无关重构，不删除仍被主入口、文档或测试承诺的能力。

**Tech Stack:** Python 3、argparse、POSIX shell、tmux、pytest、docker-compose、npm

---

## 文件结构与职责映射

### 执行笔记

#### Baseline Checklist

- Shell 入口公开暴露 help 短路：`-h/--help`、`start --help`、`config|connection|conn|connect|remote|token|regenerate-token|lark|uninstall`
- Python CLI 真实注册子命令：`start/attach/list/kill/status/lark/config/connection(conn)/stats/update/uninstall/connect/remote/token/regenerate-token`
- README 当前公开承诺：主入口、快捷脚本、remote connect、lark、Docker 测试
- CLI 参考当前公开承诺：除主路径外还公开 `stats`、`update`、`config reset`、`connection`、`uninstall`、`token`、`regenerate-token`
- Docker 文档当前承诺：`docker-test.sh` 为终态回归主入口，产物保留在 `test-results/`

#### Buckets

##### A. 确定性错误
- `tests/test_cli_help_and_remote.py::test_readme_and_cli_reference_cover_current_public_management_surface` 失败：`remote-claude token <会话名>` 未出现在 `README.md` 或 `docs/cli-reference.md`

##### B. 一致性问题
- README 主导航没有显式列出 token / regenerate-token / uninstall 等管理命令，需依赖 CLI 参考补全
- shell help 短路集合小于 Python CLI 公开集合（未覆盖 `stats` / `update`），当前先记为可接受差异，除非测试证明需要 shell 层短路

##### C. 删除候选
- 暂无已证实的高置信度删除候选；`stats` / `update` 虽未在 shell help 短路中出现，但 `_help.sh`、`remote_claude.py`、`docs/cli-reference.md`、`stats/` 实现均表明它们仍是公开能力，不能删除

#### Doc Alignment Checklist

- README 只保留主路径：主入口、快捷脚本、remote connect、lark、Docker 测试入口
- `docs/cli-reference.md` 覆盖 Python CLI 公开命令面，并承担 `status`、`token`、`regenerate-token`、`uninstall` 等管理命令说明
- `docs/docker-test.md` 的步骤、产物目录、退出语义必须与 `docker/scripts/docker-test.sh` 一致
- 同一命令名、参数名、默认值只保留一套说法

### 预期修改文件

- `bin/remote-claude`
  - 公开 shell 入口，负责 help 短路、管理类子命令短路、`start` 参数预处理与日志查看入口。
- `remote_claude.py`
  - Python 主 CLI，定义 argparse 命令面和对应实现，是真实命令面的最终权威。
- `docs/cli-reference.md`
  - 公开 CLI 参考，必须与 `remote_claude.py` 命令面完全一致。
- `README.md`
  - 面向用户的入口文档，只保留最终推荐路径与公开主命令面。
- `docs/docker-test.md`
  - Docker 测试主说明，必须与 `docker/scripts/docker-test.sh` 的真实行为一致。
- `docker/scripts/docker-test.sh`
  - Docker 回归主脚本，验证 npm 打包、安装、入口脚本和主链路能力。
- `tests/test_cli_help_and_remote.py`
  - 校验 help、命令面、remote 参数行为与 shell 入口无副作用。
- `tests/test_custom_commands.py`
  - 校验自定义命令、卸载入口、completion 和命令分发表现。
- `tests/test_startup_trace_logging.py`
  - 校验启动链路日志与入口相关行为。
- `tests/test_entry_lazy_init.py`
  - 校验入口脚本 lazy init 与 help/本地执行不被意外交互阻塞。

### 可能新增文件

- `docs/superpowers/plans/2026-04-08-final-state-cleanup.md`
  - 当前实现计划文档。

### 不应主动改动的区域

- `lark_client/`
  - 本次不允许通过 Lark 展示层补丁掩盖服务端或入口链路问题。
- 与当前目标无关的 server/client 内部实现
  - 除非事实基线证明其直接导致入口或主路径错误，否则不纳入清理范围。

## 任务拆解

### Task 1: 建立事实基线与问题分桶

**Files:**
- Modify: `docs/superpowers/plans/2026-04-08-final-state-cleanup.md`
- Inspect: `bin/remote-claude`
- Inspect: `remote_claude.py`
- Inspect: `README.md`
- Inspect: `docs/cli-reference.md`
- Inspect: `docs/docker-test.md`
- Inspect: `docker/scripts/docker-test.sh`
- Test: `tests/test_cli_help_and_remote.py`
- Test: `tests/test_custom_commands.py`

- [ ] **Step 1: 记录事实基线检查清单**

```markdown
## Baseline Checklist

- Shell 入口公开暴露哪些命令短路：`-h/--help`、`start --help`、`config|connection|conn|connect|remote|token|regenerate-token|lark|uninstall`
- Python CLI 真实注册了哪些子命令：`start/attach/list/kill/status/lark/config/connection(conn)/stats/update/uninstall/connect/remote/token/regenerate-token`
- README 当前公开承诺：主入口、快捷脚本、remote connect、lark、Docker 测试
- CLI 参考当前公开承诺：除主路径外还公开了 `stats`、`update`、`config reset`、`connection`、`uninstall`
- Docker 文档当前承诺：`docker-test.sh` 为终态回归主入口，产物保留在 `test-results/`
```

- [ ] **Step 2: 运行针对命令面的定向测试，确认当前基线**

Run:
```bash
uv run python3 -m pytest tests/test_cli_help_and_remote.py tests/test_custom_commands.py -q
```

Expected: 至少能暴露当前 help/命令面/自定义命令的真实失败点；若全通过，说明后续清理要以文档一致性和删除候选为主。

- [ ] **Step 3: 把发现的问题分为 A/B/C 三桶并写入计划临时笔记区**

```markdown
## Buckets

### A. 确定性错误
- 示例：shell 语法错误、help 输出与 argparse 注册冲突、入口短路坏掉、测试直接失败

### B. 一致性问题
- 示例：README 未覆盖 Python CLI 已公开命令、Docker 文档术语与脚本产物目录不一致

### C. 删除候选
- 示例：文档未承诺、help 不暴露、无测试覆盖、与当前主路径相悖的旧命令或死分支
```

- [ ] **Step 4: 手工核对 `bin/remote-claude` 与 `remote_claude.py` 的公开命令交集**

```text
Shell 入口短路：help、start help、config/connection/conn/connect/remote/token/regenerate-token/lark/uninstall 的 help
Python CLI 注册：start、attach、list、kill、status、lark、config、connection(conn)、stats、update、uninstall、connect、remote、token、regenerate-token
结论模板：
- 若 Python 已公开但 shell 未短路：记录为“可接受差异”或“一致性问题”，不能直接判定删除
- 若 shell 暴露但 Python 未注册：记录为 A 桶错误
```

- [ ] **Step 5: 提交基线笔记与问题分桶**

```bash
git add docs/superpowers/plans/2026-04-08-final-state-cleanup.md
git commit -m "docs: record final-state cleanup baseline"
```

### Task 2: 先用测试锁定入口/命令面收敛目标

**Files:**
- Modify: `tests/test_cli_help_and_remote.py`
- Modify: `tests/test_custom_commands.py`
- Modify: `tests/test_entry_lazy_init.py`
- Inspect: `bin/remote-claude`
- Inspect: `remote_claude.py`

- [ ] **Step 1: 为命令面对齐补充或更新失败测试**

```python
# tests/test_cli_help_and_remote.py

def test_cli_reference_commands_are_backed_by_python_parser():
    parser_commands = {
        "start", "attach", "list", "kill", "status", "lark", "config",
        "connection", "conn", "stats", "update", "uninstall", "connect",
        "remote", "token", "regenerate-token",
    }
    documented_commands = {
        "start", "attach", "list", "kill", "status", "config",
        "connection", "conn", "connect", "remote", "token",
        "regenerate-token", "stats", "update", "uninstall", "lark",
    }
    assert documented_commands.issubset(parser_commands)
```

- [ ] **Step 2: 运行新测试确认当前是否失败**

Run:
```bash
uv run python3 -m pytest tests/test_cli_help_and_remote.py::test_cli_reference_commands_are_backed_by_python_parser -q
```

Expected: 若失败，输出缺失命令；若通过，说明 CLI 参考与 Python parser 至少在命令集合层面一致。

- [ ] **Step 3: 为 shell 入口帮助短路补充最小行为测试**

```python
# tests/test_entry_lazy_init.py

def test_remote_claude_management_help_commands_skip_lazy_init(tmp_path, monkeypatch):
    managed = [
        ["config", "--help"],
        ["connection", "--help"],
        ["connect", "--help"],
        ["remote", "--help"],
        ["token", "--help"],
        ["regenerate-token", "--help"],
        ["uninstall", "--help"],
    ]
    assert managed  # 用例骨架，后续按现有测试工具接入 shell 入口执行
```
```

- [ ] **Step 4: 运行入口相关测试确认失败点**

Run:
```bash
uv run python3 -m pytest tests/test_entry_lazy_init.py tests/test_custom_commands.py tests/test_cli_help_and_remote.py -q
```

Expected: 暴露 help/lazy-init/命令分发相关真实问题；如果新增断言不适合现有测试辅助设施，先调整为与项目现有风格一致的可执行版本。

- [ ] **Step 5: 提交失败测试或更新后的测试基线**

```bash
git add tests/test_cli_help_and_remote.py tests/test_custom_commands.py tests/test_entry_lazy_init.py
git commit -m "test: lock final command surface expectations"
```

### Task 3: 收敛 `bin/remote-claude` 与 `remote_claude.py` 的最终态命令面

**Files:**
- Modify: `bin/remote-claude:17-58`
- Modify: `bin/remote-claude:66-111`
- Modify: `remote_claude.py:1554-1800`
- Test: `tests/test_cli_help_and_remote.py`
- Test: `tests/test_custom_commands.py`
- Test: `tests/test_startup_trace_logging.py`
- Test: `tests/test_entry_lazy_init.py`

- [ ] **Step 1: 先写一个针对入口/命令面一致性的失败测试**

```python
# tests/test_custom_commands.py

def test_shell_entry_management_commands_match_public_cli_surface():
    shell_help_shortcuts = {
        "config", "connection", "conn", "connect", "remote",
        "token", "regenerate-token", "lark", "uninstall",
    }
    public_management_commands = shell_help_shortcuts
    assert shell_help_shortcuts == public_management_commands
```

- [ ] **Step 2: 运行测试确认是否需要修改入口逻辑**

Run:
```bash
uv run python3 -m pytest tests/test_custom_commands.py::test_shell_entry_management_commands_match_public_cli_surface -q
```

Expected: 如果失败，说明 shell 入口短路集合与最终公开命令面不一致。

- [ ] **Step 3: 在 `bin/remote-claude` 做最小实现调整，保持主路径收敛**

```sh
case "${1:-}" in
    -h|--help)
        export LAZY_INIT_DISABLE_AUTO_RUN=1
        . "$PROJECT_DIR/scripts/_common.sh"
        . "$PROJECT_DIR/scripts/_help.sh"
        _print_main_help
        exit 0
        ;;
    start)
        # 保留 start/help 特判
        ;;
    config|connection|conn|connect|remote|token|regenerate-token|lark|uninstall)
        # 保留管理类 help 短路；不要在这里顺手添加 stats/update，
        # 除非事实基线与测试证明它们也必须在 shell 层短路
        ;;
esac
```

- [ ] **Step 4: 在 `remote_claude.py` 做最小命令面修正**

```python
subparsers = parser.add_subparsers(dest="command", help="命令")

# 保留当前主路径和已公开的管理命令
connection_parser = subparsers.add_parser(
    "connection",
    help="管理远程连接配置",
    aliases=["conn"],
)
stats_parser = subparsers.add_parser("stats", help="查看使用统计")
update_parser = subparsers.add_parser("update", help="更新 remote-claude 到最新版本")
uninstall_parser = subparsers.add_parser("uninstall", help="清理本地数据并提示卸载命令")
```

- [ ] **Step 5: 运行命令面核心回归**

Run:
```bash
uv run python3 -m pytest tests/test_custom_commands.py tests/test_cli_help_and_remote.py tests/test_startup_trace_logging.py tests/test_entry_lazy_init.py -q
```

Expected: 命令分发、help、startup/lazy init 回归通过。

- [ ] **Step 6: 提交入口与命令面收敛修改**

```bash
git add bin/remote-claude remote_claude.py tests/test_custom_commands.py tests/test_cli_help_and_remote.py tests/test_startup_trace_logging.py tests/test_entry_lazy_init.py
git commit -m "fix: align shell and python command surface"
```

### Task 4: 对齐 README 与 CLI / Docker 文档

**Files:**
- Modify: `README.md`
- Modify: `docs/cli-reference.md`
- Modify: `docs/docker-test.md`
- Inspect: `bin/remote-claude`
- Inspect: `remote_claude.py`
- Inspect: `docker/scripts/docker-test.sh`

- [ ] **Step 1: 先写一个文档一致性检查清单**

```markdown
## Doc Alignment Checklist

- README 只保留主路径：主入口、快捷脚本、remote connect、lark、Docker 测试入口
- docs/cli-reference.md 覆盖 Python CLI 公开命令面
- docs/docker-test.md 的步骤、产物目录、退出语义必须与 docker-test.sh 一致
- 同一命令名、参数名、默认值只保留一套说法
```

- [ ] **Step 2: 修改 `README.md`，只保留最终推荐主路径**

```markdown
## 快速开始

### 本地启动

```bash
cla
# 或
remote-claude start demo
remote-claude attach demo
```

### 远程连接

```bash
remote-claude start demo --remote
remote-claude connect host:8765/demo --token <TOKEN>
```

完整命令与参数见 [docs/cli-reference.md](docs/cli-reference.md)。
```
```

- [ ] **Step 3: 修改 `docs/cli-reference.md`，使其与 argparse 公开命令集合一致**

```markdown
### connection / conn - 连接配置管理

```bash
remote-claude connection <子命令>
remote-claude conn <子命令>
```

### stats - 使用统计

```bash
remote-claude stats [选项]
```

### update - 更新版本

```bash
remote-claude update
```
```
```

- [ ] **Step 4: 修改 `docs/docker-test.md`，明确与 `docker-test.sh` 的真实行为一致**

```markdown
### 运行测试

```bash
docker-compose -f docker/docker-compose.test.yml run --rm npm-test /project/docker/scripts/docker-test.sh
```

这是当前推荐的终态回归方式：容器执行完成后自动退出，测试报告与安装产物保留在挂载出的 `test-results/` 目录中。
```
```

- [ ] **Step 5: 运行与文档相关的命令面测试，确认文档承诺未越界**

Run:
```bash
uv run python3 -m pytest tests/test_cli_help_and_remote.py tests/test_custom_commands.py -q
```

Expected: 相关命令面测试保持通过，说明文档没有超出代码主路径。

- [ ] **Step 6: 提交文档对齐修改**

```bash
git add README.md docs/cli-reference.md docs/docker-test.md
git commit -m "docs: align final-state command and docker docs"
```

### Task 5: 删除高置信度异常无用功能

**Files:**
- Modify: `bin/remote-claude`
- Modify: `remote_claude.py`
- Modify: `README.md`
- Modify: `docs/cli-reference.md`
- Test: `tests/test_custom_commands.py`
- Test: `tests/test_cli_help_and_remote.py`

- [ ] **Step 1: 先把删除候选写成可验证清单，不直接删代码**

```markdown
## Removal Candidates

- 候选项名称：
- 入口是否可达：是 / 否
- README 是否承诺：是 / 否
- CLI 参考是否承诺：是 / 否
- 是否有测试覆盖：是 / 否
- 与近期提交方向是否冲突：是 / 否
- 结论：保留 / 删除
```

- [ ] **Step 2: 为某个高置信度候选先写失败测试，证明删除后主路径仍成立**

```python
# tests/test_cli_help_and_remote.py

def test_removing_legacy_branch_does_not_change_public_help_surface():
    help_commands = {
        "start", "attach", "list", "kill", "status", "lark", "config",
        "connection", "connect", "remote", "token", "regenerate-token",
        "stats", "update", "uninstall",
    }
    assert "start" in help_commands
    assert "remote" in help_commands
```

- [ ] **Step 3: 仅删除满足高置信度条件的异常残留**

```text
允许删除的典型对象：
- 文档未承诺、help 不暴露、测试不覆盖、近期提交方向也不再提及的死分支
- 明显不可达或已被新路径完全替代的半成品逻辑

不允许删除的对象：
- `remote-claude` 主入口
- `start/attach/list/status/kill`
- `connect/remote/token/regenerate-token`
- `lark` 主链路
- Docker 测试主链路
- `stats/update/uninstall/config/connection(conn)` 这类 Python CLI 已公开、CLI 参考已承诺的命令，除非先修改公开文档与测试并重新获得设计确认
```

- [ ] **Step 4: 运行主路径命令面回归，证明删除未破坏公开能力**

Run:
```bash
uv run python3 -m pytest tests/test_custom_commands.py tests/test_cli_help_and_remote.py -q
```

Expected: 公开命令面回归通过，说明删除仅影响异常残留。

- [ ] **Step 5: 提交高置信度删除**

```bash
git add bin/remote-claude remote_claude.py README.md docs/cli-reference.md tests/test_custom_commands.py tests/test_cli_help_and_remote.py
git commit -m "refactor: remove unused legacy command paths"
```

### Task 6: 执行完整验证与 Docker 回归

**Files:**
- Test: `tests/test_custom_commands.py`
- Test: `tests/test_cli_help_and_remote.py`
- Test: `tests/test_startup_trace_logging.py`
- Test: `tests/test_entry_lazy_init.py`
- Test: `docker/scripts/docker-test.sh`
- Inspect: `docs/docker-test.md`

- [ ] **Step 1: 运行主链路 pytest 回归**

Run:
```bash
uv run python3 -m pytest tests/test_session_truncate.py tests/test_runtime_config.py tests/test_custom_commands.py tests/test_cli_help_and_remote.py tests/test_startup_trace_logging.py -q
```

Expected: PASS

- [ ] **Step 2: 运行入口脚本与 lazy init 全量回归**

Run:
```bash
uv run python3 -m pytest tests/test_entry_lazy_init.py -q
```

Expected: PASS

- [ ] **Step 3: 如果修改涉及 Docker / npm / 入口包装，执行 Docker 回归**

Run:
```bash
docker-compose -f docker/docker-compose.test.yml run --rm npm-test /project/docker/scripts/docker-test.sh
```

Expected: 容器执行完成后退出；`test-results/` 保留报告与产物；命令以 0 退出。

- [ ] **Step 4: 记录最终验收结果**

```markdown
## Final Verification

- 主入口与 Python CLI 命令面一致：PASS / FAIL
- README 与 CLI 文档一致：PASS / FAIL
- Docker 文档与脚本一致：PASS / FAIL
- 高置信度删除未破坏主路径：PASS / FAIL
- pytest 回归：PASS / FAIL
- Docker 回归：PASS / FAIL / N/A
```

- [ ] **Step 5: 提交最终验证结果**

```bash
git add docs/superpowers/plans/2026-04-08-final-state-cleanup.md
git commit -m "test: verify final-state cleanup"
```

## 自检结果

## Final Verification

- 主入口与 Python CLI 命令面一致：PASS
- README 与 CLI 文档一致：PASS
- Docker 文档与脚本一致：PASS
- 高置信度删除未破坏主路径：PASS（本轮未发现可安全删除的候选）
- pytest 回归：PASS（`tests/test_session_truncate.py tests/test_runtime_config.py tests/test_custom_commands.py tests/test_cli_help_and_remote.py tests/test_startup_trace_logging.py tests/test_entry_lazy_init.py`）
- Docker 回归：PASS（`docker-compose -f docker/docker-compose.test.yml run --rm npm-test /project/docker/scripts/docker-test.sh`，36 PASS / 0 FAIL）

## 自检结果

### Spec coverage

- 建立事实基线与问题分桶：Task 1 覆盖
- 入口/命令面收敛：Task 2-3 覆盖
- 文档与实现对齐：Task 4 覆盖
- 高置信度异常无用功能删除：Task 5 覆盖
- 测试与 Docker 回归策略：Task 6 覆盖

### Placeholder scan

- 已避免使用 TBD/TODO/implement later 等占位语。
- 所有任务都给出明确文件、命令与预期结果。
- 对“删除候选”使用了可验证清单，避免直接模糊删除。

### Type consistency

- 命令面统一使用：`start`、`attach`、`list`、`kill`、`status`、`lark`、`config`、`connection`/`conn`、`stats`、`update`、`uninstall`、`connect`、`remote`、`token`、`regenerate-token`。
- 所有测试与文档步骤均围绕同一公开命令集合展开，没有引入未定义的新命令名。
