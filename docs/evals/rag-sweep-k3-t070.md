# RAG Retrieval Report

## Summary

- Cases: 16
- Positive hits: 14
- Hit rate: 100.00%
- False accepts: 2
- False accept rate: 100.00%
- Top K: 3
- Distance threshold: 0.7

## Results

| Case | Accepted Chunks | Hit | False Accept | Pass |
| --- | --- | --- | --- | --- |
| care_cotton_tshirt | 洗涤养护.txt/洗涤养护.txt-001@0.1977<br>洗涤养护.txt/洗涤养护.txt-006@0.2109<br>洗涤养护.txt/洗涤养护.txt-003@0.2201 | YES | NO | PASS |
| care_wool_sweater | 洗涤养护.txt/洗涤养护.txt-009@0.1990<br>材质知识.txt/材质知识.txt-004@0.1997<br>洗涤养护.txt/洗涤养护.txt-014@0.2036 | YES | NO | PASS |
| care_denim_fading | 洗涤养护.txt/洗涤养护.txt-010@0.2194<br>洗涤养护.txt/洗涤养护.txt-002@0.2315<br>洗涤养护.txt/洗涤养护.txt-015@0.2549 | YES | NO | PASS |
| color_commute | 场景穿搭.txt/场景穿搭.txt-001@0.1398<br>颜色选择.txt/颜色选择.txt-002@0.1632<br>颜色选择.txt/颜色选择.txt-004@0.2311 | YES | NO | PASS |
| color_daily_basic | 颜色选择.txt/颜色选择.txt-002@0.1822<br>场景穿搭.txt/场景穿搭.txt-001@0.1999<br>颜色选择.txt/颜色选择.txt-004@0.2210 | YES | NO | PASS |
| care_silk | 洗涤养护.txt/洗涤养护.txt-005@0.1703<br>洗涤养护.txt/洗涤养护.txt-007@0.1969<br>洗涤养护.txt/洗涤养护.txt-008@0.2012 | YES | NO | PASS |
| care_knit_drying | 洗涤养护.txt/洗涤养护.txt-003@0.2627<br>材质知识.txt/材质知识.txt-004@0.2936<br>洗涤养护.txt/洗涤养护.txt-008@0.3001 | YES | NO | PASS |
| color_interview | 颜色选择.txt/颜色选择.txt-002@0.1544<br>颜色选择.txt/颜色选择.txt-004@0.2063<br>场景穿搭.txt/场景穿搭.txt-001@0.2212 | YES | NO | PASS |
| scene_student_daily | 颜色选择.txt/颜色选择.txt-002@0.2152<br>场景穿搭.txt/场景穿搭.txt-002@0.2453<br>场景穿搭.txt/场景穿搭.txt-001@0.2559 | YES | NO | PASS |
| scene_date_focus | 颜色选择.txt/颜色选择.txt-002@0.1802<br>场景穿搭.txt/场景穿搭.txt-001@0.1903<br>场景穿搭.txt/场景穿搭.txt-003@0.2061 | YES | NO | PASS |
| material_linen_wrinkles | 材质知识.txt/材质知识.txt-002@0.1682<br>洗涤养护.txt/洗涤养护.txt-006@0.2486<br>材质知识.txt/材质知识.txt-001@0.2714 | YES | NO | PASS |
| material_polyester_tradeoffs | 材质知识.txt/材质知识.txt-003@0.2370<br>洗涤养护.txt/洗涤养护.txt-004@0.2745<br>材质知识.txt/材质知识.txt-002@0.2856 | YES | NO | PASS |
| fit_high_waist_proportion | 版型知识.txt/版型知识.txt-003@0.2284<br>版型知识.txt/版型知识.txt-001@0.3457<br>颜色选择.txt/颜色选择.txt-003@0.3633 | YES | NO | PASS |
| fit_oversized_boundary | 版型知识.txt/版型知识.txt-006@0.2130<br>版型知识.txt/版型知识.txt-004@0.2458<br>版型知识.txt/版型知识.txt-005@0.3168 | YES | NO | PASS |
| unsupported_fireproof_standard | 材质知识.txt/材质知识.txt-003@0.3542<br>洗涤养护.txt/洗涤养护.txt-004@0.3639<br>洗涤养护.txt/洗涤养护.txt-016@0.3640 | NO | YES | FAIL |
| unsupported_polar_expedition | 材质知识.txt/材质知识.txt-001@0.2547<br>材质知识.txt/材质知识.txt-006@0.2807<br>材质知识.txt/材质知识.txt-003@0.2933 | NO | YES | FAIL |