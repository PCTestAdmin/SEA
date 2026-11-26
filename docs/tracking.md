# Object Tracking (v0.12)

The optional Vision AI detector can now be used on a sequence of selected video frames. Set up the [COCO model](vision-ai.md) first. No new model download or dependency is needed. OWLv2 text-conditioned tracking is not yet implemented.

`track_objects(path,start_s=0,duration_s=10,samples=6,threshold=.5,min_iou=.3,labels=None,limit=12)` returns a structured report. Use an authorized local video, a 0.25–60 second window and 2–12 evenly spaced requested sample times (end excluded). Known media duration bounds the window. Optional labels select up to eight exact COCO class names. Up to 20 detections are returned per sample, with truncation flags. Filtering is applied to at most 50 detector predictions. The model is loaded once per call, on CPU.

Tracks are linked only between consecutive successful samples when same-class bounding boxes meet the requested intersection-over-union threshold (0.1–1) and each has exactly one candidate on the other side. Ambiguous matches, failed frames and missed detections end existing tracks. This deliberately favors fragmentation over unsupported identity claims. Track IDs and observation IDs are local to one report. A unique overlap is still only a tentative association.

Observations contain requested times, scores, normalized boxes and center coordinates. Net center shifts and sampled center path length are in normalized image units (x and y independently normalized), not meters, speed, or real-world movement. Camera motion, perspective and sampling affect them. Single-observation tracks have null movement metrics. A gap does not imply that an object left the scene.

`view_object_tracks(...)` reruns the analysis and creates a contact sheet showing sample times, status and tentative track IDs. It does not reuse prior reports. IDs and predictions may differ between calls. The image is sent to the MCP host/model.

Decode failures and unattempted samples remain visible. The soft 65-second scheduling budget starts after model loading; an in-progress decode or inference can run longer. No continuous tracking, re-identification, face recognition, cross-video identity linking or exhaustive counting. No persistent storage is created by this feature.

## Verification

Core tests exercise movement, ambiguous matches, gaps, limits and annotated output. A separate real-model CI smoke test generates a short video from the public cat test fixture and verifies repeated detections across two requested frames. This checks the integration, not tracking accuracy for moving objects. See [tests](../tests/test_tracking.py) and [Vision AI CI](https://github.com/PCTestAdmin/SEA/actions/workflows/vision.yml).
