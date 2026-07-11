# RAG Retrieval Report

## Summary

- Cases: 16
- Positive hits: 14
- Hit rate: 100.00%
- False accepts: 1
- False accept rate: 50.00%
- Top K: 3
- Distance threshold: 0.3

## Results

| Case | Accepted Chunks | Hit | False Accept | Pass |
| --- | --- | --- | --- | --- |
| care_cotton_tshirt | 洗涤养护.txt/洗涤养护.txt-001@0.1974<br>洗涤养护.txt/洗涤养护.txt-006@0.2106<br>洗涤养护.txt/洗涤养护.txt-003@0.2198 | YES | NO | PASS |
| care_wool_sweater | 洗涤养护.txt/洗涤养护.txt-009@0.1990<br>材质知识.txt/材质知识.txt-004@0.1997<br>洗涤养护.txt/洗涤养护.txt-014@0.2036 | YES | NO | PASS |
| care_denim_fading | 洗涤养护.txt/洗涤养护.txt-010@0.2183<br>洗涤养护.txt/洗涤养护.txt-002@0.2302<br>洗涤养护.txt/洗涤养护.txt-015@0.2537 | YES | NO | PASS |
| color_commute | 场景穿搭.txt/场景穿搭.txt-001@0.1399<br>颜色选择.txt/颜色选择.txt-002@0.1625<br>颜色选择.txt/颜色选择.txt-004@0.2307 | YES | NO | PASS |
| color_daily_basic | 颜色选择.txt/颜色选择.txt-002@0.1822<br>场景穿搭.txt/场景穿搭.txt-001@0.1999<br>颜色选择.txt/颜色选择.txt-004@0.2210 | YES | NO | PASS |
| care_silk | 洗涤养护.txt/洗涤养护.txt-005@0.1703<br>洗涤养护.txt/洗涤养护.txt-007@0.1969<br>洗涤养护.txt/洗涤养护.txt-008@0.2012 | YES | NO | PASS |
| care_knit_drying | 洗涤养护.txt/洗涤养护.txt-003@0.2651<br>材质知识.txt/材质知识.txt-004@0.2956 | YES | NO | PASS |
| color_interview | 颜色选择.txt/颜色选择.txt-002@0.1536<br>颜色选择.txt/颜色选择.txt-004@0.2059<br>场景穿搭.txt/场景穿搭.txt-001@0.2204 | YES | NO | PASS |
| scene_student_daily | 颜色选择.txt/颜色选择.txt-002@0.2145<br>场景穿搭.txt/场景穿搭.txt-002@0.2452<br>场景穿搭.txt/场景穿搭.txt-001@0.2548 | YES | NO | PASS |
| scene_date_focus | 颜色选择.txt/颜色选择.txt-002@0.1801<br>场景穿搭.txt/场景穿搭.txt-001@0.1905<br>场景穿搭.txt/场景穿搭.txt-003@0.2069 | YES | NO | PASS |
| material_linen_wrinkles | 材质知识.txt/材质知识.txt-002@0.1697<br>洗涤养护.txt/洗涤养护.txt-006@0.2497<br>材质知识.txt/材质知识.txt-001@0.2725 | YES | NO | PASS |
| material_polyester_tradeoffs | 材质知识.txt/材质知识.txt-003@0.2370<br>洗涤养护.txt/洗涤养护.txt-004@0.2745<br>材质知识.txt/材质知识.txt-002@0.2856 | YES | NO | PASS |
| fit_high_waist_proportion | 版型知识.txt/版型知识.txt-003@0.2284 | YES | NO | PASS |
| fit_oversized_boundary | 版型知识.txt/版型知识.txt-006@0.2119<br>版型知识.txt/版型知识.txt-004@0.2444 | YES | NO | PASS |
| unsupported_fireproof_standard | - | NO | NO | PASS |
| unsupported_polar_expedition | 材质知识.txt/材质知识.txt-001@0.2565<br>材质知识.txt/材质知识.txt-006@0.2809<br>材质知识.txt/材质知识.txt-003@0.2939 | NO | YES | FAIL |