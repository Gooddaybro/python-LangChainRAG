# RAG Retrieval Report

## Configuration

- Embedding provider: Jina
- Embedding model: `jina-embeddings-v4`
- Indexed chunks: 34
- Knowledge source: committed local knowledge files

## Summary

- Cases: 10
- Positive hits: 8
- Hit rate: 100.00%
- False accepts: 2
- False accept rate: 100.00%
- Top K: 3
- Distance threshold: 0.7

## Results

| Case | Accepted Chunks | Hit | False Accept | Pass | Failure Classification |
| --- | --- | --- | --- | --- | --- |
| care_cotton_tshirt | 洗涤养护.txt/洗涤养护.txt-001@0.1974<br>洗涤养护.txt/洗涤养护.txt-006@0.2106<br>洗涤养护.txt/洗涤养护.txt-003@0.2198 | YES | NO | PASS | - |
| care_wool_sweater | 洗涤养护.txt/洗涤养护.txt-009@0.1990<br>洗涤养护.txt/洗涤养护.txt-014@0.2036<br>洗涤养护.txt/洗涤养护.txt-003@0.2298 | YES | NO | PASS | - |
| care_denim_fading | 洗涤养护.txt/洗涤养护.txt-010@0.2194<br>洗涤养护.txt/洗涤养护.txt-002@0.2315<br>洗涤养护.txt/洗涤养护.txt-015@0.2549 | YES | NO | PASS | - |
| color_commute | 颜色选择.txt/颜色选择.txt-002@0.1642<br>颜色选择.txt/颜色选择.txt-004@0.2325<br>颜色选择.txt/颜色选择.txt-006@0.2790 | YES | NO | PASS | - |
| color_daily_basic | 颜色选择.txt/颜色选择.txt-002@0.1822<br>颜色选择.txt/颜色选择.txt-004@0.2210<br>颜色选择.txt/颜色选择.txt-006@0.2361 | YES | NO | PASS | - |
| care_silk | 洗涤养护.txt/洗涤养护.txt-005@0.1703<br>洗涤养护.txt/洗涤养护.txt-007@0.1969<br>洗涤养护.txt/洗涤养护.txt-008@0.2012 | YES | NO | PASS | - |
| care_knit_drying | 洗涤养护.txt/洗涤养护.txt-003@0.2641<br>洗涤养护.txt/洗涤养护.txt-008@0.3010<br>洗涤养护.txt/洗涤养护.txt-009@0.3046 | YES | NO | PASS | - |
| color_interview | 颜色选择.txt/颜色选择.txt-002@0.1536<br>颜色选择.txt/颜色选择.txt-004@0.2059<br>颜色选择.txt/颜色选择.txt-001@0.2464 | YES | NO | PASS | - |
| unsupported_fireproof_standard | 洗涤养护.txt/洗涤养护.txt-004@0.3661<br>洗涤养护.txt/洗涤养护.txt-016@0.3669<br>洗涤养护.txt/洗涤养护.txt-010@0.3766 | NO | YES | FAIL | noisy_retrieval |
| unsupported_polar_expedition | 洗涤养护.txt/洗涤养护.txt-016@0.3054<br>洗涤养护.txt/洗涤养护.txt-003@0.3296<br>洗涤养护.txt/洗涤养护.txt-001@0.3316 | NO | YES | FAIL | noisy_retrieval |
