import json
from pathlib import Path

from astrbot.api import logger

PLUGIN_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = PLUGIN_DIR / "config.json"


def _load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        logger.error(
            "配置文件 %s 不存在",
            CONFIG_FILE,
        )
        raise ValueError("配置文件缺失，请确保 config.json 存在于插件目录下") from None


_config = _load_config()

ICS_URL = _config.get("ICS_URL", "")
BUILDING_URL = _config.get("BUILDING_URL", "")
XUEXING = _config.get("XUEXING", "")
XUEZHENG = _config.get("XUEZHENG", "")
XUEMING = _config.get("XUEMING", "")
XUESI = _config.get("XUESI", "")
XUEHAI = _config.get("XUEHAI", "")
GUANGLE = _config.get("GUANGLE", "")
DIANJIAO = _config.get("DIANJIAO", "")
BEIDA = _config.get("BEIDA", "")
XINXI = _config.get("XINXI", "")
