# RAG Retrieval Report

## Summary

- Cases: 16
- Positive hits: 14
- Hit rate: 100.00%
- False accepts: 2
- False accept rate: 100.00%
- Top K: 3
- Distance threshold: 0.55

## Results

| Case | Accepted Chunks | Hit | False Accept | Pass |
| --- | --- | --- | --- | --- |
| care_cotton_tshirt | 洗涤养护.txt/洗涤养护.txt-001@0.1974<br>洗涤养护.txt/洗涤养护.txt-006@0.2106<br>洗涤养护.txt/洗涤养护.txt-003@0.2198 | YES | NO | PASS |
| care_wool_sweater | 洗涤养护.txt/洗涤养护.txt-009@0.1990<br>材质知识.txt/材质知识.txt-004@0.1997<br>洗涤养护.txt/洗涤养护.txt-014@0.2036 | YES | NO | PASS |
| care_denim_fading | 洗涤养护.txt/洗涤养护.txt-010@0.2194<br>洗涤养护.txt/洗涤养护.txt-002@0.2315<br>洗涤养护.txt/洗涤养护.txt-015@0.2549 | YES | NO | PASS |
| color_commute | 场景穿搭.txt/场景穿搭.txt-001@0.1401<br>颜色选择.txt/颜色选择.txt-002@0.1630<br>颜色选择.txt/颜色选择.txt-004@0.2310 | YES | NO | PASS |
| color_daily_basic | 颜色选择.txt/颜色选择.txt-002@0.1822<br>场景穿搭.txt/场景穿搭.txt-001@0.1999<br>颜色选择.txt/颜色选择.txt-004@0.2210 | YES | NO | PASS |
| care_silk | 洗涤养护.txt/洗涤养护.txt-005@0.1697<br>洗涤养护.txt/洗涤养护.txt-007@0.1963<br>洗涤养护.txt/洗涤养护.txt-008@0.2005 | YES | NO | PASS |
| care_knit_drying | 洗涤养护.txt/洗涤养护.txt-003@0.2627<br>材质知识.txt/材质知识.txt-004@0.2936<br>洗涤养护.txt/洗涤养护.txt-008@0.3001 | YES | NO | PASS |
| color_interview | 颜色选择.txt/颜色选择.txt-002@0.1536<br>颜色选择.txt/颜色选择.txt-004@0.2059<br>场景穿搭.txt/场景穿搭.txt-001@0.2204 | YES | NO | PASS |
| scene_student_daily | 颜色选择.txt/颜色选择.txt-002@0.2136<br>场景穿搭.txt/场景穿搭.txt-002@0.2437<br>场景穿搭.txt/场景穿搭.txt-001@0.2537 | YES | NO | PASS |
| scene_date_focus | 颜色选择.txt/颜色选择.txt-002@0.1826<br>场景穿搭.txt/场景穿搭.txt-001@0.1929<br>场景穿搭.txt/场景穿搭.txt-003@0.2080 | YES | NO | PASS |
| material_linen_wrinkles | 材质知识.txt/材质知识.txt-002@0.1699<br>洗涤养护.txt/洗涤养护.txt-006@0.2507<br>材质知识.txt/材质知识.txt-001@0.2737 | YES | NO | PASS |
| material_polyester_tradeoffs | 材质知识.txt/材质知识.txt-003@0.2370<br>洗涤养护.txt/洗涤养护.txt-004@0.2745<br>材质知识.txt/材质知识.txt-002@0.2856 | YES | NO | PASS |
| fit_high_waist_proportion | 版型知识.txt/版型知识.txt-003@0.2284<br>版型知识.txt/版型知识.txt-001@0.3457<br>颜色选择.txt/颜色选择.txt-003@0.3633 | YES | NO | PASS |
| fit_oversized_boundary | 版型知识.txt/版型知识.txt-006@0.2130<br>版型知识.txt/版型知识.txt-004@0.2458<br>版型知识.txt/版型知识.txt-005@0.3168 | YES | NO | PASS |
| unsupported_fireproof_standard | 材质知识.txt/材质知识.txt-003@0.3558<br>洗涤养护.txt/洗涤养护.txt-004@0.3652<br>洗涤养护.txt/洗涤养护.txt-016@0.3653 | NO | YES | FAIL |
| unsupported_polar_expedition | 材质知识.txt/材质知识.txt-001@0.2559<br>材质知识.txt/材质知识.txt-006@0.2819<br>材质知识.txt/材质知识.txt-003@0.2943 | NO | YES | FAIL |