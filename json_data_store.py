"""Read and atomically update the JSON data file configured by FILE_PATH."""

import json
import os
import tempfile

from bot_logging import get_logger

logger = get_logger("store")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHOOL_SCHEDULE_PATH = os.path.join(ROOT_DIR, "school_schedule.json")


def read_data(path: str):
    """Load and return the JSON value at path."""
    try:
        with open(path, "r", encoding="utf-8") as data_file:
            data = json.load(data_file)
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to read JSON file | path=%s", path)
        raise
    logger.debug("JSON file read | path=%s", path)
    return data


def read_school_schedule():
    """Load school_schedule.json from the program root directory."""
    return read_data(SCHOOL_SCHEDULE_PATH)


def write_data(path: str, data) -> None:
    """Atomically replace path with the supplied JSON value."""
    directory = os.path.dirname(os.path.abspath(path))
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory, delete=False
        ) as temp_file:
            temp_path = temp_file.name
            json.dump(data, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
        os.replace(temp_path, path)
        logger.info("JSON file written | path=%s", path)
    except Exception:
        logger.exception("Failed to write JSON file | path=%s", path)
        raise
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
