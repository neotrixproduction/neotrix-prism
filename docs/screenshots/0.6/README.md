# Neotrix Prism 0.6 screenshots

Captured from the native Qt application on 2026-10-13 using isolated, fictional
projects and preferences. The logical window is 1360 × 900 at 150% display
scaling; PNGs retain their native 2040 × 1350 resolution. The accepted application
artwork, layout, styles and motion implementation were not modified for capture.

The files and activity entries are demonstration indexing fixtures, not usable
creative documents or evidence of application saves. No production files are
opened and no shared storage is modified.

To reproduce from a development environment with PySide6 installed, run:

```powershell
python scripts/capture_readme.py
```

The script creates a temporary library and preferences, waits for workers and
navigation transitions, clears hovered cards and captures the actual Qt window.
It does not change the user's preferences. Capture metadata is in `capture.json`.
The Settings screenshot shows the default Relay root; the demo uses local fixtures.

Included screens: project library, project overview, client assets, named
versions, production stages, working files, preview collections, favorites,
activity and settings. Earlier screenshots outside this folder are historical
and are no longer used by the repository's main README.
