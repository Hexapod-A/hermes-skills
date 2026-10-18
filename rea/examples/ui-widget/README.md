# Browser UI example (offline)

Run `python3 run_demo.py` (needs Node, Playwright, Chromium, Pillow). The original and replica
are local HTML files with different markup. The test maps their selectors, runs 8 action sequences
on 1440x900 and 390x844 viewports, and checks text, boxes, computed styles, attributes and
whole-page plus element screenshots. `?bug=1` changes one button's border radius.

Verified 2026-10-18: clean 16/16; buggy 0/16. The whole-page image threshold missed 8 of the
small radius differences; element shots and computed styles found all 16. No random cases were
run, so **99.9% is NOT substantiated**. Add more viewports and independent random action paths for
a production claim. Browser output may vary by platform, font and graphics stack.
