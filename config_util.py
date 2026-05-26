import json
from pathlib import Path


def load_config(config_path="config.json"):
    config_path = Path(config_path).resolve()
    with open(config_path) as f:
        config = json.load(f)
    local_path = config_path.parent / "config.local.json"
    if local_path.exists():
        with open(local_path) as f:
            config.update(json.load(f))
    return config
