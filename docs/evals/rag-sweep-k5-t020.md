# RAG Retrieval Report

## Summary

- Cases: 16
- Positive hits: 7
- Hit rate: 50.00%
- False accepts: 0
- False accept rate: 0.00%
- Top K: 5
- Distance threshold: 0.2

## Results

| Case | Accepted Chunks | Hit | False Accept | Pass |
| --- | --- | --- | --- | --- |
| care_cotton_tshirt | 洗涤养护.txt/洗涤养护.txt-001@0.1974 | YES | NO | PASS |
| care_wool_sweater | 洗涤养护.txt/洗涤养护.txt-009@0.1990<br>材质知识.txt/材质知识.txt-004@0.1997 | YES | NO | PASS |
| care_denim_fading | - | NO | NO | FAIL |
| color_commute | 场景穿搭.txt/场景穿搭.txt-001@0.1416<br>颜色选择.txt/颜色选择.txt-002@0.1639 | YES | NO | PASS |
| color_daily_basic | 颜色选择.txt/颜色选择.txt-002@0.1822<br>场景穿搭.txt/场景穿搭.txt-001@0.1999 | YES | NO | PASS |
| care_silk | 洗涤养护.txt/洗涤养护.txt-005@0.1685<br>洗涤养护.txt/洗涤养护.txt-007@0.1952<br>洗涤养护.txt/洗涤养护.txt-008@0.1994 | YES | NO | PASS |
| care_knit_drying | - | NO | NO | FAIL |
| color_interview | 颜色选择.txt/颜色选择.txt-002@0.1536 | YES | NO | PASS |
| scene_student_daily | - | NO | NO | FAIL |
| scene_date_focus | 颜色选择.txt/颜色选择.txt-002@0.1801<br>场景穿搭.txt/场景穿搭.txt-001@0.1905 | NO | NO | FAIL |
| material_linen_wrinkles | 材质知识.txt/材质知识.txt-002@0.1697 | YES | NO | PASS |
| material_polyester_tradeoffs | - | NO | NO | FAIL |
| fit_high_waist_proportion | - | NO | NO | FAIL |
| fit_oversized_boundary | - | NO | NO | FAIL |
| unsupported_fireproof_standard | - | NO | NO | PASS |
| unsupported_polar_expedition | - | NO | NO | PASS |