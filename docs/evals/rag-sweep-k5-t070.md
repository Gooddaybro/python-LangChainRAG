# RAG Retrieval Report

## Summary

- Cases: 16
- Positive hits: 14
- Hit rate: 100.00%
- False accepts: 2
- False accept rate: 100.00%
- Top K: 5
- Distance threshold: 0.7

## Results

| Case | Accepted Chunks | Hit | False Accept | Pass |
| --- | --- | --- | --- | --- |
| care_cotton_tshirt | 洗涤养护.txt/洗涤养护.txt-001@0.1977<br>洗涤养护.txt/洗涤养护.txt-006@0.2109<br>洗涤养护.txt/洗涤养护.txt-003@0.2201<br>材质知识.txt/材质知识.txt-001@0.2301<br>洗涤养护.txt/洗涤养护.txt-007@0.2370 | YES | NO | PASS |
| care_wool_sweater | 洗涤养护.txt/洗涤养护.txt-009@0.1990<br>材质知识.txt/材质知识.txt-004@0.1997<br>洗涤养护.txt/洗涤养护.txt-014@0.2036<br>洗涤养护.txt/洗涤养护.txt-003@0.2298<br>洗涤养护.txt/洗涤养护.txt-016@0.2352 | YES | NO | PASS |
| care_denim_fading | 洗涤养护.txt/洗涤养护.txt-010@0.2194<br>洗涤养护.txt/洗涤养护.txt-002@0.2315<br>洗涤养护.txt/洗涤养护.txt-015@0.2549<br>材质知识.txt/材质知识.txt-005@0.2754<br>洗涤养护.txt/洗涤养护.txt-001@0.2989 | YES | NO | PASS |
| color_commute | 场景穿搭.txt/场景穿搭.txt-001@0.1416<br>颜色选择.txt/颜色选择.txt-002@0.1639<br>颜色选择.txt/颜色选择.txt-004@0.2326<br>场景穿搭.txt/场景穿搭.txt-002@0.2760<br>颜色选择.txt/颜色选择.txt-006@0.2794 | YES | NO | PASS |
| color_daily_basic | 颜色选择.txt/颜色选择.txt-002@0.1822<br>场景穿搭.txt/场景穿搭.txt-001@0.1999<br>颜色选择.txt/颜色选择.txt-004@0.2210<br>颜色选择.txt/颜色选择.txt-006@0.2360<br>颜色选择.txt/颜色选择.txt-001@0.2491 | YES | NO | PASS |
| care_silk | 洗涤养护.txt/洗涤养护.txt-005@0.1703<br>洗涤养护.txt/洗涤养护.txt-007@0.1969<br>洗涤养护.txt/洗涤养护.txt-008@0.2012<br>洗涤养护.txt/洗涤养护.txt-006@0.2191<br>洗涤养护.txt/洗涤养护.txt-001@0.2405 | YES | NO | PASS |
| care_knit_drying | 洗涤养护.txt/洗涤养护.txt-003@0.2627<br>材质知识.txt/材质知识.txt-004@0.2936<br>洗涤养护.txt/洗涤养护.txt-008@0.3001<br>洗涤养护.txt/洗涤养护.txt-009@0.3029<br>洗涤养护.txt/洗涤养护.txt-007@0.3160 | YES | NO | PASS |
| color_interview | 颜色选择.txt/颜色选择.txt-002@0.1554<br>颜色选择.txt/颜色选择.txt-004@0.2074<br>场景穿搭.txt/场景穿搭.txt-001@0.2228<br>颜色选择.txt/颜色选择.txt-001@0.2481<br>颜色选择.txt/颜色选择.txt-005@0.2528 | YES | NO | PASS |
| scene_student_daily | 颜色选择.txt/颜色选择.txt-002@0.2136<br>场景穿搭.txt/场景穿搭.txt-002@0.2437<br>场景穿搭.txt/场景穿搭.txt-001@0.2537<br>颜色选择.txt/颜色选择.txt-004@0.2680<br>材质知识.txt/材质知识.txt-005@0.3100 | YES | NO | PASS |
| scene_date_focus | 颜色选择.txt/颜色选择.txt-002@0.1826<br>场景穿搭.txt/场景穿搭.txt-001@0.1929<br>场景穿搭.txt/场景穿搭.txt-003@0.2080<br>颜色选择.txt/颜色选择.txt-006@0.2228<br>颜色选择.txt/颜色选择.txt-004@0.2326 | YES | NO | PASS |
| material_linen_wrinkles | 材质知识.txt/材质知识.txt-002@0.1695<br>洗涤养护.txt/洗涤养护.txt-006@0.2510<br>材质知识.txt/材质知识.txt-001@0.2731<br>洗涤养护.txt/洗涤养护.txt-007@0.2928<br>洗涤养护.txt/洗涤养护.txt-008@0.2966 | YES | NO | PASS |
| material_polyester_tradeoffs | 材质知识.txt/材质知识.txt-003@0.2370<br>洗涤养护.txt/洗涤养护.txt-004@0.2745<br>材质知识.txt/材质知识.txt-002@0.2856<br>材质知识.txt/材质知识.txt-001@0.2861<br>洗涤养护.txt/洗涤养护.txt-003@0.2867 | YES | NO | PASS |
| fit_high_waist_proportion | 版型知识.txt/版型知识.txt-003@0.2284<br>版型知识.txt/版型知识.txt-001@0.3457<br>颜色选择.txt/颜色选择.txt-003@0.3633<br>版型知识.txt/版型知识.txt-005@0.3694<br>版型知识.txt/版型知识.txt-004@0.3875 | YES | NO | PASS |
| fit_oversized_boundary | 版型知识.txt/版型知识.txt-006@0.2130<br>版型知识.txt/版型知识.txt-004@0.2458<br>版型知识.txt/版型知识.txt-005@0.3168<br>材质知识.txt/材质知识.txt-005@0.3787<br>颜色选择.txt/颜色选择.txt-003@0.3789 | YES | NO | PASS |
| unsupported_fireproof_standard | 材质知识.txt/材质知识.txt-003@0.3558<br>洗涤养护.txt/洗涤养护.txt-004@0.3652<br>洗涤养护.txt/洗涤养护.txt-016@0.3653<br>材质知识.txt/材质知识.txt-005@0.3685<br>洗涤养护.txt/洗涤养护.txt-010@0.3749 | NO | YES | FAIL |
| unsupported_polar_expedition | 材质知识.txt/材质知识.txt-001@0.2555<br>材质知识.txt/材质知识.txt-006@0.2808<br>材质知识.txt/材质知识.txt-003@0.2937<br>洗涤养护.txt/洗涤养护.txt-016@0.3062<br>洗涤养护.txt/洗涤养护.txt-003@0.3306 | NO | YES | FAIL |