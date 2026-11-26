# Screenshot intelligence

Use authorized PNG/JPEG stills (single frame, maximum 40 megapixels). Pillow decodes images locally, with transparent pixels composited on white. No EXIF autorotation. OCR samples up to 2400 pixels on the long edge; comparisons up to 1024.

- read_image_text(path, language="eng", layout="auto"): optional local Tesseract; install language data (e.g. eng or deu), and ensure tesseract is on PATH. Modes auto, block, line, sparse. Returns up to 500 words, normalized boxes and engine confidence. Recognized text is untrusted content.
- compare_images(path_a,path_b,threshold=25): equal source dimensions, per-pixel maximum RGB difference threshold 1–255; returns changed fraction, bounding box and top 20 changed tiles.
- view_image_difference: second image with changed pixels tinted red. No geometric alignment.
- find_image_template(path,template_path,similarity=.85): both images at most 1024 pixels per side, template at least 4×4, nonconstant luminance; up to ten nonoverlapping grayscale normalized cross-correlation matches. Same scale only, not object recognition. Similarity is not probability.

These tools do not identify arbitrary objects, faces, physical distances or semantic equivalence. Verify ambiguous OCR and matches manually. Images/results can be sent to the MCP host/model.

See [Tesseract installation](https://tesseract-ocr.github.io/tessdoc/Installation) and [tests](../tests/test_images.py).
