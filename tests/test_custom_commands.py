#!/usr/bin/env python3
"""
启动器配置测试

测试覆盖：
1. Launcher 数据类
2. Settings 数据类
3. get_launcher 函数
4. 启动器配置的读取和保存
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import remote_claude

from utils.runtime_config import (
    Launcher,
    Settings,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestLauncherDataClass:
    """测试 Launcher 数据类"""

    def test_create_launcher(self):
        cmd = Launcher(
            name="claude",
            cli_type="claude",
            command="claude",
            desc="Claude Code CLI"
        )
        assert cmd.name == "claude"
        assert cmd.cli_type == "claude"
        assert cmd.command == "claude"
        assert cmd.desc == "Claude Code CLI"

    def test_launcher_to_dict(self):
        cmd = Launcher(
            name="codex",
            cli_type="codex",
            command="/usr/local/bin/codex",
            desc="OpenAI Codex CLI"
        )
        d = cmd.to_dict()
        assert d["name"] == "codex"
        assert d["cli_type"] == "codex"
        assert d["command"] == "/usr/local/bin/codex"
        assert d["desc"] == "OpenAI Codex CLI"

    def test_launcher_from_dict(self):
        data = {
            "name": "claude",
            "cli_type": "claude",
            "command": "claude",
            "desc": "Claude Code CLI"
        }
        cmd = Launcher.from_dict(data)
        assert cmd.name == "claude"
        assert cmd.cli_type == "claude"
        assert cmd.command == "claude"
        assert cmd.desc == "Claude Code CLI"

    def test_launcher_empty_name(self):
        with pytest.raises(ValueError, match="启动器名称不能为空"):
            Launcher(name="", cli_type="claude", command="test")

    def test_launcher_empty_command(self):
        with pytest.raises(ValueError, match="启动器命令不能为空"):
            Launcher(name="test", cli_type="claude", command="")

    def test_launcher_requires_cli_type(self):
        cmd = Launcher(name="Claude", cli_type="claude", command="claude")
        assert cmd.cli_type == "claude"

        with pytest.raises(ValueError, match="CLI 类型不能为空"):
            Launcher(name="Test", cli_type="", command="test")

        with pytest.raises(ValueError, match="CLI 类型必须是"):
            Launcher(name="Test", cli_type="invalid", command="test")


class TestSettingsDataClass:
    """测试 Settings 数据类"""

    def test_create_settings(self):
        settings = Settings(
            launchers=[
                Launcher("claude", "claude", "claude"),
                Launcher("codex", "codex", "codex"),
            ]
        )
        assert len(settings.launchers) == 2

    def test_get_launcher(self):
        settings = Settings(
            launchers=[
                Launcher("claude", "claude", "/usr/local/bin/claude"),
                Launcher("codex", "codex", "codex"),
            ]
        )
        assert settings.get_launcher("claude").command == "/usr/local/bin/claude"
        assert settings.get_launcher("codex").command == "codex"
        assert settings.get_launcher("unknown") is None

    def test_get_default_launcher(self):
        settings = Settings(
            launchers=[
                Launcher("claude", "claude", "/usr/local/bin/claude"),
            ]
        )
        assert settings.get_default_launcher().command == "/usr/local/bin/claude"
        empty_settings = Settings()
        assert empty_settings.get_default_launcher() is None

    def test_settings_roundtrip(self):
        settings = Settings()
        settings.launchers = [
            Launcher("claude", "claude", "/opt/claude", "Custom Claude"),
            Launcher("codex", "codex", "/opt/codex", "Custom Codex"),
        ]
        data = settings.to_dict()
        loaded = Settings.from_dict(data)
        assert len(loaded.launchers) == 2
        assert loaded.launchers[0].name == "claude"
        assert loaded.launchers[0].cli_type == "claude"
        assert loaded.launchers[0].command == "/opt/claude"


class TestGetMatchingCommands:
    """测试 _get_matching_commands 辅助函数"""

    def test_no_settings(self):
        from lark_client.card_builder import _get_matching_commands

        settings = None
        result = _get_matching_commands(settings)
        assert result == [
            {"name": "Claude", "command": "claude"},
            {"name": "Codex", "command": "codex"},
        ]

    def test_empty_launchers(self):
        from lark_client.card_builder import _get_matching_commands

        settings = Settings()
        result = _get_matching_commands(settings)
        assert result == [
            {"name": "Claude", "command": "claude"},
            {"name": "Codex", "command": "codex"},
        ]

    def test_returns_all_launchers(self):
        from lark_client.card_builder import _get_matching_commands

        settings = Settings()
        settings.launchers = [
            Launcher(name="Claude", cli_type="claude", command="claude"),
            Launcher(name="Aider", cli_type="claude", command="aider --model claude-sonnet-4"),
            Launcher(name="Codex", cli_type="codex", command="codex"),
        ]
        result = _get_matching_commands(settings)
        assert len(result) == 3
        assert result[0]["name"] == "Claude"
        assert result[1]["name"] == "Aider"
        assert result[2]["name"] == "Codex"


class TestDirStartCallback:
    """测试 dir_start 回调处理"""

    def test_dir_start_callback_uses_launcher_name(self):
        value = {
            "action": "dir_start",
            "path": "/path/to/project",
            "session_name": "myproject",
            "launcher": "Aider",
        }
        assert value.get("launcher") == "Aider"

    def test_dir_start_callback_without_launcher_keeps_empty(self):
        value = {
            "action": "dir_start",
            "path": "/path/to/project",
            "session_name": "myproject",
        }
        assert value.get("launcher") is None


def test_package_json_includes_public_docs_but_not_superpowers_docs():
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    files = package["files"]

    assert "docs/*.md" in files
    assert "docs/*.json" in files
    assert "docs/superpowers/" not in files
    assert "docs/superpowers/**" not in files


def test_package_json_includes_postinstall_script_in_packed_files():
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    files = package["files"]

    assert "scripts/postinstall.sh" in files
    assert "scripts/*.sh" in files


def test_npmignore_preserves_install_scripts_when_present():
    npmignore_path = REPO_ROOT / ".npmignore"
    if not npmignore_path.exists():
        return

    npmignore = npmignore_path.read_text(encoding="utf-8")
    assert "!scripts/postinstall.sh" in npmignore
    assert "!scripts/preinstall.sh" in npmignore
    assert "!scripts/uninstall.sh" in npmignore


def test_remote_list_does_not_require_session_name():
    from remote_claude import validate_remote_args

    args = type("Args", (), {
        "host" : "example.com",
        "port" : 8765,
        "token": "secret-token",
        "name" : "",
    })()

    result = validate_remote_args(args, session_fallback="list")
    assert result == ("example.com", 8765, "list", "secret-token")


def test_cmd_uninstall_calls_uninstall_script_and_prints_followup(monkeypatch, capsys):
    called = {}

    def fake_run(cmd, **kwargs):
        called["cmd"] = cmd

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(remote_claude.subprocess, "run", fake_run)
    args = SimpleNamespace(yes=False)

    result = remote_claude.cmd_uninstall(args)

    assert result == 0
    assert called["cmd"][:2] == ["sh", str(remote_claude.SCRIPT_DIR / "scripts" / "uninstall.sh")]
    out = capsys.readouterr().out
    assert "npm uninstall -g remote-claude" in out
    assert "pnpm remove -g remote-claude" in out


def test_cmd_uninstall_passes_yes_flag_to_shell(monkeypatch):
    called = {}

    def fake_run(cmd, **kwargs):
        called["cmd"] = cmd

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(remote_claude.subprocess, "run", fake_run)
    args = SimpleNamespace(yes=True)

    remote_claude.cmd_uninstall(args)

    assert called["cmd"][-1] == "--yes"


def test_cmd_config_help_mentions_reset_scope(capsys):
    result = remote_claude.cmd_config(SimpleNamespace())

    assert result == 0
    out = capsys.readouterr().out
    assert "settings.json + state.json" in out
    assert "仅重置用户配置（settings.json）" in out
    assert "仅重置运行时配置（state.json）" in out


def test_test_plan_uses_existing_entry_lazy_init_target():
    content = (REPO_ROOT / "tests" / "TEST_PLAN.md").read_text(encoding="utf-8")

    assert "test_entry_script_runtime_behaviors" in content
    assert "test_entry_script_skips_feishu_prompt_and_executes_remote_claude_when_optional" not in content



def test_claude_md_uses_existing_entry_lazy_init_target():
    content = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    assert "test_entry_script_runtime_behaviors" in content
    assert "test_entry_script_skips_feishu_prompt_and_executes_remote_claude_when_optional" not in content



def test_cmd_config_reset_interactive_choice_3_resets_only_state(monkeypatch, tmp_path, capsys):
    user_data_dir = tmp_path / "user-data"
    user_data_dir.mkdir()
    settings_file = user_data_dir / "settings.json"
    state_file = user_data_dir / "state.json"
    settings_lock_file = user_data_dir / "settings.json.lock"
    state_lock_file = user_data_dir / "state.json.lock"
    env_file = user_data_dir / ".env"
    settings_file.write_text('{"version":"1.1","keep":"settings"}', encoding="utf-8")
    state_file.write_text('{"version":"1.1","keep":"state"}', encoding="utf-8")
    env_file.write_text("FEISHU_APP_ID=keep\n", encoding="utf-8")

    defaults_dir = remote_claude.SCRIPT_DIR / "resources" / "defaults"
    expected_state = (defaults_dir / "state.json.example").read_text(encoding="utf-8")
    assert expected_state.endswith("\n")

    monkeypatch.setattr("builtins.input", lambda _prompt: "3")
    monkeypatch.setattr("utils.runtime_config.USER_DATA_DIR", user_data_dir)
    monkeypatch.setattr("utils.runtime_config.SETTINGS_FILE", settings_file)
    monkeypatch.setattr("utils.runtime_config.STATE_FILE", state_file)
    monkeypatch.setattr("utils.runtime_config.SETTINGS_LOCK_FILE", settings_lock_file)
    monkeypatch.setattr("utils.runtime_config.STATE_LOCK_FILE", state_lock_file)

    result = remote_claude.cmd_config_reset(SimpleNamespace(all=False, settings_only=False, state_only=False))

    assert result == 0
    assert settings_file.read_text(encoding="utf-8") == '{"version":"1.1","keep":"settings"}'
    assert state_file.read_text(encoding="utf-8") == expected_state
    assert env_file.read_text(encoding="utf-8") == "FEISHU_APP_ID=keep\n"
    out = capsys.readouterr().out
    assert "已重置运行时配置" in out
    assert "已重置用户配置" not in out



def test_completion_script_advertises_current_public_management_commands():
    content = (REPO_ROOT / "scripts" / "completion.sh").read_text(encoding="utf-8")

    assert '"connection:远程连接配置管理"' in content
    assert '"connect:连接到远程会话"' in content
    assert '"token:查看会话 token"' in content
    assert '"regenerate-token:刷新会话 token"' in content
    assert '"remote:远程控制"' in content
    assert '"uninstall:清理本地数据并提示卸载命令"' in content
    assert 'connection token regenerate-token connect remote uninstall' in content


def test_shell_entry_help_shortcuts_match_current_management_surface():
    content = (REPO_ROOT / "bin" / "remote-claude").read_text(encoding="utf-8")

    assert "config|connection|conn|connect|remote|token|regenerate-token|lark|uninstall)" in content
    assert "stats|update" not in content


def test_completion_extracts_session_names_from_list_output():
    result = subprocess.run(
        ["bash"],
        input=f"""#!/usr/bin/env bash
set -e
PATH='/usr/bin:/bin:{REPO_ROOT}:$PATH'
function remote-claude() {{
cat <<'EOF'
活跃会话:
────────────────────────────────────────────────────────
类型     PID      tmux     名称
────────────────────────────────────────────────────────
claude   123      yes      alpha_session
codex    456      no       beta_session
共 2 个会话
EOF
}}
source '{REPO_ROOT / 'scripts' / 'completion.sh'}'
_remote_claude_get_sessions
""",
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["alpha_session", "beta_session"]


def test_completion_extracts_session_names_from_ansi_list_output():
    result = subprocess.run(
        ["bash"],
        input=f"""#!/usr/bin/env bash
set -e
PATH='/usr/bin:/bin:{REPO_ROOT}:$PATH'
function remote-claude() {{
printf '活跃会话:\n'
printf '────────────────────────────────────────────────────────\n'
printf '类型     PID      tmux     名称\n'
printf '────────────────────────────────────────────────────────\n'
printf '\033[0;32mclaude\033[0m  123      yes      ansi_alpha\n'
printf '\033[0;34mcodex\033[0m   456      no       ansi_beta\n'
printf '共 2 个会话\n'
}}
source '{REPO_ROOT / 'scripts' / 'completion.sh'}'
_remote_claude_get_sessions
""",
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["ansi_alpha", "ansi_beta"]




def test_completion_extracts_session_names_without_extra_processes():
    result = subprocess.run(
        ["bash"],
        input=f"""#!/usr/bin/env bash
set -e
PATH='/usr/bin:/bin:{REPO_ROOT}:$PATH'
function remote-claude() {{
cat <<'EOF'
活跃会话:
────────────────────────────────────────────────────────
类型     PID      tmux     名称
────────────────────────────────────────────────────────
claude   123      yes      alpha_session
codex    456      no       beta_session
共 2 个会话
EOF
}}
function sed() {{
  echo 'sed should not be called' >&2
  return 91
}}
function awk() {{
  echo 'awk should not be called' >&2
  return 92
}}
source '{REPO_ROOT / 'scripts' / 'completion.sh'}'
_remote_claude_get_sessions
""",
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["alpha_session", "beta_session"]
    result = subprocess.run(
        ["bash"],
        input=f"""#!/usr/bin/env bash
set -e
PATH='/nonexistent'
source '{REPO_ROOT / 'scripts' / 'completion.sh'}'
printf 'loaded\n'
_remote_claude_get_sessions
""",
        text=True,
        capture_output=True,
        cwd='/',
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["loaded"]


if __name__ == "__main__":
    pytest.main([__file__])
