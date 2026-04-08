#!/usr/bin/env python3

import logging
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import remote_claude


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_parse_host_session_keeps_positional_session_name():
    args = SimpleNamespace(host="10.0.0.1", port=10000, token="t", name="assistant_public")
    host, port, session, token = remote_claude.parse_host_session(args)
    assert (host, port, session, token) == ("10.0.0.1", 10000, "assistant_public", "t")


def test_validate_remote_args_accepts_current_attach_order():
    args = SimpleNamespace(host="10.0.0.1", port=10000, token="t", name="assistant_public")
    assert remote_claude.validate_remote_args(args, "assistant_public") == (
        "10.0.0.1",
        10000,
        "assistant_public",
        "t",
    )


def test_bin_remote_claude_lark_help_exits_cleanly_without_env_prompt(tmp_path):
    home_dir = tmp_path / "lark_help_home"
    (home_dir / ".remote-claude").mkdir(parents=True)

    result = subprocess.run(
        [str(REPO_ROOT / "bin/remote-claude"), "lark", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home_dir)},
    )

    assert result.returncode == 0
    assert "飞书客户端尚未配置" not in result.stdout


def test_bin_remote_claude_help_exits_cleanly_without_spawning_session(tmp_path):
    home_dir = tmp_path / "remote_help_home"
    (home_dir / ".remote-claude").mkdir(parents=True)

    result = subprocess.run(
        [str(REPO_ROOT / "bin/remote-claude"), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home_dir)},
    )

    assert result.returncode == 0
    assert "remote_claude.py" not in result.stdout




def test_remote_claude_start_here_help_rewrites_to_plain_start_without_passing_here(tmp_path):
    home_dir = tmp_path / "start_here_help_home"
    startup_dir = tmp_path / "workspace" / "demo-project"
    (home_dir / ".remote-claude").mkdir(parents=True)
    startup_dir.mkdir(parents=True)

    result = subprocess.run(
        [str(REPO_ROOT / "bin/remote-claude"), "start", "--here", "--help"],
        cwd=startup_dir,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home_dir)},
    )

    assert result.returncode == 0
    assert "usage: remote-claude start" in result.stdout
    assert "--here" not in result.stdout


def test_remote_claude_top_level_here_is_treated_as_unknown_subcommand(tmp_path):
    home_dir = tmp_path / "top_level_here_home"
    startup_dir = tmp_path / "workspace" / "demo-project"
    (home_dir / ".remote-claude").mkdir(parents=True)
    startup_dir.mkdir(parents=True)

    result = subprocess.run(
        [str(REPO_ROOT / "bin/remote-claude"), "--here", "--help"],
        cwd=startup_dir,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home_dir)},
    )

    assert result.returncode == 0
    assert "--here" not in result.stdout
    assert "{start,attach,list,kill,status" in result.stdout


def test_remote_claude_start_here_conflicts_with_explicit_session_name(tmp_path):
    home_dir = tmp_path / "start_here_conflict_home"
    startup_dir = tmp_path / "workspace" / "demo-project"
    (home_dir / ".remote-claude").mkdir(parents=True)
    startup_dir.mkdir(parents=True)

    result = subprocess.run(
        [str(REPO_ROOT / "bin/remote-claude"), "start", "demo", "--here"],
        cwd=startup_dir,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home_dir)},
    )

    assert result.returncode != 0
    assert "--here 不能与显式会话名同时使用" in result.stdout


def test_main_help_advertises_current_public_management_commands(tmp_path):
    home_dir = tmp_path / "main_help_current_public_management_commands"
    (home_dir / ".remote-claude").mkdir(parents=True)

    install_dir_file = REPO_ROOT / "test-results" / "install_dir.txt"
    command_path = REPO_ROOT / "bin" / "remote-claude"
    command_cwd = REPO_ROOT
    env_overrides = {}
    if install_dir_file.exists():
        install_dir = Path(install_dir_file.read_text(encoding="utf-8").strip())
        candidate = install_dir / "node_modules" / "remote-claude"
        if candidate.exists():
            command_path = candidate / "bin" / "remote-claude"
            command_cwd = candidate
            env_overrides = {
                "REMOTE_CLAUDE_UV_PROJECT_DIR": str(candidate),
                "REMOTE_CLAUDE_FORCE_UV_RUN": "1",
            }
            broken_python = candidate / ".venv" / "bin" / "python3"
            if broken_python.exists() or broken_python.is_symlink():
                broken_python.unlink()

    result = subprocess.run(
        [str(command_path), "--help"],
        cwd=command_cwd,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home_dir), **env_overrides},
    )

    assert result.returncode == 0
    assert "connection       远程连接配置管理" in result.stdout
    assert "remote-claude attach mywork --remote --host host:8765 --token <token>" in result.stdout
    assert "remote-claude connect host:8765/mywork --token <token>" in result.stdout
    assert "remote-claude token mywork" in result.stdout
    assert "remote-claude regenerate-token mywork" in result.stdout
    assert "remote-claude remote restart <host>" in result.stdout
    assert "uninstall        清理环境" in result.stdout


def test_bin_remote_claude_supports_remote_token_and_regenerate_help_without_lazy_init_side_effects(tmp_path):
    home_dir = tmp_path / "remote_management_help_home"
    (home_dir / ".remote-claude").mkdir(parents=True)

    for command in (["remote", "--help"], ["token", "--help"], ["regenerate-token", "--help"]):
        result = subprocess.run(
            [str(REPO_ROOT / "bin/remote-claude"), *command],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home_dir)},
        )

        assert result.returncode == 0, (command, result.stderr)
        assert "请选择 Claude CLI 可执行文件" not in result.stdout
        assert "飞书客户端尚未配置" not in result.stdout


def test_cmd_remote_uses_current_remote_control_path(monkeypatch):
    calls = []

    class FakeClient:
        async def send_control(self, action):
            calls.append(("send_control", action))
            return {"success": True, "message": "ok"}

    def fake_build_remote_client(host, session, token, port):
        calls.append(("build", host, session, token, port))
        return FakeClient()

    monkeypatch.setattr(remote_claude, "_build_remote_client", fake_build_remote_client)

    args = SimpleNamespace(action="restart", host="10.0.0.1", port=10000, token="secret-token", session="demo")
    result = remote_claude.cmd_remote(args)

    assert result == 0
    assert calls == [
        ("build", "10.0.0.1", "demo", "secret-token", 10000),
        ("send_control", "restart"),
    ]



def test_cmd_token_uses_validate_remote_args_and_run_remote_control(monkeypatch):
    calls = []

    def fake_validate_remote_args(args, session_fallback=None):
        calls.append(("validate", args, session_fallback))
        return ("10.0.0.1", 10000, "demo", "secret-token")

    def fake_run_remote_control(host, port, session, token, operation):
        calls.append(("run", host, port, session, token, operation))
        return 0

    monkeypatch.setattr(remote_claude, "validate_remote_args", fake_validate_remote_args)
    monkeypatch.setattr(remote_claude, "run_remote_control", fake_run_remote_control)

    args = SimpleNamespace(session="demo", remote=True, host="10.0.0.1", port=10000, token="secret-token")
    result = remote_claude.cmd_token(args)

    assert result == 0
    assert calls[0][0] == "validate"
    assert calls[1] == ("run", "10.0.0.1", 10000, "demo", "secret-token", "token")



def test_cmd_regenerate_token_uses_validate_remote_args_and_run_remote_control(monkeypatch):
    calls = []

    def fake_validate_remote_args(args, session_fallback=None):
        calls.append(("validate", args, session_fallback))
        return ("10.0.0.1", 10000, "demo", "secret-token")

    def fake_run_remote_control(host, port, session, token, operation):
        calls.append(("run", host, port, session, token, operation))
        return 0

    monkeypatch.setattr(remote_claude, "validate_remote_args", fake_validate_remote_args)
    monkeypatch.setattr(remote_claude, "run_remote_control", fake_run_remote_control)

    args = SimpleNamespace(session="demo", remote=True, host="10.0.0.1", port=10000, token="secret-token")
    result = remote_claude.cmd_regenerate_token(args)

    assert result == 0
    assert calls[0][0] == "validate"
    assert calls[1] == ("run", "10.0.0.1", 10000, "demo", "secret-token", "regenerate-token")



def test_remote_list_does_not_require_session_name():
    args = SimpleNamespace(host="example.com", port=8765, token="secret-token", name="")

    result = remote_claude.validate_remote_args(args, session_fallback="list")

    assert result == ("example.com", 8765, "list", "secret-token")



def test_cmd_config_help_uses_settings_and_state_names(capsys):
    rc = remote_claude.cmd_config(SimpleNamespace())
    captured = capsys.readouterr()

    assert rc == 0
    assert "settings.json" in captured.out
    assert "state.json" in captured.out
    assert "config.json" not in captured.out
    assert "runtime.json" not in captured.out



def test_remote_connection_doc_matches_current_public_remote_surface():
    content = (REPO_ROOT / "docs" / "remote-connection.md").read_text(encoding="utf-8")

    assert "remote-claude start <session> --remote" in content
    assert "remote-claude attach ... --remote" in content
    assert "remote-claude connect ..." in content
    assert "remote-claude token <session>" in content
    assert "remote-claude regenerate-token <session>" in content
    assert "remote-claude remote <action> ..." in content
    assert "remote-claude lark start --remote" in content
    assert "stage=server_spawn" in content
    assert "stage=server_start_failed" in content
    assert "server_cmd_sanitized" in content
    assert "remote-claude` 是公开 CLI 主入口" in content
    assert "`cla`、`cl`、`cx`、`cdx` 仍是本地启动快捷脚本，不承担远程管理职责" in content



def test_developer_doc_matches_server_and_lark_boundaries():
    content = (REPO_ROOT / "docs" / "developer.md").read_text(encoding="utf-8")

    assert "`server/server.py`：PTY → parser → snapshot → shared memory 主链路，负责 PTY 代理、输出广播、远程连接与终端状态恢复" in content
    assert "`bin/cla`、`bin/cl`、`bin/cx`、`bin/cdx`：面向常用场景的快捷启动脚本，不承担远程管理入口职责" in content
    assert "`lark_client/`：飞书消息、卡片交互与共享状态展示，不负责字符串修复或 ANSI 清理" in content
    assert "`server/ws_handler.py`：WebSocket 鉴权、远程控制动作与远程 Lark 管理入口" in content



def test_feishu_client_doc_matches_current_lark_boundary_and_runtime_paths():
    content = (REPO_ROOT / "docs" / "feishu-client.md").read_text(encoding="utf-8")

    assert "~/.remote-claude/lark_client.log" in content
    assert "Lark 侧不做 ANSI 清理" in content
    assert "remote-claude lark stop" in content
    assert "rm -f /tmp/remote-claude/lark.pid" not in content
    assert "rm -f /tmp/remote-claude/lark.status" not in content



def test_readme_and_cli_reference_cover_current_public_management_surface():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    cli_doc = (REPO_ROOT / "docs" / "cli-reference.md").read_text(encoding="utf-8")
    remote_doc = (REPO_ROOT / "docs" / "remote-connection.md").read_text(encoding="utf-8")

    coverage_map = {
        "remote-claude status <会话名>": {readme, cli_doc},
        "remote-claude token <session>": {cli_doc, remote_doc},
        "remote-claude regenerate-token <session>": {cli_doc, remote_doc},
        "remote-claude uninstall": {cli_doc},
    }

    for text, sources in coverage_map.items():
        assert any(text in source for source in sources)



def test_management_subcommand_help_and_empty_invocation_do_not_create_side_effects(tmp_path):
    commands = [
        ["config", "--help"],
        ["connection", "--help"],
        ["conn", "--help"],
        ["connect", "--help"],
        ["uninstall", "--help"],
        ["connection", "list", "--help"],
        ["connection", "show", "--help"],
        ["connection", "delete", "--help"],
        ["connection", "set-default", "--help"],
        ["config", "reset", "--help"],
        ["lark", "--help"],
    ]

    install_dir_file = REPO_ROOT / "test-results" / "install_dir.txt"
    command_path = REPO_ROOT / "bin" / "remote-claude"
    command_cwd = REPO_ROOT
    env_overrides = {}
    broken_python = None
    if install_dir_file.exists():
        install_dir = Path(install_dir_file.read_text(encoding="utf-8").strip())
        candidate = install_dir / "node_modules" / "remote-claude"
        if candidate.exists():
            command_path = candidate / "bin" / "remote-claude"
            command_cwd = candidate
            env_overrides = {
                "REMOTE_CLAUDE_UV_PROJECT_DIR": str(candidate),
                "REMOTE_CLAUDE_FORCE_UV_RUN": "1",
            }
            broken_python = candidate / ".venv" / "bin" / "python3"

    for command in commands:
        home_dir = tmp_path / "_".join(command).replace("-", "_")
        (home_dir / ".remote-claude").mkdir(parents=True)

        if broken_python is not None and (broken_python.exists() or broken_python.is_symlink()):
            broken_python.unlink()

        before = {p.name for p in Path("/tmp/remote-claude").glob("*")}
        env = {**os.environ, "HOME": str(home_dir), **env_overrides}
        result = subprocess.run(
            [str(command_path), *command],
            cwd=command_cwd,
            capture_output=True,
            text=True,
            env=env,
        )
        after = {p.name for p in Path("/tmp/remote-claude").glob("*")}

        assert result.returncode == 0, (command, result.stdout, result.stderr)
        assert "检测到依赖变更，正在更新 Python 环境..." not in result.stdout, (command, result.stdout)
        assert "scripts/setup.sh --npm --lazy" not in result.stderr, (command, result.stderr)
        assert "飞书客户端尚未配置" not in result.stdout, (command, result.stdout)
        assert not any(name.startswith(home_dir.name) for name in after - before), (command, sorted(after - before))


def test_connection_shortcuts_fall_back_to_uv_when_system_python_too_old(tmp_path):
    install_dir_file = REPO_ROOT / "test-results" / "install_dir.txt"
    if not install_dir_file.exists():
        pytest.skip("requires installed package fixture")

    install_dir = Path(install_dir_file.read_text(encoding="utf-8").strip())
    candidate = install_dir / "node_modules" / "remote-claude"
    if not candidate.exists():
        pytest.skip("requires installed package fixture")

    home_dir = tmp_path / "connection_shortcut_old_python"
    (home_dir / ".remote-claude").mkdir(parents=True)
    broken_python = candidate / ".venv" / "bin" / "python3"
    if broken_python.exists() or broken_python.is_symlink():
        broken_python.unlink()

    shim_dir = tmp_path / "shim-bin"
    shim_dir.mkdir()
    (shim_dir / "python3").write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"--version\" ]; then\n"
        "  echo 'Python 3.9.0'\n"
        "  exit 0\n"
        "fi\n"
        "exec /usr/bin/python3 \"$@\"\n",
        encoding="utf-8",
    )
    (shim_dir / "python3").chmod(0o755)

    env = {
        **os.environ,
        "HOME": str(home_dir),
        "PATH": f"{shim_dir}:{os.environ.get('PATH', '')}",
        "REMOTE_CLAUDE_UV_PROJECT_DIR": str(candidate),
        "REMOTE_CLAUDE_FORCE_UV_RUN": "1",
    }

    result = subprocess.run(
        [str(candidate / "bin" / "remote-claude"), "connection"],
        cwd=candidate,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "scripts/setup.sh --npm --lazy" not in result.stderr
