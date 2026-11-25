# Autonomous recording investigation

`investigate_recording(path, start_s=0, span_s=60, max_windows=5, max_refinements=2)` selects bounded samples and revisits measured changes. The host agent interprets the evidence. No additional model, arbitrary commands or file writes.

The requested span is 0.25–1800 seconds, truncated to known duration. SEA divides it into up to five equal strata and samples up to six seconds near each center. Candidate bins contain a visual change flag (mean pixel difference >= 0.12), an adjacent audio-level change >= 12 dB with at least one bin >= -40 dBFS (floor -100 dBFS), or both. Window-boundary changes are not inferred. A heuristic priority favors multimodal bins and threshold exceedance; it is not a confidence score.

Up to two separated candidate timestamps are revisited using the detailed investigation engine, each in a window of up to four seconds. Reference candidate ID together with report-local event ID.

The response identifies scanned, failed, empty and unattempted windows, observed bin endpoints and modality counts. Unscanned ranges describe gaps between successfully sampled requested windows, not exact decoded coverage. Even sampled windows can miss events. A soft 75-second scheduling deadline prevents new work after the deadline; running decoders may finish later. The existing 45-second per-decoder timeout remains. At most 30 seconds of coarse requested windows and 8 seconds of refinement are scheduled. Up to 20 candidates are returned. No candidate does not mean nothing happened; correlation is not causation.

For exhaustive examination request additional bounded windows. Use only authorized local files. See [tests](../tests/test_survey.py), [investigation](investigation.md) and [setup](installation.md).
