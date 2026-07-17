# RAG Retrieval Parameter Decision

## Decision

Set `RAG_TOP_K = 3` and `RAG_DISTANCE_THRESHOLD = 0.25`.

The selection rule is: first require `false_accept_count == 0`; then choose the
highest `positive_hit_count`; break ties with the smaller `top_k`, then the
stricter (smaller) distance threshold. The selected configuration returns 13
of 14 positive cases and accepts none of the two out-of-scope cases.

## Method

The original grid (`0.40`, `0.55`, `0.70`) had no eligible configuration:
every setting accepted both out-of-scope questions. The baseline scores show
the closest invalid result at a distance of `0.2556`, so the original minimum
threshold of `0.40` could not test the reject boundary. A follow-up grid
(`0.20`, `0.25`, `0.30`) was therefore run before changing any runtime value.

| top_k | threshold | positive_hit_count | hit_rate | false_accept_count | selected | decision note |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.20 | 6 | 42.86% | 0 | no | Safe but rejects too many grounded answers. |
| 1 | 0.25 | 10 | 71.43% | 0 | no | Safe, but fewer hits than `top_k=3`. |
| 1 | 0.30 | 11 | 78.57% | 1 | no | The polar-expedition question is accepted. |
| 1 | 0.40 | 11 | 78.57% | 2 | no | Both out-of-scope questions are accepted. |
| 1 | 0.55 | 11 | 78.57% | 2 | no | Both out-of-scope questions are accepted. |
| 1 | 0.70 | 11 | 78.57% | 2 | no | Both out-of-scope questions are accepted. |
| 3 | 0.20 | 7 | 50.00% | 0 | no | Safe but rejects too many grounded answers. |
| 3 | 0.25 | 13 | 92.86% | 0 | **yes** | Highest hit count among safe settings; beats the tie at `top_k=5`. |
| 3 | 0.30 | 14 | 100.00% | 1 | no | The polar-expedition question is accepted. |
| 3 | 0.40 | 14 | 100.00% | 2 | no | Both out-of-scope questions are accepted. |
| 3 | 0.55 | 14 | 100.00% | 2 | no | Both out-of-scope questions are accepted. |
| 3 | 0.70 | 14 | 100.00% | 2 | no | Both out-of-scope questions are accepted. |
| 5 | 0.20 | 7 | 50.00% | 0 | no | Safe but rejects too many grounded answers. |
| 5 | 0.25 | 13 | 92.86% | 0 | no | Same safe hit count as `top_k=3`; tie-breaker chooses the smaller `top_k`. |
| 5 | 0.30 | 14 | 100.00% | 1 | no | The polar-expedition question is accepted. |
| 5 | 0.40 | 14 | 100.00% | 2 | no | Both out-of-scope questions are accepted. |
| 5 | 0.55 | 14 | 100.00% | 2 | no | Both out-of-scope questions are accepted. |
| 5 | 0.70 | 14 | 100.00% | 2 | no | Both out-of-scope questions are accepted. |

## Consequence

The stricter threshold deliberately rejects the `care_knit_drying` positive
case. This is recorded as `threshold_rejected` and is preferable to giving a
confident answer to either unsupported question. The next knowledge expansion
or retrieval improvement must keep this decision report as the comparison
baseline.
