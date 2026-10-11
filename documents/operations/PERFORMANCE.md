# Performance measurement

Nexora records a baseline before a cache, index, query rewrite or provider change is introduced. The measurements are process-local Prometheus-compatible metrics and structured logs; they do not store request bodies, document text, prompts or credentials.

## Measurements available

| Measurement | Metric | Use |
| --- | --- | --- |
| API latency | `nexora_http_request_duration_seconds_count` and `_sum` | Compare endpoint latency before and after a change. |
| Database query count | `nexora_database_queries_total` | Detect N+1 queries and unnecessary database work per endpoint. |
| Database query time | `nexora_database_query_duration_seconds_count` and `_sum` | Separate database time from total endpoint latency. |
| Process memory | `nexora_process_resident_memory_bytes` | Identify memory growth during uploads, retrieval and document processing. |
| Provider latency | `nexora_provider_latency_seconds_count` and `_sum` | Compare Qdrant and OpenRouter latency and failures independently from Nexora code. |
| Provider failures | `nexora_provider_requests_total{result="failed"}` | Decide whether retries, fallback or provider investigation is required. |

The API middleware also writes `duration_ms`, `db_query_count`, `db_query_duration_ms` and `memory_rss_bytes` to the structured request log. Qdrant and OpenRouter measurements include the provider, operation and success or failure result.

## Access and baseline procedure

Metrics remain unavailable unless `METRICS_BEARER_TOKEN` is configured. Query them with an authorized operational client:

```powershell
Invoke-WebRequest http://localhost:8000/metrics -Headers @{ Authorization = "Bearer <METRICS_BEARER_TOKEN>" }
```

For a representative scenario, record the metric output and application logs before making a performance change. Run the same scenario with comparable data, concurrency and provider configuration afterward. Compare request latency, query count, query duration, resident memory and provider latency. A cache or index is retained only when the measurement shows a useful improvement without violating data freshness, access controls or failure behavior.

Metrics are in-process. In a multi-replica deployment, scrape every API and worker process into the organization’s monitoring system before drawing aggregate conclusions.
