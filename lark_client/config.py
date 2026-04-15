"""
Lark 客户端配置
"""

from utils.env_config import load_env_config


_env = load_env_config()

# 飞书应用配置
FEISHU_APP_ID = _env.feishu_app_id
FEISHU_APP_SECRET = _env.feishu_app_secret

# 用户白名单（逗号分隔的 open_id 列表）
ALLOWED_USERS = _env.allowed_users
ENABLE_USER_WHITELIST = _env.enable_user_whitelist

# 机器人名称（用于群聊命名）
BOT_NAME = "Claude"

# 群聊名称前缀（格式：{GROUP_NAME_PREFIX}{dir}-{HH-MM}）
GROUP_NAME_PREFIX = _env.group_name_prefix or "【Remote-Claude】"

# 流式卡片配置
MAX_CARD_BLOCKS = _env.max_card_blocks

# lark_client 日志级别（可选，默认 WARNING）
# 支持: DEBUG / INFO / WARNING / ERROR
_LOG_LEVEL_MAP = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}
LARK_LOG_LEVEL = _LOG_LEVEL_MAP.get((_env.lark_log_level or "WARNING").upper(), _LOG_LEVEL_MAP["WARNING"])

# SOCKS 代理兼容（可选，默认 False）
# 系统有 SOCKS 代理但飞书可直连时，设为 1 绕过代理
LARK_NO_PROXY = _env.lark_no_proxy
