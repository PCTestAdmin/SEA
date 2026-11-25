# Acoustic analysis

SEA v0.3 adds three MCP tools. All require an absolute authorized local media path and an analysis window of 0.25–30 seconds. Audio is the first stream, resampled to 16 kHz mono. No semantic classification is performed.

| Tool | Arguments | Result |
| --- | --- | --- |
| sense_audio | path, start_s, duration_s | Numeric spectral peaks, power bands, RMS and peak levels, threshold events |
| audio_spectrogram | path, start_s, duration_s, max_hz | PNG; 0 Hz at bottom, time left to right |
| compare_recordings | path_a, path_b, start_a_s, start_b_s, duration_s | Summaries and B-minus-A differences |

## Interpretation

A 1024-sample Hann FFT with 256-sample hop yields 15.625 Hz frequency bins. The strongest local peaks (up to five) are reported relative to the strongest bin. DC is excluded; spectral centroid is power weighted. Band fractions are relative spectral power, not calibrated physical energy. The PNG uses a fixed -90 to 0 dBFS amplitude color scale (navy to pale yellow), up to 900 time columns, with maximum pooling when needed. Its upper frequency is the highest included FFT bin. Image pixels do not replace numeric measurements.

Level bins are 100 ms. Active intervals use RMS >= -40 dBFS; level rise/drop flags require at least 12 dB difference between adjacent bins, with a -100 dBFS floor and one bin above the active threshold. These are heuristic level events, not statistical anomaly detection. Silent or unavailable values are null. Timestamps are approximate decoded offsets. Short transients may be missed or averaged out.

Comparisons require equal decoded durations; choose equivalent segments and recording conditions. There is no automatic alignment, quality score, source identification, machine diagnosis, or music transcription. Differences are B minus A.

## Reproducible verification

Run `python -m unittest discover -s tests -v`. The synthetic fixtures check a gated 440 Hz tone, level transitions near 0.5 and 1.5 seconds, a half-amplitude recording (~-6.02 dB), silence, duration limits and a valid spectrogram PNG. These are test expectations, not a field benchmark. See [CI](https://github.com/PCTestAdmin/SEA/actions/workflows/test.yml).

Results and images are passed to the MCP host/model. See [privacy and setup](installation.md).
