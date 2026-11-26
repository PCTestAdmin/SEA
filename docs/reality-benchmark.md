# SEA Reality Benchmark — paired evaluation protocol

**Status: evaluation infrastructure, not a measured model improvement.** The included synthetic MP4 smoke suite tests the pipeline, not real-world understanding. No model scores are shipped. SEA does not run a model, send videos, download datasets or require an API key.

## 1. Freeze a suite before testing

Use local, authorized MP4 clips and a JSON specification like [smoke_spec.json](../benchmarks/smoke_spec.json). Each clip has an opaque ID, relative filename, source_kind (real or synthetic), source attribution and questions with unique IDs, category, 2–6 options and one zero-based correct answer. Have a human verify all annotations against the exact clip. Freeze the inputs before any model run.

For a real-world pilot, collect at least 30 independently recorded clips across temporal order, object interactions, occlusion, camera movement, fast motion, audio-visual association and longer multi-step actions; keep several unseen clips per category. For each clip write 3–5 unambiguous questions, including hard negatives and distractors, with option order varied before freezing. A second reviewer should check labels and resolve disagreements. Use opaque filenames and strip revealing metadata where appropriate. Do not use private recordings without permission.

An external source is [Google DeepMind Perception Test](https://github.com/google-deepmind/perception_test) (Patraucean et al., NeurIPS 2023). The upstream repository provides sample MP4 and annotation archives and documents CC BY 4.0 for non-code materials. Download/extract them separately, retain attribution, and manually transcribe selected multiple-choice items into the SEA spec. Upstream validation/training cup-game clips may reveal the answer at the end: exclude these clips or apply and verify the official cut mapping before freezing. Do not claim an official leaderboard score. Public datasets may be contaminated by model training; prefer a separate fresh-recording holdout. No third-party videos are redistributed here.

```bash
sea-benchmark prepare private-spec.json /absolute/media ./frozen
sea-benchmark packet frozen/suite.json clip001 /absolute/media
```

The output directory must not already exist. Preparation hashes MP4 bytes, writes a public suite and separate answer key. The packet checks the media hash again and emits only the selected questions and media reference. Keep the original spec and key.json outside the model's accessible files; even the public suite contains source metadata not needed by the model.

## 2. Run both conditions with the same exact model

Use fresh isolated sessions for each clip and condition. Both receive the same original video input (or identical fixed frame/audio presentation if the host cannot accept MP4) and same question packet, system prompt, model version, settings, time/token budget and access to other tools. No outside lookup. The only planned difference is SEA access: baseline has it disabled; assisted has it enabled. Give the assisted model permission to access only the clip's media directory, not keys. If the baseline cannot take the same raw video input, label a separate access-capability experiment; do not call it a controlled accuracy comparison. Counterbalance which condition runs first, repeat on independent sessions, record model versions, actual prompt and input representation. Disable memory/cross-session leakage.

Use [protocol.example.json](../benchmarks/protocol.example.json) as a starting point, fill with actual settings, then:

```bash
sea-benchmark run-template frozen/suite.json baseline protocol.json > baseline.json
sea-benchmark run-template frozen/suite.json sea protocol.json > assisted.json
```

For each clip collect the model's answer mapping and transfer into the run file. Use null for abstention, invalid model output or failed clip (record failures as error). Update clip_runs with status completed/error, actual number of SEA calls (zero for baseline), elapsed seconds. Pending templates cannot be scored. Keep actual transcripts/tool logs separately for audit, including any failed tool calls. No manual correction of model answers. Report no-use assisted clips. The tool does not attest the authenticity of transcripts or enforce host settings; operators must verify them.

## 3. Score without cherry-picking

```bash
sea-benchmark score frozen/suite.json frozen/key.json baseline.json assisted.json > result.json
```

The scorer requires both full sets of answers, matching suite hashes, matching model/host/protocol and completed/error statuses. Abstentions and errors count as incorrect. It reports paired accuracy and percentage-point delta, improved and regressed questions, separate real/synthetic and skill breakdowns, clip-level accuracy and equally weighted clip-macro accuracy, elapsed time and tool calls. No fabricated baseline, significance test or automatic model invocation. Results are descriptive; questions within one clip are correlated, so uncertainty estimates should resample independent clips rather than individual questions. Do not publish identifying video paths or personal data.

## 4. Controlled smoke test (not a real-world benchmark)

```bash
python examples/make_mp4_demo.py demo.mp4
sea-benchmark prepare benchmarks/smoke_spec.json . ./smoke-frozen
```

The smoke spec asks about the black/white/black scene, sound and transitions. CI generates an actual MPEG-4/AAC MP4 directly from 24 raw RGB frames and exactly 96000 PCM samples, using explicit stream maps, single-threaded encoders, intra frames, a six-second output limit and no interactive stdin. Tests require complete audio and visual coverage, both scene changes and both nearby audio transitions, and exercise packet generation, scoring, error cases and CLI. Mock answer values in unit tests are only test inputs, never measured model results.

No new mandatory dependency. The initial benchmark is multiple-choice video QA; free-form narrative quality, precise temporal localization and long-video generalization remain follow-up evaluation tasks.
