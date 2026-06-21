import os
import yaml

_loaded: dict[str, dict] = {}
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def load_all():
    global _loaded
    _loaded = {}
    if not os.path.isdir(PROMPTS_DIR):
        return
    for fname in os.listdir(PROMPTS_DIR):
        if fname.endswith((".yaml", ".yml")):
            path = os.path.join(PROMPTS_DIR, fname)
            with open(path) as f:
                key = fname.replace(".yaml", "").replace(".yml", "")
                _loaded[key] = yaml.safe_load(f)


def get(prompt_name: str, key: str = "system") -> str:
    if not _loaded:
        load_all()
    block = _loaded.get(prompt_name, {})
    val = block.get(key, "")
    return val


def get_list(prompt_name: str, key: str) -> list:
    if not _loaded:
        load_all()
    return _loaded.get(prompt_name, {}).get(key, [])


def get_dict(prompt_name: str, key: str) -> list[dict]:
    if not _loaded:
        load_all()
    return _loaded.get(prompt_name, {}).get(key, [])
