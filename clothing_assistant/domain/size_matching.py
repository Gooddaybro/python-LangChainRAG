import re

SIZE_ORDER = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
MAX_MIXED_SIZE_GAP = 1


def extract_user_measurements(user_query):
    height_match = re.search(
        r"身高\s*([0-9]{2,3}(?:\.\d+)?)\s*(?:cm|厘米)?",
        user_query,
        re.IGNORECASE,
    )
    weight_match = re.search(
        r"体重\s*([0-9]{2,3}(?:\.\d+)?)\s*(kg|公斤|斤)?",
        user_query,
        re.IGNORECASE,
    )

    height_cm = float(height_match.group(1)) if height_match else None
    weight_value = float(weight_match.group(1)) if weight_match else None
    weight_unit = (
        weight_match.group(2).lower()
        if weight_match and weight_match.group(2)
        else None
    )

    if weight_value is None:
        weight_jin = None
    elif weight_unit in {"kg", "公斤"}:
        weight_jin = weight_value * 2
    else:
        # 服装尺码表使用“斤”，用户没写单位时先按“斤”理解。
        weight_jin = weight_value

    return {
        "height_cm": height_cm,
        "weight_jin": weight_jin,
        "raw_weight_value": weight_value,
        "raw_weight_unit": weight_unit,
    }


def has_complete_measurements(user_query):
    """判断一段文本里是否同时包含身高和体重。"""
    measurements = extract_user_measurements(user_query)
    return measurements["height_cm"] is not None and measurements["weight_jin"] is not None


def parse_size_rule_line(line):
    pattern = re.compile(
        r"身高[:：]\s*(\d+)(?:-(\d+))?cm(\+)?[，,\s]*"
        r"体重[:：]\s*(\d+)(?:-(\d+))?\s*斤(\+)?[，,\s]*"
        r"建议尺码\s*([A-Za-z0-9]+)",
    )
    match = pattern.search(line)

    if not match:
        return None

    height_min = float(match.group(1))
    height_max = None if match.group(3) else float(match.group(2) or match.group(1))
    weight_min = float(match.group(4))
    weight_max = None if match.group(6) else float(match.group(5) or match.group(4))

    return {
        "rule_text": line,
        "height_min": height_min,
        "height_max": height_max,
        "weight_min": weight_min,
        "weight_max": weight_max,
        "size": match.group(7),
    }


def value_in_range(value, min_value, max_value):
    if value is None:
        return False

    if value < min_value:
        return False

    if max_value is not None and value > max_value:
        return False

    return True


def distance_to_range(value, min_value, max_value):
    if value is None:
        return None

    if value < min_value:
        return min_value - value

    if max_value is not None and value > max_value:
        return value - max_value

    return 0


def find_rule_by_size(size_rules, size):
    for rule in size_rules:
        if rule["size"] == size:
            return rule

    return None


def get_size_index(size):
    if size not in SIZE_ORDER:
        return None

    return SIZE_ORDER.index(size)


def calculate_size_gap(first_size, second_size):
    first_index = get_size_index(first_size)
    second_index = get_size_index(second_size)

    if first_index is None or second_index is None:
        return None

    return abs(first_index - second_index)


def choose_closest_mixed_rules(height_matched_rules, weight_matched_rules):
    scored_pairs = []

    for height_rule in height_matched_rules:
        for weight_rule in weight_matched_rules:
            size_gap = calculate_size_gap(height_rule["size"], weight_rule["size"])

            if size_gap is not None:
                scored_pairs.append((size_gap, height_rule, weight_rule))

    if not scored_pairs:
        return height_matched_rules[0], weight_matched_rules[0], None

    scored_pairs.sort(key=lambda item: item[0])
    size_gap, height_rule, weight_rule = scored_pairs[0]
    return height_rule, weight_rule, size_gap


def build_size_result(match_type, primary_rule, measurements, reason, alternative_rule=None):
    return {
        "matched": primary_rule is not None,
        "match_type": match_type,
        "primary_size": primary_rule["size"] if primary_rule else None,
        "alternative_size": alternative_rule["size"] if alternative_rule else None,
        "reason": reason,
        "matched_rule": primary_rule["rule_text"] if primary_rule else None,
        "alternative_rule": alternative_rule["rule_text"] if alternative_rule else None,
        "measurements": measurements,
    }


def find_nearest_rule(size_rules, measurements):
    scored_rules = []

    for rule in size_rules:
        height_distance = distance_to_range(
            measurements["height_cm"],
            rule["height_min"],
            rule["height_max"],
        )
        weight_distance = distance_to_range(
            measurements["weight_jin"],
            rule["weight_min"],
            rule["weight_max"],
        )

        if height_distance is None or weight_distance is None:
            continue

        scored_rules.append((height_distance + weight_distance, rule))

    if not scored_rules:
        return None

    scored_rules.sort(key=lambda item: item[0])
    return scored_rules[0][1]


def match_size_rule(user_query, size_rules):
    measurements = extract_user_measurements(user_query)

    if not size_rules:
        return build_size_result(
            "missing_rules",
            None,
            measurements,
            "知识库中没有可用的尺码规则。",
        )

    if measurements["height_cm"] is None or measurements["weight_jin"] is None:
        return build_size_result(
            "missing_measurements",
            None,
            measurements,
            "用户问题中没有同时提供身高和体重，无法做尺码规则匹配。",
        )

    height_matched_rules = []
    weight_matched_rules = []

    for rule in size_rules:
        height_ok = value_in_range(
            measurements["height_cm"],
            rule["height_min"],
            rule["height_max"],
        )
        weight_ok = value_in_range(
            measurements["weight_jin"],
            rule["weight_min"],
            rule["weight_max"],
        )

        if height_ok:
            height_matched_rules.append(rule)

        if weight_ok:
            weight_matched_rules.append(rule)

        if height_ok and weight_ok:
            return build_size_result(
                "exact",
                rule,
                measurements,
                f"身高和体重都命中 {rule['size']} 码规则。",
            )

    if height_matched_rules and weight_matched_rules:
        primary_rule, alternative_rule, size_gap = choose_closest_mixed_rules(
            height_matched_rules,
            weight_matched_rules,
        )

        if size_gap is not None and size_gap > MAX_MIXED_SIZE_GAP:
            reason = (
                f"身高更接近 {primary_rule['size']} 码区间，"
                f"体重更接近 {alternative_rule['size']} 码区间，"
                "两个尺码区间差距较大。当前尺码表无法给出单一可靠尺码，"
                "建议补充胸围、肩宽、衣长或试穿确认。"
            )
            return build_size_result(
                "measurement_conflict",
                None,
                measurements,
                reason,
            )

        reason = (
            f"身高更接近 {primary_rule['size']} 码区间，"
            f"体重更接近 {alternative_rule['size']} 码区间，"
            "建议结合穿着习惯选择。"
        )
        return build_size_result(
            "mixed",
            primary_rule,
            measurements,
            reason,
            alternative_rule=alternative_rule,
        )

    nearest_rule = find_nearest_rule(size_rules, measurements)

    if nearest_rule:
        return build_size_result(
            "nearest",
            nearest_rule,
            measurements,
            "没有完全命中身高和体重区间，已按最接近的尺码规则推荐。",
        )

    return build_size_result(
        "no_match",
        None,
        measurements,
        "知识库中没有找到可匹配或可降级推荐的尺码规则。",
    )
