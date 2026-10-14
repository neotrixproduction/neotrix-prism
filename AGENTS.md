# Current iteration workflow

The user accepted the visuals and animations and explicitly authorized a functional
audit and testing on 2026-10-13.

- Functionality audits and tests are now authorized. Preserve Claude's accepted visuals, artwork, layout and animation implementation exactly; restrict fixes to functional logic.
- Do not rebuild or publish a package unless requested. Earlier rapid-iteration test deferral has been superseded by the explicit audit request.
- Dark mode is the only application appearance. Keep Manrope, gradients, rounded surfaces and motion.
- Follow the user's CleanMyMac references closely: darker page backgrounds, brighter colorful translucent panels, large artwork, minimal text and details on hover/focus. Projects and stages use a bento grid with consistent gutters.
- Keep glyphs at native size during motion; animate artwork, opacity and pixel-aligned translation instead of scaling text.
- The user requires image generation for redesigned icon artwork. Projects, files, versions and default artwork are generated PNGs in assets/ui-icons; preserve custom project artwork and application identities. Do not substitute hand-drawn SVGs for requested icon replacements.
- Sidebar navigation uses a separate monochrome pearl-white generated set in assets/nav-icons at 24 px; keep colorful asset artwork separate. Keep the sidebar brand small and on one line, and do not show a Relay connection label.
- Existing tests and release validation describe earlier behavior until final validation updates them.

## Refresh animation handoff

- Before changing refresh motion, read [docs/REFRESH_ANIMATION.md](docs/REFRESH_ANIMATION.md). It describes all renderers, curves, timing, revision instructions and deferred validation.
- All interactive motion runs on retargetable springs (`neotrix_prism/physics.py`, `motion.spring`) and the layers in `neotrix_prism/choreo.py`. Do not reintroduce fixed-duration tweens for hover, scroll, selection or navigation.
- Idle colour and floating 3D artwork are wanted; drive them from `ambient.time` (`neotrix_prism/ambient.py`) so they pause when the app is hidden, inactive, unused or in reduced motion. Keep per-frame work small: cache layers, and only move artwork every frame.
- Project artwork is chosen by `themed_artwork` from `assets/project-art`; per-project `_TOOLS/icon` art still has priority. Card colours derive from artwork (`art3d.card_palette`); do not hard-code card palettes.
- Every current page needs a visible refresh response. Home and its decorative panel have been removed; Projects is the opening page.
- Opening a project shows Assets | Versions/Working files | Preview, in that order. Assets is grouped client material plus the authoritative brief; production assets stay in Working files. Preview groups Full/per-shot and only shows MP4/MOV. Reuse existing GridCards/ZoomThrough/ambient responses at every level; no separate animation or visual system.
- Keep the handoff note updated when revising this animation.

## Interface sound

- The user asked on 2026-10-13 for soothing, engaging and immersive sound for every animation and click; it must feel premium. Read [docs/SOUND.md](docs/SOUND.md) before changing sound.
- Cues are synthesized by `scripts/build_sounds.py` into `assets/sounds`: 48 kHz stereo WAV in one key (E-flat major pentatonic) and one shared synthetic room. Regenerate them with that script instead of hand-editing or adding outside samples.
- Each new animation or interaction gets a cue through `self.sound` (`neotrix_prism/sound.py`), timed to the motion's key moment. Pan positional cues by window x; keep hover cues quiet and rate-limited.
- Sound must never stall the UI thread (push-mode voice pool) and stays silent when muted, offscreen or under pytest (`NEOTRIX_SOUND` overrides).
