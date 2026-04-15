"""
远程连接配置管理

提供远程连接配置的持久化存储和管理功能。
"""

from dataclasses import dataclass
from typing import List, Optional
import json

from utils.runtime_config import (
    RemoteConnection,
    list_remote_connections,
    get_remote_connection,
    get_default_remote_connection,
    save_remote_connection,
    delete_remote_connection as delete_remote_connection_impl,
    set_default_remote_connection,
    load_settings,
    save_settings,
    touch_remote_connection,
)
from utils.session import USER_DATA_DIR


CONNECTIONS_FILE = USER_DATA_DIR / "remote_connections.json"


@dataclass
class SavedConnection:
    """保存的远程连接配置"""
    name: str = ""
    host: str = ""
    port: int = 8765
    token: str = ""
    session: str = ""
    description: str = ""
    created_at: str = ""
    last_used: str = ""
    is_default: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "token": self.token,
            "session": self.session,
            "description": self.description,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "is_default": self.is_default,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SavedConnection":
        return cls(
            name=data.get("name", ""),
            host=data.get("host", ""),
            port=data.get("port", 8765),
            token=data.get("token", ""),
            session=data.get("session", ""),
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
            last_used=data.get("last_used", ""),
            is_default=data.get("is_default", False),
        )


_legacy_migrated = False


def _to_saved_connection(conn: RemoteConnection) -> SavedConnection:
    return SavedConnection(**conn.to_dict())


def _migrate_legacy_connections_if_needed() -> None:
    global _legacy_migrated
    if _legacy_migrated:
        return
    _legacy_migrated = True

    settings = load_settings()
    if settings.remote.connections or not CONNECTIONS_FILE.exists():
        return

    try:
        data = json.loads(CONNECTIONS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"警告: 加载旧远程连接配置失败: {e}")
        return

    connections = data.get("connections", {})
    default_name = ""
    for name, conn_data in connections.items():
        conn = SavedConnection.from_dict(conn_data)
        settings.remote.connections[name] = RemoteConnection.from_dict(conn.to_dict())
        if conn.is_default and not default_name:
            default_name = name

    if not default_name and settings.remote.connections:
        default_name = next(iter(settings.remote.connections.keys()))
    settings.remote.default_connection = default_name
    if default_name and default_name in settings.remote.connections:
        settings.remote.connections[default_name].is_default = True

    save_settings(settings)


def list_connections() -> List[SavedConnection]:
    _migrate_legacy_connections_if_needed()
    return [_to_saved_connection(conn) for conn in list_remote_connections()]


def get_connection(name: str) -> Optional[SavedConnection]:
    _migrate_legacy_connections_if_needed()
    conn = get_remote_connection(name)
    return _to_saved_connection(conn) if conn else None


def touch_connection(name: str) -> Optional[SavedConnection]:
    _migrate_legacy_connections_if_needed()
    conn = touch_remote_connection(name)
    return _to_saved_connection(conn) if conn else None


def get_default_connection() -> Optional[SavedConnection]:
    _migrate_legacy_connections_if_needed()
    conn = get_default_remote_connection()
    return _to_saved_connection(conn) if conn else None


def save_connection(
    name: str,
    host: str,
    port: int,
    token: str,
    session: str = "",
    description: str = "",
    is_default: bool = False,
) -> SavedConnection:
    _migrate_legacy_connections_if_needed()
    conn = save_remote_connection(name, host, port, token, session, description, is_default)
    return _to_saved_connection(conn)


def delete_connection(name: str) -> bool:
    _migrate_legacy_connections_if_needed()
    return delete_remote_connection_impl(name)


def set_default_connection(name: str) -> bool:
    _migrate_legacy_connections_if_needed()
    return set_default_remote_connection(name)
