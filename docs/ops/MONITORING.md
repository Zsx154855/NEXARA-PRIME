# Monitoring and alerting (v0)

Everything here is deliberately small: stdout logs plus one scrape endpoint.

## What the process emits

**Request logs** — one JSON object per line on stdout:

```json
{"event":"http_request","request_id":"9f2c…","method":"POST","path":"/api/missions",
 "status":200,"duration_ms":31.4,"client":"172.17.0.1","user_agent":"curl/8.7"}
```

- `request_id` comes from `X-Request-Id` when the caller sets it, otherwise generated;
  it is echoed back in the response header so a user report can be traced to a line.
- Never logged: `Authorization`, `Cookie`, request bodies. (There is a test for this.)

**Metrics** — `GET /metrics` in Prometheus text format:

| metric | type | meaning |
|---|---|---|
| `nexara_uptime_seconds` | gauge | process uptime |
| `nexara_http_requests_total{method,path,status}` | counter | requests by route and status |
| `nexara_missions{state}` | gauge | missions currently stored, by state |
| `nexara_evidence_total` | gauge | evidence artifacts stored |

Access: loopback only by default. Set `NEXARA_METRICS_PUBLIC=1` only when a
scraper on another host needs it, and put it behind your proxy's auth.

## Thresholds worth alerting on

These are starting points, not tuned values. Each is expressed with the metrics
above so it can be wired without new instrumentation.

| Alert | Expression | Why |
|---|---|---|
| 5xx rate | `sum(rate(nexara_http_requests_total{status=~"5.."}[5m])) / sum(rate(nexara_http_requests_total[5m])) > 0.02` | 2% of requests failing for 5 minutes is a page |
| Latency | `histogram_quantile` is not available in v0; use log `duration_ms` p95 over 5 min > 2000 ms | the current latency signal lives in logs |
| Missions stuck | `nexara_missions{state="Execution"} > 0` for 30 min | a mission that never advances is a stuck worker |
| No traffic | `rate(nexara_http_requests_total[10m]) == 0` while the process is up | scrape or proxy is misconfigured |
| Disk | volume `/data` > 80% | SQLite and reports both live there |

## What is deliberately missing in v0

- No distributed tracing (no `trace_id` propagation across processes).
- No log shipping config: rely on the platform (`docker logs`, journald, k8s).
- No dashboards checked in. The metric names above are the contract.
- Latency percentiles require a histogram; that is the first thing to add if you
  adopt this beyond a single instance.
