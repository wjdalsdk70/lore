# 경로 상수 및 전역 설정
import json
from pathlib import Path

_CONFIG_FILE   = Path.home() / ".config" / "lore" / "config.json"
_DEFAULT_BRAIN = Path("/Users/minty/JM/brain")


def _load_vault_dir() -> Path:
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            p = Path(data["brain_dir"]).expanduser()
            if p.name:
                return p
        except Exception:
            pass
    return _DEFAULT_BRAIN


def save_config(vault_dir: Path) -> None:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps({"brain_dir": str(vault_dir)}, ensure_ascii=False),
        encoding="utf-8",
    )


VAULT_DIR    = _load_vault_dir()
WIKI_DIR     = VAULT_DIR / "wiki"
QUEUE_DIR    = VAULT_DIR / "queue"
INDEX_PATH   = VAULT_DIR / "index.md"
LOG_PATH     = VAULT_DIR / "log.md"
HISTORY_FILE = VAULT_DIR / ".lore_history"

HOOKS_DIR    = Path(__file__).parent / "hooks"

MODEL      = "claude-haiku-4-5-20251001"
MODEL_CHAT = MODEL
MODEL_AUTO = MODEL
