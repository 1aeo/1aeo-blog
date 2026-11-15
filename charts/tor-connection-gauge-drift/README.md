# Isolated Connection-Gauge Accounting Model (`tor-0.4.8.16`)

Reproduces the synthetic accounting model curve (`conn-gauge-repro-drift.png`) in [The Metric That Drifts to Zero: An Accounting Bug in Tor's Connection Gauge](https://1aeo.com/blog/tor-connection-gauge-drift.html).

`gauge-accounting-model.c` compiles the verbatim `rep_hist_note_conn_opened`, `rep_hist_note_conn_closed`, and `rep_hist_get_conn_opened` functions from `tor-0.4.8.16` (`src/feature/stats/rephist.c`), counts 40,000 simulated inbound open connections, and applies 50,000 unmatched close calls to demonstrate the zero-floored decrement drift.

## Build and run

```sh
cc -O2 -Wall -Wextra -o gauge-accounting-model gauge-accounting-model.c
./gauge-accounting-model
```
