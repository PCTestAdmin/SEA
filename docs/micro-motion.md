# Micro-Motion Intelligence (experimental)

SEA estimates small translations of a textured mechanical video region relative to its first sampled frame. The implementation is original, using a first-order brightness-constancy least-squares model with an additive illumination term, followed by a Hann-windowed temporal spectrum. It is not the MIT phase-based magnification algorithm or NASA autoRIFT. Research inspiration: [MIT phase-based video processing](https://people.csail.mit.edu/nwadhwa/phase-video/) (DARPA-supported) and [NASA JPL autoRIFT](https://github.com/nasa-jpl/autoRIFT). No upstream code is incorporated.

Tools:
- measure_micro_motion(path,box,start_s=0,duration_s=4,sample_fps=24,reference_box=None)
- view_motion_waveform(same arguments): reruns the measurement and returns a PNG chart.

Use a fixed-camera video of a mechanical target with two-dimensional texture and stable lighting. Boxes are normalized left,top,right,bottom in coded image orientation. Regions must be at least 16x16 sampled pixels. Optional nonoverlapping reference region should be stationary relative to the camera scene. Subtracting the reference estimates shared translation only; it cannot compensate rotation, zoom or perspective.

Limits: 0.25–8 seconds, 10/15/24/30/60 fps not exceeding reported average source frame rate, max 240 requested samples, max sample side 512 pixels. The model rejects estimates above 1.5 sample pixels or high residual/brightness change; thresholds are heuristic. Invalid samples have null displacement. Spectral peaks require all samples valid, at least two seconds, minimum demeaned RMS .025 sample pixels, and at least 25% of candidate spectral power in one bin. DC, first bin and Nyquist endpoint are excluded. Frequency resolution is sample rate divided by frame count; no high-frequency or absence guarantees.

Temporal sampling is approximate. Variable frame rate, rolling shutter, camera motion, compression, blur, aliasing and lighting can affect measurements. No metric calibration, audio recovery, biological inference or diagnosis. This is not motion-amplified video output.

Reproduce: python examples/make_motion_demo.py /absolute/path/to/media/motion.avi. The fixture generates a textured pattern translated horizontally by 0.4 pixels at 3 Hz for four seconds at 24 fps. Tests check estimates, reference cancellation, invalid samples, and actual decoding. Synthetic checks do not establish real-world accuracy. See [tests](../tests/test_motion.py).
