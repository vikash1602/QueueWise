# Waiting-Time Estimation

QueueWise shows every waiting customer an **estimate**, never a guarantee. This
document specifies the algorithm, its assumptions, and its test coverage.

## Inputs

| Input | Source |
|---|---|
| Per-customer service duration | `Service.avg_duration_minutes` — a rolling median of the last N completed services (N = `ESTIMATION_HISTORY_SIZE`, default 10). Falls back to `Service.duration_minutes` (the configured value) while there is no history. |
| Queue position | Count of live entries (WAITING or CALLED) with a lower token number for the same organization + service + operating day, plus one. |
| Active counters | `ServiceCounter` rows with `is_active=True` for the service (minimum 1). |

## Algorithm

```
wait(position, service):
    duration  = rolling_median(last N completed durations) or configured_duration
    counters  = max(active_counters(service), 1)
    batches   = ceil((position - 1) / counters)
    return batches * duration
```

- **Median, not mean**: one-off long services (a walk-in that needed extra
  care) do not skew the estimate. Durations outside `(0, 8h]` are treated as
  data errors and dropped.
- **Counters in parallel**: the queue is assumed to be served in token order by
  C identical counters working in parallel, so the customer waits for
  `ceil((position-1)/C)` service durations. With one counter this reduces to
  the classic `position-1` × duration.
- **CALLED entries count as load**: a called customer is assumed to still
  occupy their counter, so people behind them see the full remaining time of
  that service.
- **Recalculation**: estimates for all waiting entries are refreshed after any
  meaningful change — join, call, start, complete, no-show, and cancellation.

## Known simplifications

1. All counters are treated as interchangeable; per-counter speed is not modeled.
2. The first customer in line is always quoted "0 minutes" even if the person
   being served started recently — a deliberate simplicity trade-off.
3. Appointment-driven arrival patterns are not modeled; estimates only consider
   the live queue.

## Test coverage (`queues/tests.py`)

- `test_empty_history_uses_configured_duration` — no history → configured duration.
- `test_median_of_history_ignores_outliers` — an extreme duration is dropped.
- `test_multiple_counters_halve_wait` — 2 counters, position 5 → 2 batches.
- `test_zero_position_zero_wait` — boundary case.
- `test_completed_entry_fed_back_into_rolling_estimate` — a completion updates
  the rolling median and the following entries' estimates.
