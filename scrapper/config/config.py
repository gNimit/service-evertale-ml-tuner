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

def _load_env_vars():
    """
    Load environment variables from the .env file in the scrapper root directory.
    """
    env_file = os.getenv("SCRAPPER_ENV_FILE", str(SCRAPPER_ROOT / ".scrapper.env"))
    try:
        env_path = Path(env_file)
        if env_path.exists():
            with env_path.open("r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        __env_vars[k] = v
                        if k not in os.environ:
                            os.environ[k] = v
    except Exception as e:
        logging.error(f"Failed to load environment variables from {env_file}: {e}")
        raise Exception(f"Failed to load environment variables from {env_file}: {e}")

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
        1. Environment variables (os.environ)
        2. Environment file (.scrapper.env)
        3. YAML configuration
        4. Default value

        Args:
            key: Setting set
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


