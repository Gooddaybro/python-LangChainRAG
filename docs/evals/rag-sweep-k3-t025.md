# RAG Retrieval Report

## Summary

- Cases: 16
- Positive hits: 13
- Hit rate: 92.86%
- False accepts: 0
- False accept rate: 0.00%
- Top K: 3
- Distance threshold: 0.25

## Results

| Case | Accepted Chunks | Hit | False Accept | Pass |
| --- | --- | --- | --- | --- |
| care_cotton_tshirt | 洗涤养护.txt/洗涤养护.txt-001@0.1974<br>洗涤养护.txt/洗涤养护.txt-006@0.2106<br>洗涤养护.txt/洗涤养护.txt-003@0.2198 | YES | NO | PASS |
| care_wool_sweater | 洗涤养护.txt/洗涤养护.txt-009@0.1968<br>材质知识.txt/材质知识.txt-004@0.1976<br>洗涤养护.txt/洗涤养护.txt-014@0.2011 | YES | NO | PASS |
| care_denim_fading | 洗涤养护.txt/洗涤养护.txt-010@0.2194<br>洗涤养护.txt/洗涤养护.txt-002@0.2315 | YES | NO | PASS |
| color_commute | 场景穿搭.txt/场景穿搭.txt-001@0.1395<br>颜色选择.txt/颜色选择.txt-002@0.1620<br>颜色选择.txt/颜色选择.txt-004@0.2296 | YES | NO | PASS |
| color_daily_basic | 颜色选择.txt/颜色选择.txt-002@0.1822<br>场景穿搭.txt/场景穿搭.txt-001@0.1999<br>颜色选择.txt/颜色选择.txt-004@0.2210 | YES | NO | PASS |
| care_silk | 洗涤养护.txt/洗涤养护.txt-005@0.1683<br>洗涤养护.txt/洗涤养护.txt-007@0.1952<br>洗涤养护.txt/洗涤养护.txt-008@0.1992 | YES | NO | PASS |
| care_knit_drying | - | NO | NO | FAIL |
| color_interview | 颜色选择.txt/颜色选择.txt-002@0.1536<br>颜色选择.txt/颜色选择.txt-004@0.2059<br>场景穿搭.txt/场景穿搭.txt-001@0.2204 | YES | NO | PASS |
| scene_student_daily | 颜色选择.txt/颜色选择.txt-002@0.2152<br>场景穿搭.txt/场景穿搭.txt-002@0.2453 | YES | NO | PASS |
| scene_date_focus | 颜色选择.txt/颜色选择.txt-002@0.1811<br>场景穿搭.txt/场景穿搭.txt-001@0.1904<br>场景穿搭.txt/场景穿搭.txt-003@0.2069 | YES | NO | PASS |
| material_linen_wrinkles | 材质知识.txt/材质知识.txt-002@0.1706 | YES | NO | PASS |
| material_polyester_tradeoffs | 材质知识.txt/材质知识.txt-003@0.2370 | YES | NO | PASS |
| fit_high_waist_proportion | 版型知识.txt/版型知识.txt-003@0.2284 | YES | NO | PASS |
| fit_oversized_boundary | 版型知识.txt/版型知识.txt-006@0.2130<br>版型知识.txt/版型知识.txt-004@0.2458 | YES | NO | PASS |
| unsupported_fireproof_standard | - | NO | NO | PASS |
| unsupported_polar_expedition | - | NO | NO | PASS |