# RAG Retrieval Report

## Summary

- Cases: 16
- Positive hits: 11
- Hit rate: 78.57%
- False accepts: 2
- False accept rate: 100.00%
- Top K: 1
- Distance threshold: 0.4

## Results

| Case | Accepted Chunks | Hit | False Accept | Pass |
| --- | --- | --- | --- | --- |
| care_cotton_tshirt | 洗涤养护.txt/洗涤养护.txt-001@0.1974 | YES | NO | PASS |
| care_wool_sweater | 洗涤养护.txt/洗涤养护.txt-009@0.1990 | YES | NO | PASS |
| care_denim_fading | 洗涤养护.txt/洗涤养护.txt-010@0.2194 | YES | NO | PASS |
| color_commute | 场景穿搭.txt/场景穿搭.txt-001@0.1416 | NO | NO | FAIL |
| color_daily_basic | 颜色选择.txt/颜色选择.txt-002@0.1822 | YES | NO | PASS |
| care_silk | 洗涤养护.txt/洗涤养护.txt-005@0.1703 | YES | NO | PASS |
| care_knit_drying | 洗涤养护.txt/洗涤养护.txt-003@0.2627 | YES | NO | PASS |
| color_interview | 颜色选择.txt/颜色选择.txt-002@0.1535 | YES | NO | PASS |
| scene_student_daily | 颜色选择.txt/颜色选择.txt-002@0.2152 | NO | NO | FAIL |
| scene_date_focus | 颜色选择.txt/颜色选择.txt-002@0.1826 | NO | NO | FAIL |
| material_linen_wrinkles | 材质知识.txt/材质知识.txt-002@0.1699 | YES | NO | PASS |
| material_polyester_tradeoffs | 材质知识.txt/材质知识.txt-003@0.2370 | YES | NO | PASS |
| fit_high_waist_proportion | 版型知识.txt/版型知识.txt-003@0.2284 | YES | NO | PASS |
| fit_oversized_boundary | 版型知识.txt/版型知识.txt-006@0.2130 | YES | NO | PASS |
| unsupported_fireproof_standard | 材质知识.txt/材质知识.txt-003@0.3558 | NO | YES | FAIL |
| unsupported_polar_expedition | 材质知识.txt/材质知识.txt-001@0.2556 | NO | YES | FAIL |