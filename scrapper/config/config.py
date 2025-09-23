"""
Centralized configuration module for the scrapper app.
Import configuration settings and utilities for the application.
"""
import logging
import os
from pathlib import Path

# Configuration Storage
__env_vars = {}
__scrapper_settings = {}
__targets = {}
__is_initialized = False


def _find_scrapper_root():
    """
    Find the root directory of the scrapper by traversing up from the current working directory.
    Returns the root directory path.
    """
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "Makefile").exists():
            return current
        current = current.parent

    # Fallback to the directory containing this file
    return Path(__file__).parent.parent

# Project Root
SCRAPPER_ROOT = _find_scrapper_root()

def _detect_mode_from_args() -> str | None:
    """Try to detect mode from CLI args like --mode production or --mode=production."""
    import sys
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--mode" and i + 1 < len(args):
            return args[i + 1].strip().lower()
        if a.startswith("--mode="):
            return a.split("=", 1)[1].strip().lower()
    return None


def get_mode(default: str = "development") -> str:
    """
    Return current runtime mode: development | production | testing.
    Resolution order: SCRAPPER_MODE env -> CLI --mode -> default.
    """
    mode = os.getenv("SCRAPPER_MODE") or _detect_mode_from_args() or default
    mode = str(mode).strip().lower()
    if mode not in {"development", "production", "testing"}:
        mode = default
    return mode


def _load_env_vars():
    """
    Load environment variables from layered env files in the scrapper root directory.

    Order (lowest -> highest precedence among files):
      1) Base file: .scrapper.env (overridable via SCRAPPER_BASE_ENV_FILE)
      2) Mode file: .scrapper.<mode>.env (overridable via SCRAPPER_ENV_FILE)

    Precedence overall for any key:
      - Process environment (existing when the app starts) has highest priority and is never overwritten.
      - Between files, the mode-specific file overrides the base file.
      - Then YAML settings, then provided default.

    The base file may define SCRAPPER_MODE which will influence which mode file is loaded.
    """
    # Snapshot original environment keys so we don't overwrite user-provided process env
    original_env_keys = set(os.environ.keys())

    def _load_file(file_path: str, warn_if_missing: bool = True):
        try:
            env_path = Path(file_path)
            if env_path.exists():
                with env_path.open("r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip()
                            # Merge into in-memory env file store (last writer wins)
                            __env_vars[k] = v
                            # Only override os.environ if this key wasn't present in the original process env
                            # This allows mode-specific file to override base file values set earlier from files
                            if k not in original_env_keys:
                                os.environ[k] = v
            else:
                if warn_if_missing:
                    logging.warning(f"Env file not found at {file_path}; proceeding with available sources.")
        except Exception as e:
            logging.error(f"Failed to load environment variables from {file_path}: {e}")
            raise Exception(f"Failed to load environment variables from {file_path}: {e}")

    # 1) Load base file first (optional)
    base_env_file = os.getenv("SCRAPPER_BASE_ENV_FILE", str(SCRAPPER_ROOT / ".scrapper.env"))
    _load_file(base_env_file, warn_if_missing=False)

    # 2) Determine mode (base file may have set SCRAPPER_MODE) and load mode file
    mode = get_mode()
    default_env = f".scrapper.{mode}.env"
    env_file = os.getenv("SCRAPPER_ENV_FILE", str(SCRAPPER_ROOT / default_env))
    _load_file(env_file, warn_if_missing=True)

def _load_scrapper_settings():
    """
    Load settings from the settings.py file in the scrapper root directory.
    """
    settings_file = os.getenv("SCRAPPER_SETTINGS_YAML", str(SCRAPPER_ROOT / "config" / "settings.yaml"))
    try:
        settings_path = Path(settings_file)
        if settings_path.exists():
            import yaml
            with settings_path.open("r") as f:
                data = yaml.safe_load(f) or {}
                __scrapper_settings.update(data)
    except Exception as e:
        logging.error(f"Failed to load settings from {settings_file}: {e}")
        raise Exception(f"Failed to load settings from {settings_file}: {e}")

def _load_targets():
    """
    Load targets from the targets.yaml file in the scrapper root directory.
    """
    targets_file = os.getenv("SCRAPPER_TARGETS_YAML", str(SCRAPPER_ROOT / "config" / "targets.yaml"))
    try:
        targets_path = Path(targets_file)
        if targets_path.exists():
            import yaml
            with targets_path.open("r") as f:
                data = yaml.safe_load(f) or {}
                __targets.update(data)
    except Exception as e:
        logging.error(f"Failed to load targets from {targets_file}: {e}")
        raise Exception(f"Failed to load targets from {targets_file}: {e}")


def _initialize_config():
    """ Load configuration settings and environment variables."""
    global __is_initialized, __env_vars, __scrapper_settings

    if __is_initialized:
        return

    _load_env_vars()
    _load_scrapper_settings()
    _load_targets()

    __is_initialized = True

def get_setting(key, default=None, cast=None):
    """
        Get a setting with proper precedence:
        1. Environment variables present in the process (highest)
        2. Env files (layered): .scrapper.env, then .scrapper.<mode>.env
        3. YAML configuration
        4. Default value

        Args:
            key: Setting key
            default: Default value if not found
            cast: Optional function to cast the value (int, float, bool, etc.)
        """
    if not __is_initialized:
        _initialize_config()

    # Try each source in order of precedence
    if key in os.environ:
        value = os.environ[key]
    elif key in __env_vars:
        value = __env_vars[key]
    elif key in __scrapper_settings:
        value = __scrapper_settings[key]
    else:
        value = default

    # Apply casting if provided and value exists
    if cast is not None and value is not None:
        try:
            return cast(value)
        except (ValueError, TypeError):
            logging.warning(f"Failed to cast {key}={value} using {cast.__name__}")

    return value

def get_targets():
    """
    Get the target dictionary loaded from the targets.yaml file.
    Returns:
        dict: Dictionary of targets
    """
    if not __is_initialized:
        _initialize_config()
    return __targets


