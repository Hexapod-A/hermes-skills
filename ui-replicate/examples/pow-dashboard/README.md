# Example: pow-platform dashboard check

The verify loop run against the live build on Oct 18 2026. The Dribbble reference image is not stored in this repo (it is the designer's work); fetch it again with step 1.

```bash
S=ui-replicate/scripts; PY=.venv/bin/python
$PY $S/fetch_ref.py https://dribbble.com/shots/23956256-E-learning-Platform-Learning-Plan-Dashboard --out /tmp/uir --name dash
#   read page via r.jina.ai
#   /tmp/uir/dash-1.png 3228x2638
# the shot is the dashboard on a non-flat backdrop, so --trim keeps it; the frame box was read
# off grid_overlay.py and cropped by hand:
$PY $S/prep_ref.py /tmp/uir/dash-1.png --crop 197,181,3037,2178 --out /tmp/uir/ref_1440.png
#   viewport: --width 1440 --height 1013
bash $S/verify.sh /tmp/uir/ref_1440.png \
  "https://pow-platform.vercel.app/auth/demo?as=tunde%40demo.proofofwork.school&next=%2Fdashboard" \
  /tmp/uir/check --name dashboard
```

Output of the run (`report.json` in this folder is the full report):

```
ssim 0.7525 | layout 0.8489 | colour 95.0/100 | pixels differ 12.9%
worst tiles (x0,y0,x1,y1 in ref px):
  r4c6   [1200, 759, 1440, 1013]  ssim 0.604  dE 14.7
  r4c5   [960, 759, 1200, 1013]  ssim 0.664  dE 12.7
  r4c3   [480, 759, 720, 1013]  ssim 0.629  dE 9.1
  r3c2   [240, 506, 480, 759]  ssim 0.672  dE 8.4
  r3c6   [1200, 506, 1440, 759]  ssim 0.677  dE 5.0
PASS
```

`palette.py ref --compare build` on the same pair flagged the page background (`#f8f8f7` in the ref, `#ffffff` in the build, ΔE 2.5, ok) and a grey text tone (`#8a8188` vs `#757271`, ΔE 8.4, OFF).

The demo-login URL signs in as a fixed demo student so the data is the same on every run.
