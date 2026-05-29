"""结构化商品目录工具。

这个模块只处理精确事实：商品、价格、颜色、库存和尺码规则 id。
Learning: 生产 RAG 项目里，价格和库存不能交给向量检索或 prompt 猜测；
它们必须来自结构化数据源，后续可以把这里的 JSON 替换成 SQLite/Postgres。
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from clothing_assistant.config_data import PRODUCT_CATALOG_PATH


PRICE_KEYWORDS = ["多少钱", "价格", "售价", "几元", "几块", "贵吗"]
INVENTORY_KEYWORDS = ["有货", "库存", "现货", "还有吗", "缺货", "补货", "可买"]
COMMON_COLORS = [
    "黑色",
    "白色",
    "灰色",
    "红色",
    "蓝色",
    "深蓝色",
    "藏青色",
    "卡其色",
    "绿色",
    "粉色",
    "米色",
]
SIZE_PATTERN = re.compile(r"(?<![a-zA-Z0-9])(XS|S|M|L|XL|2XL|3XL|4XL|5XL)(?=\s*码|\b)", re.IGNORECASE)


def normalize_text(text):
    return str(text or "").strip().lower()


@lru_cache(maxsize=4)
def load_product_catalog(catalog_path: str | Path | None = None) -> dict[str, Any]:
    """加载商品目录。

    lru_cache 让本地 JSON 只读一次；生产环境换数据库时，这里就是替换点。
    """
    resolved_path = Path(catalog_path) if catalog_path else PRODUCT_CATALOG_PATH
    with resolved_path.open("r", encoding="utf-8") as catalog_file:
        return json.load(catalog_file)


def iter_catalog_products(catalog=None):
    return (catalog or load_product_catalog()).get("products", [])


def infer_lookup_type(user_query, intent_result=None):
    query = normalize_text(user_query)
    query_type = (intent_result or {}).get("query_type")

    if query_type in {"price", "inventory"}:
        return query_type

    if any(keyword in query for keyword in PRICE_KEYWORDS):
        return "price"

    if any(keyword in query for keyword in INVENTORY_KEYWORDS):
        return "inventory"

    return None


def product_terms(product):
    terms = [
        product.get("sku"),
        product.get("product_id"),
        product.get("name"),
        product.get("category"),
        product.get("material"),
    ]
    terms.extend(product.get("aliases", []))
    return [term for term in terms if term]


def score_product_match(query, product):
    normalized_query = normalize_text(query)
    score = 0

    for term in product_terms(product):
        normalized_term = normalize_text(term)

        if not normalized_term:
            continue

        if normalized_term in normalized_query:
            if normalized_term in {normalize_text(product.get("sku")), normalize_text(product.get("product_id"))}:
                score += 5
            elif normalized_term == normalize_text(product.get("name")):
                score += 4
            elif normalized_term in [normalize_text(alias) for alias in product.get("aliases", [])]:
                score += 3
            else:
                score += 2

    return score


def find_matching_product(user_query, catalog=None):
    """根据商品名、SKU、类别或别名匹配一个商品。

    返回结构里显式标记 ambiguous，避免多个商品同分时随便选一个。
    """
    scored_products = [
        (score_product_match(user_query, product), product)
        for product in iter_catalog_products(catalog)
    ]
    scored_products = [(score, product) for score, product in scored_products if score > 0]

    if not scored_products:
        return {"product": None, "confidence": 0.0, "ambiguous": False}

    scored_products.sort(key=lambda item: item[0], reverse=True)
    best_score, best_product = scored_products[0]
    tied_products = [product for score, product in scored_products if score == best_score]

    if len(tied_products) > 1:
        return {
            "product": None,
            "confidence": 0.4,
            "ambiguous": True,
            "candidates": [product["product_id"] for product in tied_products],
        }

    return {
        "product": best_product,
        "confidence": min(1.0, best_score / 5),
        "ambiguous": False,
    }


def extract_requested_color(user_query, product=None):
    query = normalize_text(user_query)
    color_names = []

    if product:
        color_names.extend(color["name"] for color in product.get("colors", []))

    color_names.extend(COMMON_COLORS)
    color_names = sorted(set(color_names), key=len, reverse=True)

    for color_name in color_names:
        if normalize_text(color_name) in query:
            return color_name

    return None


def extract_requested_size(user_query):
    match = SIZE_PATTERN.search(user_query)

    if not match:
        return None

    return match.group(1).upper()


def build_base_result(lookup_type, match_result):
    product = match_result.get("product")
    missing_fields = []

    if match_result.get("ambiguous"):
        missing_fields.append("product_ambiguous")
    elif not product:
        missing_fields.append("product")

    return {
        "lookup_type": lookup_type,
        "matched_product_id": product.get("product_id") if product else None,
        "matched_product_name": product.get("name") if product else None,
        "sku": product.get("sku") if product else None,
        "category": product.get("category") if product else None,
        "material": product.get("material") if product else None,
        "size_rule_id": product.get("size_rule_id") if product else None,
        "policy_id": product.get("policy_id") if product else None,
        "confidence": match_result.get("confidence", 0.0),
        "missing_fields": missing_fields,
    }


def available_colors(product):
    return [color["name"] for color in product.get("colors", [])]


def find_color_entry(product, requested_color):
    for color in product.get("colors", []):
        if color["name"] == requested_color:
            return color

    return None


def run_structured_lookup(user_query, intent_result=None, catalog=None):
    """查结构化商品事实，返回节点可验证的 dict。

    节点不需要再从自然语言答案里反推库存/价格；它直接读取这些字段。
    """
    lookup_type = infer_lookup_type(user_query, intent_result)
    match_result = find_matching_product(user_query, catalog)
    product = match_result.get("product")
    result = build_base_result(lookup_type, match_result)

    if not lookup_type:
        result["reason"] = "当前问题不属于结构化价格或库存查询。"
        return result

    if not product:
        result["reason"] = "缺少可唯一匹配的商品。"
        return result

    result["available_colors"] = available_colors(product)

    if lookup_type == "price":
        result["price_cny"] = product["price_cny"]
        result["reason"] = "价格来自 product_catalog.json。"
        return result

    requested_color = extract_requested_color(user_query, product)
    requested_size = extract_requested_size(user_query)
    result["color"] = requested_color
    result["size"] = requested_size

    if not requested_color:
        result["missing_fields"].append("color")

    if not requested_size:
        result["missing_fields"].append("size")

    color_entry = find_color_entry(product, requested_color) if requested_color else None

    if requested_color and not color_entry:
        result["missing_fields"].append("color_not_found")
        result["stock_count"] = 0
        result["in_stock"] = False
        result["reason"] = "商品目录里没有这个颜色。"
        return result

    if not color_entry or not requested_size:
        result["stock_count"] = None
        result["in_stock"] = None
        result["reason"] = "库存查询缺少颜色或尺码。"
        return result

    stock_count = int(color_entry.get("stock", {}).get(requested_size, 0))
    result["stock_count"] = stock_count
    result["in_stock"] = stock_count > 0
    result["reason"] = "库存来自 product_catalog.json。"
    return result
