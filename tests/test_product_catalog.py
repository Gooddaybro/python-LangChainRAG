import unittest

from clothing_assistant.tools.product_catalog import (
    load_product_catalog,
    run_structured_lookup,
)


class ProductCatalogTests(unittest.TestCase):
    def test_catalog_contains_parseable_products(self):
        catalog = load_product_catalog()

        self.assertGreaterEqual(len(catalog["products"]), 1)
        first_product = catalog["products"][0]
        self.assertIn("product_id", first_product)
        self.assertIn("price_cny", first_product)
        self.assertIn("colors", first_product)

    def test_lookup_returns_exact_price_for_matched_product(self):
        result = run_structured_lookup(
            "基础款纯棉T恤多少钱？",
            intent_result={"intent": "price_check", "query_type": "price"},
        )

        self.assertEqual(result["lookup_type"], "price")
        self.assertEqual(result["matched_product_id"], "TSHIRT_BASIC_001")
        self.assertEqual(result["price_cny"], 99)
        self.assertEqual(result["missing_fields"], [])

    def test_lookup_returns_stock_for_color_and_size(self):
        result = run_structured_lookup(
            "基础款纯棉T恤黑色L码有货吗？",
            intent_result={"intent": "inventory_check", "query_type": "inventory"},
        )

        self.assertEqual(result["lookup_type"], "inventory")
        self.assertEqual(result["matched_product_id"], "TSHIRT_BASIC_001")
        self.assertEqual(result["color"], "黑色")
        self.assertEqual(result["size"], "L")
        self.assertEqual(result["stock_count"], 8)
        self.assertTrue(result["in_stock"])

    def test_lookup_reports_unavailable_color_without_guessing(self):
        result = run_structured_lookup(
            "基础款纯棉T恤红色M码有货吗？",
            intent_result={"intent": "inventory_check", "query_type": "inventory"},
        )

        self.assertEqual(result["lookup_type"], "inventory")
        self.assertEqual(result["matched_product_id"], "TSHIRT_BASIC_001")
        self.assertEqual(result["color"], "红色")
        self.assertFalse(result["in_stock"])
        self.assertIn("color_not_found", result["missing_fields"])


if __name__ == "__main__":
    unittest.main()
