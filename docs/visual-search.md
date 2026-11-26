# Visual Search (v0.19)

SEA provides model-free search by visual example. The host interprets the matches. This is neither semantic search nor object, face or identity recognition.

## Reusable whole-frame search

Set SEA_INDEX_DIR as described in temporal-index.md. With explicit user approval, call build_video_index(path,confirm=true) followed by build_visual_index(path,frame_stride=30,confirm=true). SEA selects decoded presentation ordinals 0, stride, 2*stride, etc., without FPS resampling. Choose stride 1–300 and at most 12000 samples per index. A single bounded FFmpeg decode (120-second timeout) generates 32x32 RGB samples, checks the count against the temporal index and stores 48 coarse RGB means plus 56 luminance comparison bits per sample. The stored descriptors are not original frames, but may reveal coarse colors and layout. Keep the unencrypted index directory private. A matching index is reused; changing stride requires explicit deletion and rebuilding.

search_visual_index(path,reference_image=...,threshold=.9,limit=30) accepts an authorized local PNG/JPEG. Alternatively, supply reference_frame, an indexed ordinal divisible by the stored stride; the reference itself is excluded. Similarity = 0.7 * (1 - mean absolute coarse RGB difference / 255) + 0.3 * (1 - normalized Hamming distance of luminance differences). Threshold 0–1; up to 100 results sorted by similarity then ordinal. No learned embeddings, probabilities or semantic labels. The score is not calibrated. Candidate metadata includes decoder-reported timestamp ticks and relative seconds (origin = first known video PTS). Search reads stored descriptors without decoding the video again. Verify matching frames with read_video_frames within its 100000 ordinal limit; pixel retrieval is not accelerated by the index.

Whole-frame signatures stretch images to a square, use coded orientation and can differ with crop, aspect ratio, illumination, viewpoint, compression and resizing. A reference image uses Pillow bilinear resize after bounded loading; video uses FFmpeg bilinear resize. Similar objects with different backgrounds may not match; visually different objects may match. No inference of identity, behavior or absence. Unindexed frames are not searched.

delete_visual_index(path,confirm=true) removes descriptors but preserves timestamps and notes. Deleting a temporal index also deletes its descriptors. Deletion is logical only. Source revision checks detect ordinary metadata changes, not malicious modifications. Up to eight indexes through the temporal store; no additional dependencies or network calls.

## Search for a patch instead of a whole frame

search_video_template(path,reference_image,cursor=0,sample_fps=2,threshold=.9,expected_revision=...) examines one contiguous four-second segment at 1, 2 or 4 fps. Provide a textured PNG/JPEG patch 4x4 through 224x126 pixels at the same scale as the 448x252 letterboxed video samples. The existing normalized grayscale cross-correlation algorithm returns up to ten nonoverlapping matches per sampled frame. Boxes are normalized to the letterboxed sample, timestamps approximate. No scale, rotation or perspective invariance. Follow next_cursor until null, keep the source revision, and report partial/failed pages. This route writes no persistent data. It does not use or require the visual index.

Tests cover real synthetic video decoding, recurring black/white frame searches, external reference image, descriptor reuse, cascade deletion, mismatched counts and a synthetic template localization test. The template unit test uses controlled in-memory sampled frames; accuracy on real-world footage is not yet benchmarked.
