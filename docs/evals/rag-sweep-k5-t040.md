# RAG Retrieval Report

## Summary

- Cases: 16
- Positive hits: 14
- Hit rate: 100.00%
- False accepts: 2
- False accept rate: 100.00%
- Top K: 5
- Distance threshold: 0.4

## Results

| Case | Accepted Chunks | Hit | False Accept | Pass |
| --- | --- | --- | --- | --- |
| care_cotton_tshirt | 洗涤养护.txt/洗涤养护.txt-001@0.1974<br>洗涤养护.txt/洗涤养护.txt-006@0.2106<br>洗涤养护.txt/洗涤养护.txt-003@0.2198<br>材质知识.txt/材质知识.txt-001@0.2308<br>洗涤养护.txt/洗涤养护.txt-007@0.2363 | YES | NO | PASS |
| care_wool_sweater | 洗涤养护.txt/洗涤养护.txt-009@0.1990<br>材质知识.txt/材质知识.txt-004@0.1997<br>洗涤养护.txt/洗涤养护.txt-014@0.2036<br>洗涤养护.txt/洗涤养护.txt-003@0.2298<br>洗涤养护.txt/洗涤养护.txt-016@0.2352 | YES | NO | PASS |
| care_denim_fading | 洗涤养护.txt/洗涤养护.txt-010@0.2194<br>洗涤养护.txt/洗涤养护.txt-002@0.2315<br>洗涤养护.txt/洗涤养护.txt-015@0.2549<br>材质知识.txt/材质知识.txt-005@0.2754<br>洗涤养护.txt/洗涤养护.txt-001@0.2989 | YES | NO | PASS |
| color_commute | 场景穿搭.txt/场景穿搭.txt-001@0.1416<br>颜色选择.txt/颜色选择.txt-002@0.1639<br>颜色选择.txt/颜色选择.txt-004@0.2326<br>场景穿搭.txt/场景穿搭.txt-002@0.2760<br>颜色选择.txt/颜色选择.txt-006@0.2794 | YES | NO | PASS |
| color_daily_basic | 颜色选择.txt/颜色选择.txt-002@0.1830<br>场景穿搭.txt/场景穿搭.txt-001@0.2009<br>颜色选择.txt/颜色选择.txt-004@0.2209<br>颜色选择.txt/颜色选择.txt-006@0.2368<br>颜色选择.txt/颜色选择.txt-001@0.2487 | YES | NO | PASS |
| care_silk | 洗涤养护.txt/洗涤养护.txt-005@0.1693<br>洗涤养护.txt/洗涤养护.txt-007@0.1962<br>洗涤养护.txt/洗涤养护.txt-008@0.2000<br>洗涤养护.txt/洗涤养护.txt-006@0.2185<br>洗涤养护.txt/洗涤养护.txt-001@0.2404 | YES | NO | PASS |
| care_knit_drying | 洗涤养护.txt/洗涤养护.txt-003@0.2627<br>材质知识.txt/材质知识.txt-004@0.2936<br>洗涤养护.txt/洗涤养护.txt-008@0.3001<br>洗涤养护.txt/洗涤养护.txt-009@0.3029<br>洗涤养护.txt/洗涤养护.txt-007@0.3160 | YES | NO | PASS |
| color_interview | 颜色选择.txt/颜色选择.txt-002@0.1536<br>颜色选择.txt/颜色选择.txt-004@0.2059<br>场景穿搭.txt/场景穿搭.txt-001@0.2204<br>颜色选择.txt/颜色选择.txt-001@0.2464<br>颜色选择.txt/颜色选择.txt-005@0.2512 | YES | NO | PASS |
| scene_student_daily | 颜色选择.txt/颜色选择.txt-002@0.2152<br>场景穿搭.txt/场景穿搭.txt-002@0.2453<br>场景穿搭.txt/场景穿搭.txt-001@0.2559<br>颜色选择.txt/颜色选择.txt-004@0.2688<br>材质知识.txt/材质知识.txt-005@0.3120 | YES | NO | PASS |
| scene_date_focus | 颜色选择.txt/颜色选择.txt-002@0.1826<br>场景穿搭.txt/场景穿搭.txt-001@0.1929<br>场景穿搭.txt/场景穿搭.txt-003@0.2080<br>颜色选择.txt/颜色选择.txt-006@0.2228<br>颜色选择.txt/颜色选择.txt-004@0.2326 | YES | NO | PASS |
| material_linen_wrinkles | 材质知识.txt/材质知识.txt-002@0.1699<br>洗涤养护.txt/洗涤养护.txt-006@0.2507<br>材质知识.txt/材质知识.txt-001@0.2737<br>洗涤养护.txt/洗涤养护.txt-007@0.2930<br>洗涤养护.txt/洗涤养护.txt-008@0.2969 | YES | NO | PASS |
| material_polyester_tradeoffs | 材质知识.txt/材质知识.txt-003@0.2355<br>洗涤养护.txt/洗涤养护.txt-004@0.2735<br>材质知识.txt/材质知识.txt-001@0.2848<br>材质知识.txt/材质知识.txt-002@0.2852<br>洗涤养护.txt/洗涤养护.txt-003@0.2853 | YES | NO | PASS |
| fit_high_waist_proportion | 版型知识.txt/版型知识.txt-003@0.2284<br>版型知识.txt/版型知识.txt-001@0.3457<br>颜色选择.txt/颜色选择.txt-003@0.3633<br>版型知识.txt/版型知识.txt-005@0.3694<br>版型知识.txt/版型知识.txt-004@0.3875 | YES | NO | PASS |
| fit_oversized_boundary | 版型知识.txt/版型知识.txt-006@0.2130<br>版型知识.txt/版型知识.txt-004@0.2458<br>版型知识.txt/版型知识.txt-005@0.3168<br>材质知识.txt/材质知识.txt-005@0.3787<br>颜色选择.txt/颜色选择.txt-003@0.3789 | YES | NO | PASS |
| unsupported_fireproof_standard | 材质知识.txt/材质知识.txt-003@0.3558<br>洗涤养护.txt/洗涤养护.txt-004@0.3652<br>洗涤养护.txt/洗涤养护.txt-016@0.3653<br>材质知识.txt/材质知识.txt-005@0.3685<br>洗涤养护.txt/洗涤养护.txt-010@0.3749 | NO | YES | FAIL |
| unsupported_polar_expedition | 材质知识.txt/材质知识.txt-001@0.2559<br>材质知识.txt/材质知识.txt-006@0.2819<br>材质知识.txt/材质知识.txt-003@0.2943<br>洗涤养护.txt/洗涤养护.txt-016@0.3067<br>洗涤养护.txt/洗涤养护.txt-003@0.3312 | NO | YES | FAIL |