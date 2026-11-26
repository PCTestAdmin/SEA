# Vision AI (optional)

SEA's optional CPU detector uses the official Torchvision SSDLite320 MobileNetV3 Large COCO_V1 checkpoint. This is a pretrained third-party model, not a model trained by SEA. See [model documentation](https://docs.pytorch.org/vision/main/models/generated/torchvision.models.detection.ssdlite320_mobilenet_v3_large.html) for upstream metrics, classes and limitations. Upstream weights are approximately 13.4 MB; the optional PyTorch runtime is substantially larger. No model weights are included in SEA.

## Setup

In the same persistent Python environment as SEA, install the optional dependencies from the checkout:

```bash
python -m pip install ".[vision]"
```

For pipx installations use `pipx inject sea-perception-mcp "torch>=2.6,<3" "torchvision>=0.21,<1"`. Choose a compatible platform-specific PyTorch build using [the official installation guide](https://pytorch.org/get-started/locally/) if needed.

Explicitly download the [official checkpoint](https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth) into a private local directory. Add SEA_VISION_WEIGHTS with the absolute checkpoint filename to the existing SEA MCP server env object. Keep SEA_MEDIA_ROOTS and any other existing settings. Restart the host. Do not point the setting at untrusted checkpoints. SEA verifies the published SHA-256 filename prefix a79551df (not a signed full checksum), records the full digest, limits file size and loads weights-only on CPU. Both default model and backbone downloads are disabled.

Call vision_status to check prerequisites, then detect_objects with an authorized local image. Readiness is discovery only, not proof of a functioning runtime. No automatic package or model download occurs in MCP calls.

## Tools

- vision_status(): discover optional dependencies and verify checkpoint prefix.
- detect_objects(path,time_s=0,threshold=.5,limit=20): PNG/JPEG or a selected video frame, normalized [left,top,right,bottom] boxes, labels, model scores, counts and full checkpoint digest. Threshold 0.1–1, limit 1–50. Still images require time_s=0. Video frames use approximate timestamps and up to 512-pixel samples.
- view_detections(...): return a PNG with matching evidence IDs, boxes and labels. This runs inference again; results can differ across runtime versions.

Only fixed COCO object classes are supported. A person class means a predicted person, not an identity. Scores are not calibrated probabilities. Missing detections do not prove absence. No tracking, open-vocabulary recognition, physical depth, or automatic diagnosis. No EXIF autorotation. Model and preprocessing can miss small or unusual objects. The MCP host may transmit results to its model provider.

## Verification

Core tests cover normalization, limits, offline opt-in and image output. The separate Vision AI CI lane downloads official weights and a publicly accessible COCO validation image (000000039769.jpg, two cats) only for testing and checks for a cat prediction. This is a smoke test, not a quantitative benchmark. The fixture and weights are not redistributed in SEA. See [CI](https://github.com/PCTestAdmin/SEA/actions/workflows/vision.yml).
