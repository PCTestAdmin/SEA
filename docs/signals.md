# Recorded sensor and signal perception

`sense_signals(path, time_column, channels, change_thresholds=None)` analyzes authorized local UTF-8 comma-separated files. Example:

```csv
time_s,temperature_c,fan_rpm
0,38,900
1,39,900
2,44,1500
3,43,1400
```

Ask the agent to select temperature_c and fan_rpm and optionally use a threshold of 4 for temperature_c. SEA reports min/max, mean, median, population standard deviation, net change and up to eight largest adjacent sample changes per channel. With a positive threshold, SEA returns the hit count and up to twenty strongest matching changes. Values are in the original units; names do not prove calibration.

Pearson correlation compares simultaneous rows, not time-weighted samples or lagged events. Constant channels have null correlation. A high coefficient does not establish cause.

Limits: 2 MiB, 20,000 rows, 64 unique header names, 1–8 selected channels, strictly increasing numeric time in seconds, finite numeric selected values. Missing data, duplicate timestamps and malformed CSV are rejected, not silently repaired. SEA does not connect to live devices. No file is modified. Selected summaries go to the MCP host.

See [tests](../tests/test_signals.py) for reproducible examples.
