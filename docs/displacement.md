# Precision Displacement (experimental)

SEA calls the actual upstream [NASA JPL autoRIFT](https://github.com/nasa-jpl/autoRIFT/tree/v2.1.1) Python interface, not a substitute algorithm. autoRIFT is a separately installed Apache-2.0 dependency, copyright 2019 California Institute of Technology, U.S. Government Sponsorship Acknowledged. See the upstream [license](https://github.com/nasa-jpl/autoRIFT/blob/v2.1.1/LICENSE), source notices (including export restrictions) and [research paper](https://doi.org/10.3390/rs13040749). SEA is not endorsed by NASA or JPL. No upstream source/binary is redistributed.

## Setup (Linux/macOS)

Install Miniforge/Conda, then from the SEA source directory:

```bash
conda create -n sea-autorift -c conda-forge --override-channels python=3.11 autorift=2.1.1 pip ffmpeg
conda activate sea-autorift
python -m pip install .
sea doctor
```

Configure your MCP client with the absolute Python interpreter from this environment and your authorized media folder, as in installation.md. autoRIFT is not installed via pip by SEA. Windows native Conda packages are not provided by this integration; use a separately configured Linux/WSL host if appropriate. Normal SEA installation continues to work on Windows without autoRIFT.

## Tools and constraints

- autorift_status: package/version discovery; no import or inference guarantee.
- measure_displacement(path_a,path_b,search_radius=12): equal-size PNG/JPEG images, downsample to at most 768 pixels on the long side. Radius integer 6–24 sampled pixels. At least eight grid points per axis; fixed 32-pixel chip and spacing. Uses upstream runAutorift with one thread and oversampling 16; no Geogrid or satellite preprocessing.
- view_displacement_field: reruns analysis, draws raw native vectors at grid centers at 2x scale, with distinct colors for matched, interpolated and missing points. Raw source-order sign convention is retained rather than claiming a registration transform. Upstream Cartesian y is positive upward. Validate direction with known translations for the application.

No files outside authorized media roots are accepted. A private temporary directory holds numeric arrays only for the call; a native worker runs with a 90-second timeout. It may fail on incompatible builds. Reports distinguish direct accepted matches, interpolation and unavailable values. Medians include direct matches only. Output is in sampled-image pixels, not physical distances or velocities. Requires suitable textured, aligned imagery; camera changes and repeated patterns can cause false matches. No guaranteed physical deformation or diagnosis. Results go to the MCP host.

The [native CI](https://github.com/PCTestAdmin/SEA/actions/workflows/autorift.yml) uses actual Conda autoRIFT on a generated 512x512 image pair with a known 5-pixel horizontal and 3-pixel vertical shift. It checks absolute displacement magnitudes and matched points, not signed registration or field accuracy. This is a synthetic integration smoke test, not a field benchmark. See [tests](../tests/test_displacement.py).
