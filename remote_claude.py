#!/usr/bin/env python3
"""
Remote Claude - 双端共享 Claude/Codex CLI 工具

命令:
  start <name>       启动新会话（在 tmux 中）
  attach <name>      连接到已有会话
  list               列出所有会话
  kill <name>        终止会话
  status <name>      显示会话状态
  lark               飞书客户端管理（start/stop/restart/status）
  stats              查看使用统计
  update             更新 remote-claude 到最新版本
"""

import argparse
import logging
import os
import sys
import subprocess
import time
import json
import shlex
import signal
from datetime import datetime
from pathlib import Path

# 获取脚本所在目录
SCRIPT_DIR = Path(__file__).parent.absolute()
_PROJECT_ROOT = str(SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
logger = logging.getLogger('RemoteCLI')
USER_DATA_DIR = None


def _session_api():
    from utils.session import (
        get_socket_path, ensure_socket_dir, tmux_session_exists, tmux_create_session,
        tmux_kill_session,
        list_active_sessions, is_session_active, cleanup_session,
        is_lark_running, get_lark_pid, get_lark_status, get_lark_pid_file,
        save_lark_status, cleanup_lark,
        USER_DATA_DIR, ensure_user_data_dir,
        get_env_snapshot_path,
    )
    return {
        "get_socket_path"      : get_socket_path,
        "ensure_socket_dir"    : ensure_socket_dir,
        "tmux_session_exists"  : tmux_session_exists,
        "tmux_create_session"  : tmux_create_session,
        "tmux_kill_session"    : tmux_kill_session,
        "list_active_sessions" : list_active_sessions,
        "is_session_active"    : is_session_active,
        "cleanup_session"      : cleanup_session,
        "is_lark_running"      : is_lark_running,
        "get_lark_pid"         : get_lark_pid,
        "get_lark_status"      : get_lark_status,
        "get_lark_pid_file"    : get_lark_pid_file,
        "save_lark_status"     : save_lark_status,
        "cleanup_lark"         : cleanup_lark,
        "USER_DATA_DIR"        : USER_DATA_DIR,
        "ensure_user_data_dir" : ensure_user_data_dir,
        "get_env_snapshot_path": get_env_snapshot_path,
    }


def _get_cli_type():
    from server.biz_enum import CliType
    return CliType


def _get_role_log_path(role: str):
    from utils.logging_setup import get_role_log_path
    return get_role_log_path(role)


# 兼容现有测试与 monkeypatch：保留轻量可替换包装层

def is_session_active(session_name):
    return _session_api()["is_session_active"](session_name)


def tmux_session_exists(session_name):
    return _session_api()["tmux_session_exists"](session_name)


def cleanup_session(session_name):
    return _session_api()["cleanup_session"](session_name)


def ensure_socket_dir():
    return _session_api()["ensure_socket_dir"]()


def ensure_user_data_dir():
    return _session_api()["ensure_user_data_dir"]()


def get_socket_path(session_name):
    return _session_api()["get_socket_path"](session_name)


def get_env_snapshot_path(session_name):
    return _session_api()["get_env_snapshot_path"](session_name)


def tmux_create_session(session_name, command, detached=True):
    return _session_api()["tmux_create_session"](session_name, command, detached=detached)


def tmux_kill_session(session_name):
    return _session_api()["tmux_kill_session"](session_name)


def list_active_sessions():
    return _session_api()["list_active_sessions"]()


def is_lark_running():
    return _session_api()["is_lark_running"]()


def get_lark_pid():
    return _session_api()["get_lark_pid"]()


def get_lark_status():
    return _session_api()["get_lark_status"]()


def get_lark_pid_file():
    return _session_api()["get_lark_pid_file"]()


def save_lark_status(*args, **kwargs):
    return _session_api()["save_lark_status"](*args, **kwargs)


def cleanup_lark():
    return _session_api()["cleanup_lark"]()


def _get_user_data_dir():
    value = globals().get("USER_DATA_DIR")
    if callable(value):
        return value()
    if value is not None:
        return value
    return _session_api()["USER_DATA_DIR"]


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 4:
        return "*" * len(token)
    return f"{token[:2]}***{token[-2:]}"


def _log_remote_args(command: str, host: str, port: int, session: str, token: str) -> None:
    logger.info(
        "stage=remote_args_parsed command=%s session=%s host=%s port=%s has_token=%s token_masked=%s",
        command,
        session,
        host,
        port,
        bool(token),
        _mask_token(token),
    )


def _normalize_original_path(value: str | None) -> str:
    if value is None:
        return "-"
    value = value.strip()
    return value or "-"


# 读取版本号（懒加载，避免 import 时触发文件读取）
def get_version() -> str:
    try:
        import json as _json
        return _json.loads((SCRIPT_DIR / "package.json").read_text(encoding="utf-8"))["version"]
    except (OSError, json.JSONDecodeError, KeyError):
        return "unknown"


def _sanitize_command_for_log(command: str) -> str:
    """对命令字符串做脱敏，避免 token/password/secret 泄漏到日志"""
    sensitive_flags = {"--token", "--password", "--secret"}
    sensitive_assign_keys = {"--token", "--password", "--secret", "token", "password", "secret"}

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()

    sanitized_tokens = []
    mask_next = False
    for token in tokens:
        if mask_next:
            sanitized_tokens.append("***")
            mask_next = False
            continue

        token_lower = token.lower()
        if token_lower in sensitive_flags:
            sanitized_tokens.append(token)
            mask_next = True
            continue

        if "=" in token:
            key, _ = token.split("=", 1)
            if key.lower() in sensitive_assign_keys:
                sanitized_tokens.append(f"{key}=***")
                continue

        sanitized_tokens.append(token)

    if mask_next:
        sanitized_tokens.append("***")

    return " ".join(sanitized_tokens)


def _read_start_log_lines_since(log_path: Path, start_time: datetime) -> list[str]:
    cache = getattr(_read_start_log_lines_since, "_cache", {})
    try:
        stat = log_path.stat()
    except FileNotFoundError:
        cache.pop(log_path, None)
        _read_start_log_lines_since._cache = cache
        return []

    cached = cache.get(log_path)
    if cached and cached["mtime_ns"] == stat.st_mtime_ns and cached["size"] == stat.st_size:
        lines = cached["lines"]
    else:
        previous_lines = cached["lines"] if cached else []
        previous_size = cached["size"] if cached else 0
        if cached and stat.st_size >= previous_size:
            with log_path.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(previous_size)
                appended_lines = handle.read().splitlines()
            lines = previous_lines + appended_lines
        else:
            lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        cache[log_path] = {
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
            "lines": lines,
        }
        _read_start_log_lines_since._cache = cache

    matched_lines = []
    for line in lines:
        try:
            ts = datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S.%f")
            if ts >= start_time:
                matched_lines.append(line)
        except ValueError:
            if matched_lines:
                matched_lines.append(line)
    return matched_lines


def _read_recent_start_log_lines(log_path: Path, max_lines: int = 200) -> list[str]:
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max_lines:]


def _detect_hard_startup_failure(log_lines: list[str]) -> str:
    hard_failure_markers = (
        "command not found",
        "no such file or directory",
        "filenotfounderror",
        "exec failed",
        "can't find",
        "not recognized as an internal or external command",
        "exited with status 127",
    )

    for line in log_lines:
        lower_line = line.lower()
        if any(marker in lower_line for marker in hard_failure_markers):
            return line
    return ""


def add_remote_args(parser):
    """添加远程连接公共参数

    Args:
        parser: ArgumentParser 或 subparser
    """
    parser.add_argument(
        "--remote",
        action="store_true",
        help="远程连接模式"
    )
    parser.add_argument(
        "--host",
        default="",
        help="远程服务器地址（支持 host:port 格式）"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="远程服务器端口（默认: 8765）"
    )
    parser.add_argument(
        "--token",
        default="",
        help="认证令牌（远程模式必需）"
    )


def parse_host_session(args):
    """解析 host 和 session 参数

    支持格式：
    - --host server.com --port 8765 --token xxx session_name
    - --host server.com:8765 --token xxx session_name
    - --host server.com:8765/session_name --token xxx

    Args:
        args: 解析后的参数对象

    Returns:
        (host, port, session, token) 元组，解析失败返回 (None, None, None, None)
    """
    host = getattr(args, 'host', '') or ''
    port = getattr(args, 'port', 8765)
    token = getattr(args, 'token', '') or ''
    session = getattr(args, 'name', '') or ''

    # 支持 host:port/session 格式
    if '/' in host:
        parts = host.split('/')
        host_part = parts[0]
        session = parts[1] if len(parts) > 1 else session
        if ':' in host_part:
            host, port_str = host_part.split(':')
            try:
                port = int(port_str)
            except ValueError:
                print(f"错误: 端口格式无效: {port_str}")
                return None, None, None, None
    elif ':' in host:
        host, port_str = host.split(':')
        try:
            port = int(port_str)
        except ValueError:
            print(f"错误: 端口格式无效: {port_str}")
            return None, None, None, None

    return host, port, session, token


def _run_remote_client(host: str, session: str, token: str, port: int) -> int:
    from client.remote_client import run_remote_client
    return run_remote_client(host, session, token, port)


def _build_remote_client(host: str, session: str, token: str, port: int):
    from client.remote_client import RemoteClient
    return RemoteClient(host, session, token, port)


def run_remote_control(host: str, port: int, session: str, token: str, action: str) -> int:
    """执行远程控制命令

    Args:
        host: 服务器地址
        port: 服务器端口
        session: 会话名称
        token: 认证令牌
        action: 控制命令

    Returns:
        退出码
    """
    import asyncio

    async def do_control():
        client = _build_remote_client(host, session, token, port)
        result = await client.send_control(action)
        if result['success']:
            print(f"✓ {result['message']}")
            return 0
        else:
            print(f"✗ {result['message']}")
            return 1

    try:
        return asyncio.run(do_control())
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        return 1


def validate_remote_args(args, session_fallback: str = None) -> tuple:
    """验证远程模式参数

    统一验证远程模式的必要参数，返回验证结果。

    Args:
        args: 解析后的参数对象
        session_fallback: 会话名称的后备值（如 args.name）

    Returns:
        (host, port, session, token) 元组，验证失败返回 None
    """
    host, port, session, token = parse_host_session(args)

    if host is None and port is None and session is None and token is None:
        return None

    if not host:
        print("错误: 远程模式需要 --host 参数")
        return None
    if not token:
        print("错误: 远程模式需要 --token 参数")
        return None

    if not session and session_fallback:
        session = session_fallback
    if not session:
        print("错误: 请指定会话名称")
        return None

    return host, port, session, token


def cmd_start(args):
    """启动新会话"""
    session_api = _session_api()
    original_session_name = args.name

    # 加载配置
    from utils.runtime_config import load_settings, load_state
    settings = load_settings()
    state = load_state()

    # 解析 launcher
    launcher_name = args.launcher
    if launcher_name:
        launcher = settings.get_launcher(launcher_name)
        if not launcher:
            print(f"错误: 未找到启动器 '{launcher_name}'")
            print(f"可用的启动器: {[l.name for l in settings.launchers]}")
            return 1
    else:
        launcher = settings.get_default_launcher()
        if not launcher:
            print("错误: 未配置启动器，请在 settings.json 中配置 launchers")
            return 1

    cli_type = launcher.cli_type
    command = launcher.command

    if command and os.path.isabs(command) and not Path(command).exists():
        print(f"错误: 启动器命令不存在: {command}")
        return 1

    # 使用 resolve_session_name() 处理名称截断和冲突
    from utils.session import resolve_session_name
    session_name = resolve_session_name(original_session_name, state)

    # 检查会话是否已存在
    if session_api["is_session_active"](session_name):
        print(f"错误: 会话 '{session_name}' 已存在")
        print(f"使用 'remote-claude attach {session_name}' 连接")
        return 1

    # 检查 tmux 会话是否存在
    if tmux_session_exists(session_name):
        print(f"错误: tmux 会话 'rc-{session_name}' 已存在")
        print("请先使用 'remote-claude kill {session_name}' 清理")
        return 1

    cli_args = args.cli_args if args.cli_args else []
    if any(arg in ("-h", "--help") for arg in cli_args):
        print("错误: start 子命令不支持透传帮助参数，请直接运行 remote-claude start --help 查看用法")
        return 1

    session_api["ensure_socket_dir"]()
    session_api["ensure_user_data_dir"]()  # 确保用户数据目录存在（用于 startup.log 等）

    # 将当前 shell 的完整环境变量保存到快照文件（权限 0600 防止密钥泄露）
    # tmux new-session 继承的是 tmux 服务器的全局环境，而非调用方 shell 的环境，
    # 通过快照文件将完整环境传递给 server.py 的 _start_pty()
    env_snapshot_path = session_api["get_env_snapshot_path"](session_name)
    env_fd = os.open(str(env_snapshot_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(env_fd, 'w') as f:
        json.dump(dict(os.environ), f)

    # 构建 server 命令
    server_script = SCRIPT_DIR / "server" / "server.py"
    # 使用 shlex.quote 安全转义参数，防止命令注入
    cli_args_str = " ".join(shlex.quote(arg) for arg in cli_args)
    debug_flag = " --debug-screen" if args.debug_screen else ""
    debug_verbose_flag = " --debug-verbose" if args.debug_verbose else ""
    cli_command_flag = f" --cli-command {shlex.quote(command)}"

    # 捕获用户终端环境变量（tmux 会覆盖这些值，导致 Claude CLI 无法启用 kitty keyboard protocol）
    # 使用 shlex.quote 安全转义环境变量值
    env_prefix_parts = []
    for key in ('TERM_PROGRAM', 'TERM_PROGRAM_VERSION', 'COLORTERM'):
        val = os.environ.get(key)
        if val:
            env_prefix_parts.append(f"{key}={shlex.quote(val)}")
    env_prefix = " ".join(env_prefix_parts) + " " if env_prefix_parts else ""

    # 远程模式参数
    remote_flag = ""
    if args.remote:
        remote_flag = f" --remote --remote-port {args.remote_port} --remote-host {shlex.quote(args.remote_host)}"

    # 使用 shlex.quote 安全转义所有路径和参数
    server_cmd = (
        f"{env_prefix}uv run --project {shlex.quote(str(SCRIPT_DIR))} "
        f"python3 {shlex.quote(str(server_script))}{debug_flag}{debug_verbose_flag}"
        f"{cli_command_flag}{remote_flag} -- {shlex.quote(session_name)} {cli_args_str}"
    )
    server_cmd_sanitized = _sanitize_command_for_log(server_cmd)

    # 配置启动日志（写文件 + stdout）
    _log_path = _get_user_data_dir() / "startup.log"
    _start_logger = logging.getLogger('Start')
    if not _start_logger.handlers:
        _handler_file = logging.FileHandler(_log_path, encoding="utf-8")
        _handler_file.setFormatter(logging.Formatter(
            "%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        _start_logger.addHandler(_handler_file)
        _start_logger.setLevel(logging.INFO)
        _start_logger.propagate = False

    start_time = datetime.now()
    _start_logger.info(f"启动会话: {session_name}")
    _start_logger.info(
        "stage=server_spawn session=%s cli_type=%s launcher=%s remote=%s remote_host=%s remote_port=%s cli_args_count=%s",
        session_name,
        cli_type,
        launcher.name,
        args.remote,
        args.remote_host if args.remote else "",
        args.remote_port if args.remote else "",
        len(cli_args),
    )
    _start_logger.info("server_cmd_sanitized=%s", server_cmd_sanitized)

    # 创建 tmux 会话，运行 server（detached，仅后台）
    if not tmux_create_session(session_name, server_cmd, detached=True):
        _start_logger.error(
            "stage=server_start_failed reason=tmux_create_failed session=%s remote=%s remote_host=%s remote_port=%s",
            session_name,
            args.remote,
            args.remote_host if args.remote else "",
            args.remote_port if args.remote else "",
        )
        print("错误: 无法创建 tmux 会话")
        return 1

    # 等待 server 启动（超时时间可通过环境变量 STARTUP_TIMEOUT 配置，默认 5 秒）
    try:
        startup_timeout = int(os.environ.get("STARTUP_TIMEOUT", "5"))
        if startup_timeout < 1:
            startup_timeout = 5
    except ValueError:
        startup_timeout = 5

    socket_path = get_socket_path(session_name)
    wait_interval = 0.1  # 100ms
    max_attempts = int(startup_timeout / wait_interval)
    server_status_grace_checks = 2
    for i in range(max_attempts):
        if socket_path.exists():
            break

        log_lines = _read_start_log_lines_since(_log_path, start_time)
        hard_failure = _detect_hard_startup_failure(log_lines)
        if hard_failure:
            _start_logger.error(
                "stage=server_start_failed reason=hard_startup_error session=%s remote=%s remote_host=%s remote_port=%s detail=%s",
                session_name,
                args.remote,
                args.remote_host if args.remote else "",
                args.remote_port if args.remote else "",
                hard_failure,
            )
            print("错误: Server 启动失败")
            print(f"--- Server 日志 ({_log_path}) ---")
            print("\n".join(log_lines))
            print("-------------------")
            tmux_kill_session(session_name)
            return 1

        # 检查 tmux 会话是否仍在运行（server 启动失败时会退出）
        if not tmux_session_exists(session_name):
            if server_status_grace_checks > 0:
                server_status_grace_checks -= 1
                time.sleep(wait_interval)
                continue
            _start_logger.error(
                "stage=server_start_failed reason=server_exited session=%s remote=%s remote_host=%s remote_port=%s",
                session_name,
                args.remote,
                args.remote_host if args.remote else "",
                args.remote_port if args.remote else "",
            )
            print("错误: Server 进程已退出")
            # 输出启动日志辅助诊断
            if log_lines:
                print(f"--- Server 日志 ({_log_path}) ---")
                print("\n".join(log_lines))
                print("-------------------")
            return 1
        time.sleep(wait_interval)
        if (i + 1) % 10 == 0:
            elapsed = (i + 1) // 10
            print(f"等待 Server 启动... ({elapsed}s)")
    else:
        _start_logger.error(
            "stage=server_start_failed reason=startup_timeout session=%s remote=%s remote_host=%s remote_port=%s timeout=%s",
            session_name,
            args.remote,
            args.remote_host if args.remote else "",
            args.remote_port if args.remote else "",
            startup_timeout,
        )
        print(f"错误: Server 启动超时 ({startup_timeout}s)")
        # 过滤出本次启动后的日志行
        log_lines = _read_start_log_lines_since(_log_path, start_time)
        if log_lines:
            print(f"--- Server 日志 ({_log_path}) ---")
            print("\n".join(log_lines))
            print("-------------------")
        tmux_kill_session(session_name)
        return 1

    # 再次检查 tmux 会话（socket 可能刚创建就被 server 关闭）
    if not tmux_session_exists(session_name):
        print("错误: Server 进程已退出")
        return 1

    print(f"会话已启动: rc-{session_name}")
    print(f"正在连接...")

    # 再次确认 socket 仍然存在，避免 server 刚启动即退出时继续进入 attach 分支
    if not socket_path.exists():
        _start_logger.error(
            "stage=server_start_failed reason=socket_missing_after_spawn session=%s remote=%s remote_host=%s remote_port=%s",
            session_name,
            args.remote,
            args.remote_host if args.remote else "",
            args.remote_port if args.remote else "",
        )
        print("错误: Server 已退出（socket 已丢失）")
        tmux_kill_session(session_name)
        return 1

    # 直接在前台运行 client（不走 tmux），让终端能力协商序列
    # （如 kitty keyboard protocol）直接在 Claude CLI ↔ 用户终端之间流通，
    # 从而支持 Shift+Enter 等扩展键
    from client import run_client
    return run_client(session_name)


def cmd_attach(args):
    """连接到已有会话（支持本地/远程模式）"""
    from client.connection_config import get_connection, get_default_connection, save_connection, touch_connection

    session_name = args.name
    config_name = getattr(args, 'config_name', '') or 'default'
    should_save = getattr(args, 'save', False)

    # 远程模式
    if getattr(args, 'remote', False):
        host = args.host
        token = args.token
        port = getattr(args, 'port', 8765)

        # 如果没有提供必要参数，尝试从保存的配置加载
        if not host or not token:
            conn = get_connection(config_name)
            if not conn:
                conn = get_default_connection()
            if conn:
                if not host:
                    host = conn.host
                if not token:
                    token = conn.token
                if not session_name:
                    session_name = conn.session
                if port == 8765 and conn.port != 8765:
                    port = conn.port
                touch_connection(conn.name)
                print(f"使用保存的配置: {conn.name}")

        normalized_args = argparse.Namespace(host=host, port=port, token=token, name=session_name)
        result = validate_remote_args(normalized_args, session_name)
        if result is None:
            return 1
        host, port, session_name, token = result

        if not session_name:
            print("错误: 请指定会话名称")
            return 1

        _log_remote_args("attach", host, port, session_name, token)

        # 保存配置
        if should_save:
            save_connection(
                name=config_name,
                host=host,
                port=port,
                token=token,
                session=session_name,
                is_default=(config_name == 'default')
            )
            print(f"已保存连接配置: {config_name}")

        # 运行远程客户端
        return _run_remote_client(host, session_name, token, port)

    # 本地模式
    # 检查会话是否存在
    if not is_session_active(session_name):
        print(f"错误: 会话 '{session_name}' 不存在")
        print("使用 'remote-claude list' 查看可用会话")
        return 1

    print(f"连接到会话: {session_name}")

    # 直接运行 client（不通过 tmux）
    from client.local_client import run_client
    return run_client(session_name)


def cmd_list(args):
    """列出所有会话（支持远程模式）"""
    # 远程模式
    if getattr(args, 'remote', False):
        result = validate_remote_args(args, session_fallback='list')
        if result is None:
            return 1
        host, port, session, token = result
        _log_remote_args("list", host, port, session or 'list', token)
        return run_remote_control(host, port, session or 'list', token, 'list')

    # 本地模式
    sessions = list_active_sessions()

    if not sessions:
        print("没有活跃的会话")
        return 0

    # 加载运行时配置获取会话映射
    from utils.runtime_config import load_state
    state = load_state()

    # ANSI 颜色码
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    RESET = "\033[0m"

    # 检查 --full 选项
    show_full = getattr(args, 'full', False)

    # 计算名称列最大宽度
    if show_full:
        name_col_width = max(len(s['name']) for s in sessions)
    else:
        name_col_width = 20

    # 计算路径列最大宽度
    def get_path(s):
        return _normalize_original_path(state.get_session_path(s['name']))

    if show_full:
        path_col_width = max(len(get_path(s)) for s in sessions)
    else:
        path_col_width = 52

    # 表头
    header = f"{'类型':<8} {'PID':<8} {'tmux':<6} {'名称':<{name_col_width}} {'原始路径':<{path_col_width}}"
    print("活跃会话:")
    print("-" * (8 + 8 + 6 + name_col_width + path_col_width + 4))
    print(header)
    print("-" * (8 + 8 + 6 + name_col_width + path_col_width + 4))

    for s in sessions:
        tmux_status = "是" if s["tmux"] else "否"
        cli_type = s.get('cli_type', 'claude')
        session_name = s['name']
        original_path = get_path(s)

        # 根据类型选择颜色
        cli_type_cls = _get_cli_type()
        if cli_type == cli_type_cls.CODEX:
            cli_colored = f"{GREEN}{cli_type}{RESET}"
        else:
            cli_colored = f"{YELLOW}{cli_type}{RESET}"
        # 带颜色的字段需要单独计算宽度
        padding = " " * (8 - len(cli_type))

        # 名称显示
        if show_full:
            name_display = session_name
        else:
            name_display = session_name[:18] + ".." if len(session_name) > 20 else session_name

        # 路径显示
        if show_full:
            path_display = original_path
        else:
            path_display = original_path[:50] + ".." if len(original_path) > 52 else original_path

        print(
            f"{cli_colored}{padding} {s['pid']:<8} {tmux_status:<6} {name_display:<{name_col_width}} {path_display:<{path_col_width}}")

    print("-" * (8 + 8 + 6 + name_col_width + path_col_width + 4))
    print(f"共 {len(sessions)} 个会话")

    return 0


def cmd_kill(args):
    """终止会话（支持远程模式）"""
    session_name = args.name

    # 远程模式
    if getattr(args, 'remote', False):
        result = validate_remote_args(args, session_name)
        if result is None:
            return 1
        host, port, session, token = result
        _log_remote_args("kill", host, port, session, token)
        return run_remote_control(host, port, session, token, 'kill')

    # 本地模式
    # 检查会话是否存在
    if not is_session_active(session_name) and not tmux_session_exists(session_name):
        print(f"错误: 会话 '{session_name}' 不存在")
        return 1

    print(f"终止会话: {session_name}")

    # 终止 tmux 会话
    if tmux_session_exists(session_name):
        tmux_kill_session(session_name)
        print("  - tmux 会话已终止")

    # 清理文件
    cleanup_session(session_name)

    from server.token_manager import TokenManager
    TokenManager(session_name).delete_token_file()
    print("  - 文件已清理")

    # 删除会话映射
    from utils.runtime_config import remove_session_mapping
    remove_session_mapping(session_name)

    print("完成")
    return 0


def cmd_status(args):
    """显示会话状态（支持远程模式）"""
    session_name = args.name

    # 远程模式
    if getattr(args, 'remote', False):
        result = validate_remote_args(args, session_name)
        if result is None:
            return 1
        host, port, session, token = result
        if not session:
            print("错误: 请指定会话名称")
            return 1
        _log_remote_args("status", host, port, session, token)
        return run_remote_control(host, port, session, token, 'status')

    # 本地模式
    if not is_session_active(session_name):
        print(f"错误: 会话 '{session_name}' 不存在")
        return 1

    # TODO: 实现状态查询
    print(f"会话 '{session_name}' 状态:")
    print("  (功能开发中)")
    return 0


def _watchdog_script_path() -> Path:
    return _get_user_data_dir() / "watchdog.sh"


def _watchdog_pid_file() -> Path:
    return _get_user_data_dir() / "watchdog.pid"


def _start_watchdog():
    """启动后台 watchdog（如果尚未运行）"""
    if not _watchdog_script_path().exists():
        return  # 脚本不存在时静默跳过
    # 检查是否已在运行
    if _watchdog_pid_file().exists():
        try:
            pid = int(_watchdog_pid_file().read_text().strip())
            os.kill(pid, 0)
            return  # 已在运行
        except (ProcessLookupError, ValueError, OSError):
            pass
    process = subprocess.Popen(
        ["bash", str(_watchdog_script_path())],
        stdout=subprocess.DEVNULL,  # watchdog 通过 tee 自己写 $LOG，不需要 stdout 捕获
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print(f"  watchdog: 已启动 (PID: {process.pid})")


def _stop_watchdog():
    """停止后台 watchdog"""
    if not _watchdog_pid_file().exists():
        return
    try:
        pid = int(_watchdog_pid_file().read_text().strip())
        os.kill(pid, signal.SIGTERM)
        print(f"  watchdog: 已停止 (PID: {pid})")
    except (ProcessLookupError, ValueError, OSError):
        pass
    _watchdog_pid_file().unlink(missing_ok=True)


def cmd_lark_start(args):
    """启动飞书客户端（守护进程）"""
    if is_lark_running():
        print("飞书客户端已在运行")
        status = get_lark_status()
        if status:
            print(f"PID: {status['pid']}")
            print(f"启动时间: {status['start_time']}")
            print(f"运行时长: {status['uptime']}")
        print("\n使用 'remote-claude lark stop' 停止")
        return 1

    # 检测残留的 bak 文件
    from utils.runtime_config import check_stale_backup, prompt_backup_action, cleanup_backup_files
    bak_file = check_stale_backup()
    if bak_file:
        action = prompt_backup_action(bak_file)
        if action == 'overwrite':
            # 从 bak 恢复
            print("正在从备份恢复配置...")
            try:
                # bak_file.name = "config.json.bak.20260320_143015" ->. split('.bak')[0] = "config.json"
                original_file = bak_file.name.split('.bak')[0]
                original_path = bak_file.parent / original_file
                import shutil
                shutil.copy2(bak_file, original_path)
                print(f"已从备份恢复: {original_path}")
                bak_file.unlink()
            except (OSError, shutil.Error) as e:
                print(f"恢复备份失败: {e}")
                return 1
        else:
            # 跳过：删除 bak 文件
            bak_file.unlink()
            print(f"已删除备份文件: {bak_file}")

    # 清理可能残留的其他 bak 文件
    cleanup_backup_files()

    print("正在启动飞书客户端...")

    ensure_socket_dir()
    ensure_user_data_dir()

    # 启动守护进程（使用 -m 模块方式运行，确保相对导入正常工作）
    log_file = _get_role_log_path("lark")

    try:
        # 启动进程
        process = subprocess.Popen(
            ["uv", "run", "--project", str(SCRIPT_DIR), "python3", "-m", "lark_client.main"],
            stdout=open(log_file, 'a'),
            stderr=subprocess.STDOUT,
            start_new_session=True,  # 创建新的进程组
            cwd=str(SCRIPT_DIR)
        )

        # 保存 PID
        pid = process.pid
        get_lark_pid_file().write_text(str(pid))
        save_lark_status(pid)

        # 等待一下确认启动成功
        time.sleep(1)

        if is_lark_running():
            print(f"✓ 飞书客户端已启动")
            print(f"  PID: {pid}")
            print(f"  日志: {log_file}")
            print(f"\n使用 'remote-claude lark status' 查看状态")
            print(f"使用 'remote-claude lark stop' 停止")
            _start_watchdog()
            return 0
        else:
            print("✗ 启动失败，请查看日志:")
            print(f"  tail -f {log_file}")
            cleanup_lark()
            return 1

    except Exception as e:
        print(f"✗ 启动失败: {e}")
        cleanup_lark()
        return 1


def cmd_lark_stop(args):
    """停止飞书客户端"""
    if not is_lark_running():
        print("飞书客户端未运行")
        cleanup_lark()
        return 0

    pid = get_lark_pid()
    if pid is None:
        print("无法获取 PID，清理残留文件")
        cleanup_lark()
        return 1

    print(f"正在停止飞书客户端 (PID: {pid})...")

    try:
        # 发送 SIGTERM 信号
        os.kill(pid, signal.SIGTERM)

        # 等待进程退出
        for i in range(50):  # 最多等待 5 秒
            if not is_lark_running():
                break
            time.sleep(0.1)
        else:
            # 如果还没退出，强制终止
            print("进程未响应，强制终止...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)

        if not is_lark_running():
            print("✓ 飞书客户端已停止")
            cleanup_lark()
            _stop_watchdog()
            return 0
        else:
            print("✗ 无法停止进程，请手动终止:")
            print(f"  kill -9 {pid}")
            return 1

    except ProcessLookupError:
        print("进程已不存在，清理残留文件")
        cleanup_lark()
        _stop_watchdog()
        return 0
    except PermissionError as e:
        print(f"✗ 权限不足，无法停止进程: {e}")
        return 1
    except OSError as e:
        print(f"✗ 停止失败（系统错误）: {e}")
        return 1
    except Exception as e:
        print(f"✗ 停止失败: {e}")
        return 1


def cmd_lark_restart(args):
    """重启飞书客户端"""
    print("正在重启飞书客户端...")

    # 先停止
    if is_lark_running():
        cmd_lark_stop(args)
        time.sleep(1)

    # 再启动
    return cmd_lark_start(args)


def cmd_lark_status(args):
    """显示飞书客户端状态"""
    if not is_lark_running():
        print("飞书客户端未运行")
        print("\n使用 'remote-claude lark start' 启动")
        return 0

    status = get_lark_status()
    if status is None:
        print("无法获取状态信息")
        return 1

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("飞书客户端状态")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"状态:     运行中 ✓")
    print(f"版本:     v{get_version()}")
    print(f"PID:      {status['pid']}")
    print(f"启动时间: {status['start_time']}")
    print(f"运行时长: {status['uptime']}")

    # 检查日志文件
    log_file = _get_role_log_path("lark")
    if log_file.exists():
        print(f"日志文件: {log_file}")
        print(f"日志大小: {log_file.stat().st_size / 1024:.1f} KB")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 显示最近的日志（最后 5 行）
    if log_file.exists():
        print("\n最近日志:")
        print("-" * 40)
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-5:]:
                    print(f"  {line.rstrip()}")
        except OSError as e:
            print(f"  无法读取日志（系统错误）: {e}")
        except Exception as e:
            print(f"  无法读取日志: {e}")
        print("-" * 40)

    return 0


def cmd_stats(args):
    """显示使用统计"""
    _PROJECT_ROOT = str(Path(__file__).parent)
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)

    from stats.query import query_summary, reset_stats
    from stats import report_daily

    if getattr(args, 'reset', False):
        print(reset_stats())
        return 0

    if getattr(args, 'report', False):
        report_daily()
        return 0

    range_str = getattr(args, 'range', 'today') or 'today'
    session_name = getattr(args, 'session', '') or ''
    detail = getattr(args, 'detail', False)

    print(query_summary(range_str=range_str, session_name=session_name, detail=detail))
    return 0


def cmd_update(args):
    """更新 remote-claude 到最新版本"""
    import subprocess as _sp

    git_dir = SCRIPT_DIR / ".git"
    if git_dir.exists():
        # 源码安装：git pull 更新
        print(f"检测到源码安装（{SCRIPT_DIR}）")
        print("正在更新...")
        result = _sp.run(["git", "pull"], cwd=SCRIPT_DIR)
        if result.returncode != 0:
            print("❌ git pull 失败")
            return 1
        # 同步 Python 依赖
        _sp.run(["uv", "sync"], cwd=SCRIPT_DIR)
        print("✅ 更新完成")
    else:
        # npm 安装：区分本地和全局
        install_dir_str = str(SCRIPT_DIR)
        if "node_modules" in install_dir_str:
            # 本地 npm 安装：找到项目根目录（node_modules 的上两级）
            project_root = SCRIPT_DIR.parent.parent
            print(f"检测到 npm 本地安装（{project_root}）")
            print("正在更新...")
            result = _sp.run(["npm", "install", "remote-claude@latest"], cwd=project_root)
        else:
            # 全局 npm 安装
            print("检测到 npm 全局安装")
            print("正在更新...")
            result = _sp.run(["npm", "install", "-g", "remote-claude@latest"])
        if result.returncode != 0:
            print("❌ npm 更新失败")
            return 1
        print("✅ 更新完成，请重启终端使新版本生效")
    return 0


def cmd_uninstall(args):
    """执行本地清理并提示卸载命令"""
    uninstall_script = SCRIPT_DIR / "scripts" / "uninstall.sh"
    if not uninstall_script.exists():
        print(f"✗ 未找到卸载脚本: {uninstall_script}")
        return 1

    command = ["sh", str(uninstall_script)]
    if getattr(args, "yes", False):
        command.append("--yes")

    result = subprocess.run(command, cwd=str(SCRIPT_DIR))
    if result.returncode != 0:
        return result.returncode

    print()
    print("Remote Claude 本地清理已完成。")
    print("如需卸载包，请按安装方式执行：")
    print("  npm uninstall -g remote-claude")
    print("  pnpm remove -g remote-claude")
    return 0


def cmd_connect(args):
    """连接到远程会话"""
    # 解析 host/session/port
    host = args.host
    session = args.session
    port = args.port or 8765
    token = args.token

    # 支持 host:port/session 格式
    if '/' in host:
        parts = host.split('/')
        host_part = parts[0]
        session = parts[1] if len(parts) > 1 else session
        if ':' in host_part:
            host, port_str = host_part.split(':')
            port = int(port_str)

    if not session:
        print("错误: 请指定会话名称")
        return 1

    return _run_remote_client(host, session, token, port)


def cmd_remote(args):
    """远程控制命令"""
    import asyncio

    host = args.host
    session = args.session
    token = args.token
    port = args.port or 8765

    # 解析 host:port/session 格式
    if '/' in host:
        parts = host.split('/')
        host_part = parts[0]
        session = parts[1] if len(parts) > 1 else session
        if ':' in host_part:
            host, port_str = host_part.split(':')
            port = int(port_str)

    if not session:
        print("错误: 请指定会话名称")
        return 1

    client = _build_remote_client(host, session, token, port)

    async def run_action():
        try:
            result = await client.send_control(args.action)
            if result['success']:
                print(f"✓ {result['message']}")
                return 0
            else:
                print(f"✗ {result['message']}")
                return 1
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return 1

    return asyncio.run(run_action())


def cmd_token(args):
    """显示会话 token（支持远程模式）"""
    session_name = args.session

    # 远程模式
    if getattr(args, 'remote', False):
        result = validate_remote_args(args, session_name)
        if result is None:
            return 1
        host, port, session, token = result
        if not session:
            print("错误: 请指定会话名称")
            return 1
        return run_remote_control(host, port, session, token, 'token')

    # 本地模式
    from server.token_manager import TokenManager

    manager = TokenManager(session_name, _get_user_data_dir())
    token = manager.get_or_create_token()
    print(f"Session: {session_name}")
    print(f"Token: {token}")
    return 0


def cmd_regenerate_token(args):
    """重新生成 token（支持远程模式）"""
    session_name = args.session

    # 远程模式
    if getattr(args, 'remote', False):
        result = validate_remote_args(args, session_name)
        if result is None:
            return 1
        host, port, session, token = result
        if not session:
            print("错误: 请指定会话名称")
            return 1
        return run_remote_control(host, port, session, token, 'regenerate-token')

    # 本地模式
    from server.token_manager import TokenManager

    manager = TokenManager(session_name, _get_user_data_dir())
    old_token = manager._token
    new_token = manager.regenerate_token()
    print(f"Session: {session_name}")
    print(f"旧 Token 已失效")
    print(f"新 Token: {new_token}")
    return 0


def cmd_lark_status_or_help(args):
    """飞书客户端管理默认入口。"""
    parser = getattr(args, '_subparser', None)
    if parser is not None:
        parser.print_help()
        return 0

    if is_lark_running():
        return cmd_lark_status(args)

    print("飞书客户端未运行")
    print("\n可用命令:")
    print("  remote-claude lark start    - 启动客户端")
    print("  remote-claude lark stop     - 停止客户端")
    print("  remote-claude lark restart  - 重启客户端")
    print("  remote-claude lark status   - 查看状态")
    return 0


def cmd_config(args):
    """配置管理（无子命令时显示帮助）"""
    print("配置管理命令:")
    print("\n  remote-claude config reset [选项]")
    print()
    print("选项:")
    print("  --all       重置全部配置文件（settings.json + state.json）")
    print("  --settings  仅重置用户配置（settings.json）")
    print("  --state     仅重置运行时配置（state.json）")
    print()
    print("不带选项时进入交互式选择模式")
    return 0


def cmd_config_reset(args):
    """配置重置命令"""
    from utils.runtime_config import (
        USER_DATA_DIR,
        cleanup_backup_files,
        ConfigType,
        SETTINGS_FILE,
        STATE_FILE,
        SETTINGS_LOCK_FILE,
        STATE_LOCK_FILE
    )

    # 确定要重置的配置文件
    reset_all = getattr(args, 'all', False)
    reset_settings = getattr(args, 'settings_only', False)
    reset_state = getattr(args, 'state_only', False)

    if not (reset_all or reset_settings or reset_state):
        # 交互式选择
        print("选择要重置的配置：")
        print("1. 全部配置（settings.json + state.json）")
        print("2. 仅用户配置（settings.json）")
        print("3. 仅运行时配置（state.json）")
        print("4. 取消")
        try:
            choice = input("请选择 [1-4]: ").strip()
        except EOFError:
            print("\n已取消")
            return 1

        if choice == '1':
            reset_all = True
        elif choice == '2':
            reset_settings = True
        elif choice == '3':
            reset_state = True
        else:
            print("已取消")
            return 0

    config_template = SCRIPT_DIR / "resources" / "defaults" / "settings.json.example"
    runtime_template = SCRIPT_DIR / "resources" / "defaults" / "state.json.example"

    if not config_template.exists():
        print(f"✗ 未找到配置模板: {config_template}")
        return 1

    if not runtime_template.exists():
        print(f"✗ 未找到运行时模板: {runtime_template}")
        return 1

    # 执行重置
    try:
        if reset_all or reset_settings:
            SETTINGS_FILE.write_text(config_template.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"✓ 已重置用户配置: {SETTINGS_FILE}")

        if reset_all or reset_state:
            STATE_FILE.write_text(runtime_template.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"✓ 已重置运行时配置: {STATE_FILE}")

        # 清理副作用文件（锁文件、备份文件），范围与重置配置保持一致
        # 状态文件（lark.pid、lark.status）不清理
        if reset_all or reset_settings:
            try:
                SETTINGS_LOCK_FILE.unlink()
                print(f"✓ 已清理锁文件: {SETTINGS_LOCK_FILE}")
            except FileNotFoundError:
                pass
            cleanup_backup_files(ConfigType.SETTINGS)
            print("✓ 已清理 settings 备份文件")

        if reset_all or reset_state:
            try:
                STATE_LOCK_FILE.unlink()
                print(f"✓ 已清理锁文件: {STATE_LOCK_FILE}")
            except FileNotFoundError:
                pass
            cleanup_backup_files(ConfigType.STATE)
            print("✓ 已清理 state 备份文件")

        print()
        print("配置重置完成")
        return 0

    except PermissionError:
        print(f"✗ 权限不足，无法写入配置目录: {USER_DATA_DIR}")
        return 1
    except OSError as e:
        print(f"✗ 重置失败（系统错误）: {e}")
        return 1


def cmd_deps(args):
    """检查并安装依赖"""
    import shutil

    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    RESET = "\033[0m"

    def print_ok(msg):
        print(f"{GREEN}✓{RESET} {msg}")

    def print_warn(msg):
        print(f"{YELLOW}⚠{RESET} {msg}")

    def print_err(msg):
        print(f"{RED}✗{RESET} {msg}")

    print(f"\n{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{GREEN}  依赖检查{RESET}")
    print(f"{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}\n")

    # 检查 uv
    uv_path = shutil.which("uv")
    if uv_path:
        r = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        print_ok(f"uv: {r.stdout.strip()}")
    else:
        print_err("uv: 未安装")

    # 检查 claude CLI
    claude_path = shutil.which("claude")
    if claude_path:
        print_ok("Claude CLI: 已安装")
    else:
        print_warn("Claude CLI: 未安装")

    # 检查 codex CLI
    codex_path = shutil.which("codex")
    if codex_path:
        print_ok("Codex CLI: 已安装")
    else:
        print_warn("Codex CLI: 未安装（可选）")

    # 检查 tmux
    REQUIRED_MAJOR = 3
    REQUIRED_MINOR = 6

    tmux_path = shutil.which("tmux")
    tmux_ok = False
    if tmux_path:
        r = subprocess.run(["tmux", "-V"], capture_output=True, text=True)
        ver_str = r.stdout.strip().split()[-1] if r.stdout.strip() else "0.0"
        parts = ver_str.replace("a", "").replace("b", "").replace("c", "").split(".")
        try:
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            major, minor = 0, 0
        if major > REQUIRED_MAJOR or (major == REQUIRED_MAJOR and minor >= REQUIRED_MINOR):
            print_ok(f"tmux: {r.stdout.strip()}（满足 >= {REQUIRED_MAJOR}.{REQUIRED_MINOR}）")
            tmux_ok = True
        else:
            print_warn(f"tmux: {r.stdout.strip()}（需要 >= {REQUIRED_MAJOR}.{REQUIRED_MINOR}）")
    else:
        print_err("tmux: 未安装")

    if tmux_ok:
        print(f"\n{GREEN}所有关键依赖已满足。{RESET}")
        return 0

    # tmux 版本不满足，提供源码编译安装
    print(f"\n{YELLOW}tmux 版本不满足要求，是否从源码编译安装 tmux 3.6a？{RESET}")
    print(f"  安装位置: $HOME/.local（不需要 root 权限）")
    print(f"  编译依赖安装可能需要 sudo 密码\n")

    try:
        answer = input("继续？[y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return 0

    if answer not in ("y", "yes"):
        print("已跳过 tmux 安装。")
        return 0

    # 安装编译依赖
    print(f"\n{YELLOW}[1/4] 安装编译依赖...{RESET}")
    os_name = os.uname().sysname
    if os_name == "Darwin":
        subprocess.run(["brew", "install", "libevent", "ncurses", "pkg-config", "bison"], check=False)
    elif os_name == "Linux":
        if shutil.which("apt-get"):
            subprocess.run(["sudo", "apt-get", "update"], check=False)
            subprocess.run(["sudo", "apt-get", "install", "-y",
                          "build-essential", "libevent-dev", "libncurses5-dev",
                          "libncursesw5-dev", "bison", "pkg-config"], check=False)
        elif shutil.which("yum"):
            subprocess.run(["sudo", "yum", "groupinstall", "-y", "Development Tools"], check=False)
            subprocess.run(["sudo", "yum", "install", "-y",
                          "libevent-devel", "ncurses-devel", "bison"], check=False)
        else:
            print_warn("无法识别包管理器，请手动安装编译依赖: libevent-dev ncurses-dev bison pkg-config")

    # 下载源码
    print(f"\n{YELLOW}[2/4] 下载 tmux 3.6a 源码...{RESET}")
    import tempfile
    tmpdir = tempfile.mkdtemp()
    tarball = os.path.join(tmpdir, "tmux.tar.gz")
    tmux_url = "https://github.com/tmux/tmux/releases/download/3.6a/tmux-3.6a.tar.gz"

    r = subprocess.run(["curl", "-fsSL", tmux_url, "-o", tarball])
    if r.returncode != 0:
        print_err("下载失败，请检查网络连接。")
        return 1

    subprocess.run(["tar", "-xzf", tarball, "-C", tmpdir], check=True)
    src_dir = os.path.join(tmpdir, "tmux-3.6a")

    # 编译
    prefix = os.path.join(os.path.expanduser("~"), ".local")
    print(f"\n{YELLOW}[3/4] 编译 tmux（安装到 {prefix}）...{RESET}")

    nproc = "2"
    try:
        r = subprocess.run(["nproc"], capture_output=True, text=True)
        if r.returncode == 0:
            nproc = r.stdout.strip()
    except FileNotFoundError:
        pass

    r = subprocess.run(
        f"./configure --prefix={prefix} && make -j{nproc} && make install",
        shell=True, cwd=src_dir
    )
    if r.returncode != 0:
        print_err("编译失败，请检查编译依赖是否已安装。")
        return 1

    # 清理临时目录
    import shutil as _shutil
    _shutil.rmtree(tmpdir, ignore_errors=True)

    # 配置 PATH
    print(f"\n{YELLOW}[4/4] 配置 PATH...{RESET}")
    local_bin = os.path.join(prefix, "bin")
    os.environ["PATH"] = f"{local_bin}:{os.environ.get('PATH', '')}"

    if f"{local_bin}" not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{local_bin}:{os.environ['PATH']}"

    # 写入 shell rc
    shell_name = os.path.basename(os.environ.get("SHELL", "bash"))
    rc_file = os.path.join(os.path.expanduser("~"), ".zshrc" if shell_name == "zsh" else ".bashrc")
    path_line = 'export PATH="$HOME/.local/bin:$PATH"'
    try:
        rc_content = open(rc_file).read() if os.path.exists(rc_file) else ""
        if "$HOME/.local/bin" not in rc_content:
            with open(rc_file, "a") as f:
                f.write(f"\n# remote-claude: tmux 路径\n{path_line}\n")
            print_ok(f"已将 $HOME/.local/bin 写入 {rc_file}")
    except Exception as e:
        print_warn(f"无法写入 {rc_file}: {e}")

    # 验证
    tmux_bin = os.path.join(local_bin, "tmux")
    if os.path.exists(tmux_bin):
        r = subprocess.run([tmux_bin, "-V"], capture_output=True, text=True)
        print(f"\n{GREEN}✓ tmux 安装成功: {r.stdout.strip()}{RESET}")
        print(f"  路径: {tmux_bin}")
        print(f"  请运行 source {rc_file} 或重新打开终端使 PATH 生效。")
    else:
        print_err("安装似乎未成功，请检查上方输出。")
        return 1

    return 0


def cmd_lark_init(args):
    """飞书机器人配置向导（扫码自动创建应用）"""
    from lark_client.setup_wizard import SetupWizard
    check_only = getattr(args, "check", False)
    new_only = getattr(args, "new", False)
    wizard = SetupWizard(check_only=check_only, new_only=new_only)
    rc = wizard.run()
    if rc == 0 and not check_only and not new_only:
        print("\n正在重启飞书客户端以应用新配置...")
        cmd_lark_restart(args)
    return rc


def cmd_connection(args):
    """管理保存的远程连接配置"""
    from client.connection_config import (
        list_connections, get_connection, delete_connection, set_default_connection
    )

    action = args.connection_action

    if action == 'list':
        connections = list_connections()
        if not connections:
            print("没有保存的连接配置")
            return 0

        print("保存的连接配置:")
        print("-" * 70)
        print(f"{'名称':<15} {'主机':<25} {'端口':<8} {'会话':<15} {'默认'}")
        print("-" * 70)
        for conn in connections:
            default_mark = "✓" if conn.is_default else ""
            session_display = conn.session[:13] + ".." if len(conn.session) > 15 else conn.session
            host_display = conn.host[:23] + ".." if len(conn.host) > 25 else conn.host
            print(f"{conn.name:<15} {host_display:<25} {conn.port:<8} {session_display:<15} {default_mark}")
        return 0

    elif action == 'show':
        name = args.name
        conn = get_connection(name)
        if not conn:
            print(f"错误: 配置 '{name}' 不存在")
            return 1

        print(f"配置名称: {conn.name}")
        print(f"主机地址: {conn.host}")
        print(f"端口: {conn.port}")
        print(f"会话: {conn.session or '(未设置)'}")
        print(f"Token: {'*' * 8} (已保存)")
        print(f"描述: {conn.description or '(无)'}")
        print(f"创建时间: {conn.created_at or '(未知)'}")
        print(f"最后使用: {conn.last_used or '(从未使用)'}")
        print(f"默认配置: {'是' if conn.is_default else '否'}")
        return 0

    elif action == 'delete':
        name = args.name
        if delete_connection(name):
            print(f"✓ 已删除配置: {name}")
            return 0
        else:
            print(f"错误: 配置 '{name}' 不存在")
            return 1

    elif action == 'set-default':
        name = args.name
        conn = get_connection(name)
        if not conn:
            print(f"错误: 配置 '{name}' 不存在")
            return 1

        if set_default_connection(name):
            print(f"✓ 已将 '{name}' 设为默认配置")
            return 0
        print(f"错误: 配置 '{name}' 不存在")
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="remote-claude",
        description="Remote Claude - 双端共享 Claude/Codex CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s start mywork                  启动名为 mywork 的会话（使用默认启动器）
  %(prog)s start mywork --launcher Codex 使用 Codex 启动器启动会话
  %(prog)s start mywork -l Codex         同上（简写）
  %(prog)s attach mywork                 连接到 mywork 会话
  %(prog)s list                      列出所有会话
  %(prog)s kill mywork               终止 mywork 会话
  %(prog)s status mywork             显示 mywork 会话状态

飞书客户端:
  %(prog)s lark init                 配置向导（首次使用，扫码自动创建应用）
  %(prog)s lark init --check         检查当前配置状态
  %(prog)s lark init --new           扫码创建新应用（不修改已有配置）
  %(prog)s lark start                启动飞书客户端
  %(prog)s lark stop                 停止飞书客户端
  %(prog)s lark restart              重启飞书客户端
  %(prog)s lark status               查看飞书客户端状态

终端控制:
  Ctrl+D       断开连接

飞书命令:
  /attach <名称>   连接到会话
  /detach          断开连接
  /list            列出会话
  /help            显示帮助

使用统计:
  %(prog)s stats                     今日概览
  %(prog)s stats --range 7d          最近 7 天
  %(prog)s stats --detail            详细分类
  %(prog)s stats --session mywork    按会话筛选
  %(prog)s stats --reset             清空数据

更新:
  %(prog)s update                    更新到最新版本

远程连接:
  %(prog)s start mywork --remote                    启动会话并开启远程连接
  %(prog)s connect <host>:<port>/<session> --token <TOKEN>  连接远程会话

依赖管理:
  %(prog)s deps                      检查依赖并安装（含 tmux 源码编译）
"""
    )

    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"remote-claude v{get_version()}",
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # start 命令
    start_parser = subparsers.add_parser("start", help="启动新会话")
    start_parser.add_argument("name", help="会话名称")
    start_parser.add_argument(
        "cli_args",
        nargs="*",
        help="传递给 CLI 的参数"
    )
    start_parser.add_argument(
        "--debug-screen",
        action="store_true",
        help="开启 pyte 屏幕快照调试日志（每次 flush 写入 /tmp/remote-claude/<name>_screen.log）"
    )
    start_parser.add_argument(
        "--debug-verbose",
        action="store_true",
        help="debug 日志输出完整诊断信息（indicator、repr 等），默认只输出 ansi_render"
    )
    start_parser.add_argument(
        "--launcher", "-l",
        default=None,
        help="启动器名称（对应 settings.launchers[].name），不指定则使用第一个"
    )
    start_parser.add_argument(
        "--remote",
        action="store_true",
        help="启用远程连接模式"
    )
    start_parser.add_argument(
        "--remote-port",
        type=int,
        default=8765,
        help="远程连接端口（默认: 8765）"
    )
    start_parser.add_argument(
        "--remote-host",
        default="0.0.0.0",
        help="远程连接监听地址（默认: 0.0.0.0）"
    )
    start_parser.set_defaults(func=cmd_start)

    # attach 命令
    attach_parser = subparsers.add_parser("attach", help="连接到已有会话")
    attach_parser.add_argument("name", nargs="?", default="", help="会话名称（可选，使用保存的配置时可省略）")
    attach_parser.add_argument(
        "--remote",
        action="store_true",
        help="远程连接模式"
    )
    attach_parser.add_argument(
        "--host",
        default="",
        help="远程服务器地址（支持 host:port/session 格式)"
    )
    attach_parser.add_argument(
        "--token",
        default="",
        help="认证令牌(远程模式必需)"
    )
    attach_parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="远程服务器端口(默认: 8765)"
    )
    attach_parser.add_argument(
        "--save",
        action="store_true",
        help="保存当前连接配置到本地"
    )
    attach_parser.add_argument(
        "--config-name",
        default="",
        help="使用/保存的配置名称（默认: default）"
    )
    attach_parser.set_defaults(func=cmd_attach)

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有会话")
    list_parser.add_argument("--full", action="store_true", help="显示完整名称（不截断）")
    add_remote_args(list_parser)
    list_parser.set_defaults(func=cmd_list)

    # kill 命令
    kill_parser = subparsers.add_parser("kill", help="终止会话")
    kill_parser.add_argument("name", help="会话名称")
    add_remote_args(kill_parser)
    kill_parser.set_defaults(func=cmd_kill)

    # status 命令
    status_parser = subparsers.add_parser("status", help="显示会话状态")
    status_parser.add_argument("name", help="会话名称")
    add_remote_args(status_parser)
    status_parser.set_defaults(func=cmd_status)

    # lark 命令（带子命令）
    lark_parser = subparsers.add_parser("lark", help="飞书客户端管理")
    lark_parser.set_defaults(func=cmd_lark_status_or_help, _subparser=lark_parser)
    lark_subparsers = lark_parser.add_subparsers(dest="lark_command", help="飞书客户端操作")

    # lark start
    lark_start_parser = lark_subparsers.add_parser("start", help="启动飞书客户端")
    lark_start_parser.set_defaults(func=cmd_lark_start)

    # lark stop
    lark_stop_parser = lark_subparsers.add_parser("stop", help="停止飞书客户端")
    lark_stop_parser.set_defaults(func=cmd_lark_stop)

    # lark restart
    lark_restart_parser = lark_subparsers.add_parser("restart", help="重启飞书客户端")
    lark_restart_parser.set_defaults(func=cmd_lark_restart)

    # lark status
    lark_status_parser = lark_subparsers.add_parser("status", help="查看飞书客户端状态")
    lark_status_parser.set_defaults(func=cmd_lark_status)

    # lark init
    lark_init_parser = lark_subparsers.add_parser("init", help="配置向导（扫码自动创建应用）")
    lark_init_group = lark_init_parser.add_mutually_exclusive_group()
    lark_init_group.add_argument("--check", action="store_true", help="仅检查当前配置状态")
    lark_init_group.add_argument("--new", action="store_true", help="扫码创建新应用（不修改已有配置）")
    lark_init_parser.set_defaults(func=cmd_lark_init)

    # config 命令（带子命令）
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_subparsers = config_parser.add_subparsers(dest="config_command", help="配置操作")

    # config reset
    config_reset_parser = config_subparsers.add_parser("reset", help="重置 settings.json / state.json（不删除 .env）")
    config_reset_parser.add_argument(
        "--all", action="store_true",
        help="重置全部配置文件"
    )
    config_reset_parser.add_argument(
        "--settings", dest="settings_only", action="store_true",
        help="仅重置用户配置"
    )
    config_reset_parser.add_argument(
        "--state", dest="state_only", action="store_true",
        help="仅重置运行时配置"
    )
    config_reset_parser.set_defaults(func=cmd_config_reset)

    # 如果只输入 config 没有子命令
    config_parser.set_defaults(func=cmd_config)

    # connection 命令 - 管理远程连接配置
    connection_parser = subparsers.add_parser("connection", help="管理远程连接配置",
                                              aliases=["conn"])
    connection_subparsers = connection_parser.add_subparsers(dest="connection_action", help="连接操作")

    # connection list
    conn_list_parser = connection_subparsers.add_parser("list", help="列出所有保存的连接配置")
    conn_list_parser.set_defaults(func=cmd_connection, connection_action='list')

    # connection show
    conn_show_parser = connection_subparsers.add_parser("show", help="显示连接配置详情")
    conn_show_parser.add_argument("name", help="配置名称")
    conn_show_parser.set_defaults(func=cmd_connection, connection_action='show')

    # connection delete
    conn_delete_parser = connection_subparsers.add_parser("delete", help="删除连接配置")
    conn_delete_parser.add_argument("name", help="配置名称")
    conn_delete_parser.set_defaults(func=cmd_connection, connection_action='delete')

    # connection set-default
    conn_default_parser = connection_subparsers.add_parser("set-default", help="设置默认连接配置")
    conn_default_parser.add_argument("name", help="配置名称")
    conn_default_parser.set_defaults(func=cmd_connection, connection_action='set-default')

    # 如果只输入 connection 没有子命令，默认显示列表
    connection_parser.set_defaults(func=cmd_connection, connection_action='list')

    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="查看使用统计")
    stats_parser.add_argument(
        "--range", metavar="RANGE", default="today",
        help="时间范围：today（默认）、7d、30d、90d"
    )
    stats_parser.add_argument(
        "--detail", action="store_true",
        help="显示详细分类"
    )
    stats_parser.add_argument(
        "--session", metavar="NAME", default="",
        help="按会话名筛选"
    )
    stats_parser.add_argument(
        "--reset", action="store_true",
        help="清空所有统计数据"
    )
    stats_parser.add_argument(
        "--report", action="store_true",
        help="立即触发 Mixpanel 聚合上报"
    )
    stats_parser.set_defaults(func=cmd_stats)

    # update 命令
    update_parser = subparsers.add_parser("update", help="更新 remote-claude 到最新版本")
    update_parser.set_defaults(func=cmd_update)

    # uninstall 命令
    uninstall_parser = subparsers.add_parser("uninstall", help="清理本地数据并提示卸载命令")
    uninstall_parser.add_argument("-y", "--yes", action="store_true", help="跳过确认，直接执行清理")
    uninstall_parser.set_defaults(func=cmd_uninstall)

    # connect 命令
    connect_parser = subparsers.add_parser("connect", help="连接到远程会话")
    connect_parser.add_argument("host", help="服务器地址（或 host:port/session）")
    connect_parser.add_argument("session", nargs="?", help="会话名称")
    connect_parser.add_argument("--token", required=True, help="认证 token")
    connect_parser.add_argument("--port", type=int, help="端口（默认: 8765）")
    connect_parser.set_defaults(func=cmd_connect)

    # remote 命令
    remote_parser = subparsers.add_parser("remote", help="远程控制（shutdown/restart/update）")
    remote_parser.add_argument("action", choices=["shutdown", "restart", "update"], help="远程控制动作")
    remote_parser.add_argument("host", help="服务器地址（或 host:port/session）")
    remote_parser.add_argument("session", nargs="?", help="会话名称")
    remote_parser.add_argument("--token", required=True, help="认证 token")
    remote_parser.add_argument("--port", type=int, help="端口")
    remote_parser.set_defaults(func=cmd_remote)

    # token 命令
    token_parser = subparsers.add_parser("token", help="显示会话 token")
    token_parser.add_argument("session", help="会话名称")
    token_parser.add_argument("--remote", action="store_true", help="远程模式")
    token_parser.add_argument("--host", help="远程主机")
    token_parser.add_argument("--port", type=int, help="远程端口")
    token_parser.add_argument("--token", help="连接 token")
    token_parser.set_defaults(func=cmd_token)

    # regenerate-token 命令
    regen_parser = subparsers.add_parser("regenerate-token", help="重新生成会话 token")
    regen_parser.add_argument("session", help="会话名称")
    regen_parser.add_argument("--remote", action="store_true", help="远程模式")
    regen_parser.add_argument("--host", help="远程主机")
    regen_parser.add_argument("--port", type=int, help="远程端口")
    regen_parser.add_argument("--token", help="连接 token")
    regen_parser.set_defaults(func=cmd_regenerate_token)

    # deps 命令
    deps_parser = subparsers.add_parser("deps", help="检查并安装依赖（tmux 源码编译等）")
    deps_parser.set_defaults(func=cmd_deps)

    args, remaining = parser.parse_known_args()

    if args.command is None:
        parser.print_help()
        return 0

    # 将剩余参数合并到 cli_args（支持 cx/cdx 脚本中使用 -- 分隔符）
    if args.command == "start" and hasattr(args, 'cli_args'):
        args.cli_args = args.cli_args + remaining

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
