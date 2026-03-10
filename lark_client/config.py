"""
Lark 客户端配置
"""

import os
from pathlib import Path
from dotenv import load_dotenv

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.session import USER_DATA_DIR, get_env_file

# 加载 .env 文件，优先从 ~/.remote-claude/.env 读取
_env_file = get_env_file()
_old_env_file = Path(__file__).resolve().parent.parent / ".env"

if not _env_file.exists() and _old_env_file.exists():
    import shutil
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(_old_env_file), str(_env_file))
    print(f"[config] 已将 .env 迁移到 {_env_file}")

load_dotenv(_env_file)

# 飞书应用配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

# 用户白名单（逗号分隔的 open_id 列表）
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "").split(",")
ENABLE_USER_WHITELIST = os.getenv("ENABLE_USER_WHITELIST", "false").lower() == "true"

# 机器人名称（用于群聊命名）
BOT_NAME = os.getenv("BOT_NAME", "Claude")

# 群聊名称前缀（格式：{GROUP_NAME_PREFIX}{dir}-{HH-MM}）
GROUP_NAME_PREFIX = os.getenv("GROUP_NAME_PREFIX", "【Remote-Claude】")
