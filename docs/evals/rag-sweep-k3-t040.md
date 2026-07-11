# RAG Retrieval Report

## Summary

- Cases: 16
- Positive hits: 14
- Hit rate: 100.00%
- False accepts: 2
- False accept rate: 100.00%
- Top K: 3
- Distance threshold: 0.4

## Results

| Case | Accepted Chunks | Hit | False Accept | Pass |
| --- | --- | --- | --- | --- |
| care_cotton_tshirt | 洗涤养护.txt/洗涤养护.txt-001@0.1962<br>洗涤养护.txt/洗涤养护.txt-006@0.2093<br>洗涤养护.txt/洗涤养护.txt-003@0.2184 | YES | NO | PASS |
| care_wool_sweater | 洗涤养护.txt/洗涤养护.txt-009@0.1990<br>材质知识.txt/材质知识.txt-004@0.1997<br>洗涤养护.txt/洗涤养护.txt-014@0.2036 | YES | NO | PASS |
| care_denim_fading | 洗涤养护.txt/洗涤养护.txt-010@0.2171<br>洗涤养护.txt/洗涤养护.txt-002@0.2292<br>洗涤养护.txt/洗涤养护.txt-015@0.2528 | YES | NO | PASS |
| color_commute | 场景穿搭.txt/场景穿搭.txt-001@0.1416<br>颜色选择.txt/颜色选择.txt-002@0.1639<br>颜色选择.txt/颜色选择.txt-004@0.2326 | YES | NO | PASS |
| color_daily_basic | 颜色选择.txt/颜色选择.txt-002@0.1822<br>场景穿搭.txt/场景穿搭.txt-001@0.1999<br>颜色选择.txt/颜色选择.txt-004@0.2210 | YES | NO | PASS |
| care_silk | 洗涤养护.txt/洗涤养护.txt-005@0.1703<br>洗涤养护.txt/洗涤养护.txt-007@0.1969<br>洗涤养护.txt/洗涤养护.txt-008@0.2012 | YES | NO | PASS |
| care_knit_drying | 洗涤养护.txt/洗涤养护.txt-003@0.2660<br>材质知识.txt/材质知识.txt-004@0.2970<br>洗涤养护.txt/洗涤养护.txt-008@0.3027 | YES | NO | PASS |
| color_interview | 颜色选择.txt/颜色选择.txt-002@0.1539<br>颜色选择.txt/颜色选择.txt-004@0.2070<br>场景穿搭.txt/场景穿搭.txt-001@0.2211 | YES | NO | PASS |
| scene_student_daily | 颜色选择.txt/颜色选择.txt-002@0.2152<br>场景穿搭.txt/场景穿搭.txt-002@0.2453<br>场景穿搭.txt/场景穿搭.txt-001@0.2559 | YES | NO | PASS |
| scene_date_focus | 颜色选择.txt/颜色选择.txt-002@0.1826<br>场景穿搭.txt/场景穿搭.txt-001@0.1929<br>场景穿搭.txt/场景穿搭.txt-003@0.2080 | YES | NO | PASS |
| material_linen_wrinkles | 材质知识.txt/材质知识.txt-002@0.1697<br>洗涤养护.txt/洗涤养护.txt-006@0.2501<br>材质知识.txt/材质知识.txt-001@0.2731 | YES | NO | PASS |
| material_polyester_tradeoffs | 材质知识.txt/材质知识.txt-003@0.2370<br>洗涤养护.txt/洗涤养护.txt-004@0.2745<br>材质知识.txt/材质知识.txt-002@0.2856 | YES | NO | PASS |
| fit_high_waist_proportion | 版型知识.txt/版型知识.txt-003@0.2273<br>版型知识.txt/版型知识.txt-001@0.3435<br>颜色选择.txt/颜色选择.txt-003@0.3603 | YES | NO | PASS |
| fit_oversized_boundary | 版型知识.txt/版型知识.txt-006@0.2130<br>版型知识.txt/版型知识.txt-004@0.2458<br>版型知识.txt/版型知识.txt-005@0.3168 | YES | NO | PASS |
| unsupported_fireproof_standard | 材质知识.txt/材质知识.txt-003@0.3558<br>洗涤养护.txt/洗涤养护.txt-004@0.3652<br>洗涤养护.txt/洗涤养护.txt-016@0.3653 | NO | YES | FAIL |
| unsupported_polar_expedition | 材质知识.txt/材质知识.txt-001@0.2556<br>材质知识.txt/材质知识.txt-006@0.2808<br>材质知识.txt/材质知识.txt-003@0.2937 | NO | YES | FAIL |