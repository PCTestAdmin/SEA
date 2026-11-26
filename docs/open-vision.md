# Open Vision (optional)

Open Vision uses OWLv2 from Transformers for text-conditioned detection, not a fixed category list. SEA recommends the [Google OWLv2 base patch16 ensemble](https://huggingface.co/google/owlv2-base-patch16-ensemble). Third-party model weights are not bundled. The provider is optional and runs on CPU.

Install from the source checkout in the SEA environment:

```bash
python -m pip install ".[openvision]"
```

Explicitly fetch the recommended revision with the Hugging Face Hub CLI in that environment:

```bash
hf download google/owlv2-base-patch16-ensemble --revision 27d9485a27e88c5f0435d0ed8382dcb3b911ab46 --include "*.json" "*.txt" "model.safetensors" --local-dir ./sea-owlv2
```

Set SEA_OPEN_VISION_DIR in the existing MCP server env object to the absolute path of that directory. Restart the client. Only use trusted local model files and keep the directory private. SEA uses explicit local paths, local_files_only and safetensors; no model download happens during tool calls. The weight SHA-256 is returned for provenance, not validated against an authenticated published checksum. The model and runtime may require substantial disk space, RAM and CPU time.

Tools:

- open_vision_status(): readiness discovery, not an inference test.
- find_objects_by_text(path,queries,time_s=0,threshold=.2,limit=20): 1–8 distinct short queries, max 80 characters and model token limit; prefer short English phrases. Scores 0.05–1 threshold, max 50 returned matches. Normalized boxes, label-specific NMS at IoU > .5. Image or selected approximate video frame.
- view_text_matches(...): reruns inference and draws the returned boxes. The image goes to the MCP host.

Model predictions are uncertain, not verified facts or probabilities. No identities, tracking, metric depth, guaranteed counts, or absence claims. Multiple labels may describe the same object. Use OCR for screenshot text and fixed templates for known icons. This is not general visual question answering.

Core unit tests run on each push. The [Open Vision model test](https://github.com/PCTestAdmin/SEA/actions/workflows/openvision.yml) runs on relevant main-branch changes and can also be manually triggered; documentation-only changes do not download the model. It checks the recommended checkpoint against a public cat fixture; this is not an accuracy benchmark.
