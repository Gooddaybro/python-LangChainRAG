"""Legacy wrapper and file-backed adapter for size matching.

Pure matching logic lives in ``clothing_assistant.domain.size_matching``. This
module keeps the old ``match_size_rule(user_query)`` API and owns local file
loading during the migration.
"""

from clothing_assistant.config_data import DATA_DIR, SIZE_KNOWLEDGE_FILE
from clothing_assistant.domain.size_matching import (
    build_size_result,
    calculate_size_gap,
    choose_closest_mixed_rules,
    distance_to_range,
    extract_user_measurements,
    find_nearest_rule,
    find_rule_by_size,
    get_size_index,
    has_complete_measurements,
    match_size_rule as match_size_rule_with_rules,
    parse_size_rule_line,
    value_in_range,
)


_SIZE_RULE_CACHE = None
_SIZE_RULE_CACHE_VERSION = None


def get_size_rule_file_path():
    return DATA_DIR / SIZE_KNOWLEDGE_FILE


def get_size_rule_file_version(file_path):
    stat_result = file_path.stat()
    return f"{stat_result.st_mtime_ns}:{stat_result.st_size}"


def load_size_rules_from_file():
    file_path = get_size_rule_file_path()
    size_rules = []

    for line in file_path.read_text(encoding="utf-8").splitlines():
        clean_line = line.strip()

        if not clean_line:
            continue

        parsed_rule = parse_size_rule_line(clean_line)

        if parsed_rule:
            size_rules.append(parsed_rule)

    return size_rules


def get_cached_size_rules():
    global _SIZE_RULE_CACHE, _SIZE_RULE_CACHE_VERSION

    file_path = get_size_rule_file_path()

    if not file_path.exists():
        _SIZE_RULE_CACHE = []
        _SIZE_RULE_CACHE_VERSION = None
        return _SIZE_RULE_CACHE

    current_version = get_size_rule_file_version(file_path)

    # 文件没有变化时，复用内存解析结果，避免每次查询都读盘和跑正则。
    if _SIZE_RULE_CACHE is not None and _SIZE_RULE_CACHE_VERSION == current_version:
        return _SIZE_RULE_CACHE

    _SIZE_RULE_CACHE = load_size_rules_from_file()
    _SIZE_RULE_CACHE_VERSION = current_version
    return _SIZE_RULE_CACHE


def match_size_rule(user_query):
    return match_size_rule_with_rules(user_query, get_cached_size_rules())
