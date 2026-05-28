# 경로 상수 및 전역 설정
import json
import os
from pathlib import Path

_CONFIG_FILE   = Path.home() / ".config" / "lore" / "config.json"
_DEFAULT_BRAIN = Path("/Users/minty/JM/brain")

_ENV_KEYS = ["TAVILY_API_KEY", "ANTHROPIC_API_KEY"]


def _load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _load_vault_dir() -> Path:
    data = _load_config()
    if data.get("brain_dir"):
        p = Path(data["brain_dir"]).expanduser()
        if p.name:
            return p
    return _DEFAULT_BRAIN


def _inject_env() -> None:
    data = _load_config()
    for key in _ENV_KEYS:
        if key not in os.environ and data.get(key):
            os.environ[key] = data[key]


def save_config(vault_dir: Path, **keys: str) -> None:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = _load_config()
    data["brain_dir"] = str(vault_dir)
    for k, v in keys.items():
        if v:
            data[k] = v
    _CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_search_provider(provider: str) -> None:
    global SEARCH_PROVIDER
    SEARCH_PROVIDER = provider
    data = _load_config()
    data["search_provider"] = provider
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


_inject_env()

SEARCH_PROVIDER = _load_config().get("search_provider", "tavily")

VAULT_DIR    = _load_vault_dir()
WIKI_DIR     = VAULT_DIR / "wiki"
QUEUE_DIR    = VAULT_DIR / "queue"
INDEX_PATH   = VAULT_DIR / "index.md"
LOG_PATH     = VAULT_DIR / "log.md"
HISTORY_FILE = VAULT_DIR / ".lore_history"

HOOKS_DIR    = Path(__file__).parent / "hooks"

MODEL      = "claude-haiku-4-5-20251001"
MODEL_CHAT = "claude-sonnet-4-6"
MODEL_AUTO = MODEL
