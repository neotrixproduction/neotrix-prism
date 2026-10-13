# Motion system and refresh animation handoff

Updated 2026-10-13. This is the current source-level specification for desktop
motion, including Refresh. Read this before revising any motion. Older
descriptions in MOTION.md and existing screenshots can describe superseded UI.

## User direction and current status

- The user found the earlier motion rigid and asked for dynamic, motion-graphics
  quality choreography in the spirit of CleanMyMac, but beyond it.
- Every page must visibly animate when Refresh is clicked: Projects, Favorites,
  Activity and Settings. Home and its decorative panel have been removed.
- Keep text stationary or translating only, drawn at native display resolution
  and pixel-aligned. Animate artwork, opacity, light and translation; never
  scale glyphs or rasterize labels for an effect.
- Keep dark backgrounds, brighter colorful panels, Manrope and rounded surfaces.
- The bottom-center Refresh/Stop position is fixed across every page. Stop is
  shown during a real worker; completion must not cut short decorative motion.
- Refresh/Stop has translucent glass shading, white specular highlights and
  thin reflective rims. Its body, glow and progress ring read the live
  `Atmosphere.scene_colors()` palette, including page/stage transition colors.
  `Atmosphere.palette_changed` repaints the orb on palette and refresh-light
  changes. Do not restore a fixed pink tint or maintain a separate page-color map
  for the orb. Keep its label outside the transformed artwork paint region.
- Hover clipping fix: the 68 px glass body paints in a centered 112 × 112
  transparent canvas, with matching footer height. This reserves room for halo,
  spring overshoot and busy/focus rings; the label clip stays centered at 66 px.
  Do not shrink the canvas back to 84 px or clip it with a shorter footer.
  Body size, tint and motion curves are unchanged.
- Second round (same day): the user asked for idle colour-gradient animation,
  more waves of colour, more size change, more fluid motion, professional 3D
  project artwork that rotates and hovers in 3D, and readable contrast. They gave
  full creative authority with CleanMyMac as the reference to surpass.
- Idle motion is now intentional, but it must stay cheap and polite: it runs only
  while the window is visible, active and used in the last 75 s, eases to a stop
  otherwise, and is off under reduced motion.
- Status: exercised in scratch offscreen recordings of the real window (intro,
  idle drift, hover reflow, 3D turns, refresh, search reflow, project/stage zoom
  with colour floods, page waves, sidebar, reduced motion toggled mid-flight)
  with no exceptions. The repository test suite, QA captures and package rebuild
  were NOT run; they stay paused until the user says "done". Existing tests
  still describe older behavior (for example the old Favorites/Activity tables).

## Principles

1. Springs, not durations. `neotrix_prism/physics.py` solves a damped oscillator
   in closed form. Retargeting keeps velocity, so interrupted motion flows on
   instead of restarting from rest. Use `motion.spring(owner, key, target, update,
   value=…, feel=…)`; it honors reduced motion. Do not add new fixed-duration
   tweens for interactive state.
2. One clock for painters. Widgets that paint many items (grids, lists, layers)
   run a linear millisecond `motion.clock` and sample `physics.progress` or
   `physics.bounce` per item with its own delay. Linear clock time is not linear
   motion.
3. Exit fast, enter slow, overlap slightly. Departures use ~300 ms
   soft-focus dissolves; arrivals cascade in reading order.
4. Every gesture has a source. Refresh radiates from the orb; opening a card
   expands from that card and floods the workspace with its colour from there;
   choosing a page floods its colour from the sidebar item.
5. Alive but cheap. Idle animation reads `ambient.time`, which only advances
   while the app is in use. Expensive layers are cached and refreshed slowly;
   only artwork moves every frame. Measure before adding per-frame work.

## Motion vocabulary (`physics.py`)

| Token | Response, damping | Use |
| --- | --- | --- |
| `SNAPPY` | 0.28 s, 0.78 | Pointer feedback, hover-in |
| `POP` | 0.42 s, 0.52 | Artwork landing with a visible bounce |
| `FLUID` | 0.46 s, 0.82 | Entrances, shared elements |
| `GLIDE` | 0.36 s, 1.0 | Scrolling, layout; never overshoots |
| `SETTLE` | 0.9 s, 0.96 | Atmosphere and large color fields |
| `EXIT` | 0.2 s, 1.0 | Fast departures |

## Living surfaces and 3D artwork

| File / symbol | Responsibility |
| --- | --- |
| `ambient.py`, `Ambient` | Shared idle clock (30 fps). Advances `time` only while visible, active, motion enabled and input within 75 s; eases in/out over 1.6 s, then stops its timer. Widgets subscribe with a repaint divisor. |
| `surfaces.py`, `Atmosphere` | Aurora: dark scene gradient plus five drifting hue blobs, rendered at 1/6 size and cached as a device pixmap (rebuilt ~10 fps). `focus_scene(index or 3 colours, origin)` floods the new scene outward from `origin` with a luminous rim; without an origin it crossfades. `paint_backdrop` lets content dissolve into the field. |
| `art3d.py`, `paint` | Rendered 3D icons turned in true perspective (`QTransform.rotate` about Y/X) with extruded thickness, a specular sweep and a floating contact shadow. Small idle turns use a cheap affine path; sources are pre-scaled near screen size. |
| `art3d.py`, `card_palette` | Card gradient from an artwork's saturation-weighted dominant hue, darkened until white labels keep contrast. |
| `project_browser.py`, `GridCards` | Bento cards: hovered card widens while row-mates yield (`card_rects`), swells, lifts and glows in its hue; artwork floats and turns toward the pointer; card hues drift and a diagonal colour wave crosses the grid. Each card is a cached body layer (~5 fps), live artwork, and a cached label strip. FLIP reflow on search; entrance spins artwork in from edge-on. |
| `project_browser.py`, `themed_artwork` | Projects without their own `_TOOLS/icon` art (or with the template's copy) get artwork chosen by words in the folder name, else a stable generic pick. Custom art always wins. |
| `project_browser.py`, `ActivityList` | Activity as a timeline of glass rows with event artwork; shares row motion with the file list. |
| `project_metadata.py`, `STAGES` / `inferred_stage` | The template's shot stages (Modelling, Rigging, Layout, Animation, FX, Lighting, Compositing, Others) inferred from `SHOTS/<shot>/PROJECTS/<STAGE>`; Unassigned for loose saves in `PROJECTS`. The `other` key is kept for existing labels. |
| `ui.py`, `update_browser` / `filter_files` | An "All stages" card leads the stage grid; it lists every stage's working files newest first, each row prefixed by its stage folder (`FileDelegate`, `folder`/`stage_title`). Stage cards show the template description on hover. |
| `project_browser.py`, `GridCards.fit_rows` | The stage grid shrinks its rows (floor 188 px) so every stage is visible; the project grid keeps 264 px rows and scrolls. |
| `ui.py`, `project_scene` / `projects_scene` / `projects_title` | The Projects page takes the library, project-artwork or stage scene and title for its current level. |
| `motion.py`, `MotionButton.hop` / `OrbButton` | Selected nav icons turn a full revolution in 3D; the orb breathes and its iridescent rim slowly rotates. |

Artwork: `assets/project-art` (15 themes) and the refreshed stage, version,
favorites and activity icons were generated with Codex's built-in image tool;
prompts and post-processing are recorded in each folder's `SOURCE.json`.

Measured at 150% scaling, offscreen raster: an idle grid frame is about 7 ms
(it was 15 ms before layer caching); a full-window frame is about 17 ms worst
case, and happens at ~10 fps for the backdrop.

## Where the implementation lives

| File / symbol | Responsibility |
| --- | --- |
| `physics.py`, `animate` / `settle` / `bounce` | Spring driver on Qt's animation clock; stops when idle. `settle()` snaps everything (reduced motion). `bounce()` is the normalized refresh trajectory. |
| `motion.py`, `spring` / `clock` / `refresh_motion` | Reduced-motion-aware wrappers. `refresh_motion` returns offset, speed-based stretch/landing squash and tilt. |
| `motion.py`, `MotionButton` | Spring hover/press (jelly release), icon-only artwork drawn with float transforms, `hop()` selection jump, `intro()` drop-in, refresh bounce. |
| `motion.py`, `PageEffect` / `reveal_page` / `cascade` | Opacity + pixel-aligned rise per block. `cascade` opens plain containers and staggers blocks; grids and lists run their own `play_entrance`. `PageEffect` composites `sourcePixmap` because `drawSource` ignores painter opacity. |
| `motion.py`, `SceneTransition` | Sidebar page change: outgoing snapshot accelerates away along the sidebar direction through a soft-focus dissolve; no opaque underlay. Incoming page cascades live. |
| `motion.py`, `OrbButton` | Spring activity/press, rolling Refresh/Stop label swap, intro scale. |
| `choreo.py`, `KineticLabel` | Page title and status: per-glyph rise through the label edge with converging tracking; previous text lifts away. Rapid status updates (< 450 ms) swap instantly. |
| `choreo.py`, `Shockwave` | Refresh light: leading swell, crisp echo and wake radiating from the orb across the whole window; the same radial field lights card edges as it crosses them. `delay_for(point)` syncs artwork to the wave front. |
| `choreo.py`, `ZoomThrough` | Shared-element navigation from a project/version/stage card: color field opens to the page, artwork flies to center and through the camera, previous grid recedes into soft focus. |
| `cards.py`, `CardSurface` | Spring scrolling with momentum, fling velocity and rubber-band overscroll; per-card hover and press springs; pointer tilt. |
| `project_browser.py`, `GridCards` | Diagonal three-layer entrance (card, artwork pop, title), FLIP reflow on search, hover lift/specular/parallax, scroll inertia on artwork, radial refresh bounce. |
| `project_browser.py`, `FileList` / `FileDelegate` | Row cascade with icon pop, hover and selection springs, scene-tinted neutral glass rows, radial refresh bounce. |
| `surfaces.py`, `Atmosphere` | Direct scene crossfade (never through intermediate scenes), drifting glow anchor, intro "first light", refresh swell. |
| `surfaces.py`, `GradientTile` | Spring hover/pointer lighting; refresh swell and gloss timed to the wave front. |
| `ui.py`, `MainWindow.play_intro` | Opening sequence, run before the first paint. |
| `ui.py`, `move_selection` / `toggle_sidebar` | Selection rail with separate leading/trailing edge springs (stretches in flight); spring sidebar width. |
| `ui.py`, `zoom_into` / `browse_projects` / `breadcrumb_clicked` | Card zoom forward; going back up a level cascades content down from above. |
| `ui.py`, `refresh` | Fires the shockwave and dispatches distance-based delays to grids, lists, artwork, tiles and sidebar icons. |

## Refresh values

Displacement is positive downward; A is the item's amplitude.

- Trajectory (`physics.bounce`): 95 ms anticipation dip to +0.17 A, then a
  spring released upward (response 0.6 s, damping 0.4) whose launch speed is
  solved so the peak is exactly -A. It lands with an overshoot and settles in
  about 1.44 s (`BOUNCE_MS`). Stretch follows speed (max 9%); squash follows
  the dip and landing (max 8%); tilt follows speed (about 4°).
- Amplitudes: grid artwork 18 px, file icons 8 px, sidebar icons 7 px,
  standalone artwork min(24 px, 14% of height).
- Timing: every item starts when the wave front reaches its center:
  distance from the orb / 1650 px/s.
- Shockwave: rings 230/60/420 px wide at alpha 118/92/34, a 0.42 s core flash,
  hue taken from the current scene and lifted to near white, screen-blended.
- Background and tiles: an impulse into a critically damped spring gives a
  swell that peaks in about 0.25 s and ebbs over about 1.5 s.
- Panels ride the wave (added 2026-10-13 at the user's request: "panels also
  move dynamically", then "even more dynamic"). `physics.ripple` is an impulse
  into an under-damped spring (0.7 s, 0.34), normalised to an outward peak of
  1 at ~145 ms, a rebound of -0.32 at ~515 ms and a second swing of +0.10 at
  ~890 ms, settled by `RIPPLE_MS` (~1.8 s). `RIPPLE_SPEED` is its launch speed.
  Each panel starts when the front reaches its centre and is pushed away from
  the orb; nearer panels push harder (strength 1 down to 0.7 across the wave).
  - Cards (`GridCards.ripple_for`):
    - Push and lift: 22 px push plus 8 px lift, 5.5% shape swell, and up to 7% stretch along the travel while moving fast.
    - Light: hover-strength shadow and hue glow while lifted, and a sheen that crosses the glass with the front.
    - Layering and bounds: lifted cards paint above their neighbours. Each axis's travel is limited by the room to the widget edge, so cards are never cropped.
    - Artwork jumps 24 px, 95 ms after the card is struck, and is kept below the grid's top edge.
  - Rows (`row_ripple`): 10 px push (9 px for activity) plus 4 px lift, with
    brighter glass and edge, limited to the viewport so rows never crop.
  - Every other block on the page and the page title (`motion.RippleLayer`):
    when the front reaches a block, its snapshot is drawn on a layer over the
    whole workspace, pushed 10 px plus a 3 px lift. Moving widgets in place
    cropped them at their container's edge, so the user saw the Back button,
    search and filter fields clipped. The block itself is hidden
    (`HiddenEffect`) but stays in place and interactive; hit targets never
    move. Ghosts are clipped only by a scroll viewport they belong to, and
    the shockwave light stays above them. A block that is mid-reveal or
    inside a transition is left alone. Everything is restored when its ripple
    ends or a new refresh starts.
- Footer while work runs: `choreo.StatusLine` is one quiet line (12 px, about
  60% white) that elides in the middle, with the full text as its tooltip;
  scan progress reads "12,480 files found · SH010". `choreo.Hairline` replaces
  the progress bar: a 2 px scene-tinted comet gliding along a faint track,
  fading in and out on a spring and pausing when minimised. Cancel is a quiet
  text action (`quietAction`).
- Sound (see [SOUND.md](SOUND.md)):
  - At t=0, `refresh` plays a soft thump with the core flash and an air ring that widens in stereo with the wave.
  - Each artwork plucks (`wave-0…6`) at its wave delay + 95 ms (the launch), pitched and panned by its x position, at most 8 plucks, fading.
  - `done` resolves when the task ends, never before 1.1 s.
  - If animation timing changes, keep `sound.LAUNCH_MS` and `MainWindow.wave_arrivals` in step.

## Scrolling (lists and Settings)

Added 2026-10-14 after the user reported that long file lists "jump"; they
asked for smooth, premium scrolling with no harsh jumps or snaps. Qt's default
wheel scrolling moved a 90 px-row list 270 px per notch, instantly.

- `FileList` (files and activity) scrolls on a spring:
  - Wheel: each notch glides 120 px on GLIDE; quick notches (under 160 ms apart,
    same direction) gather speed up to 2.6x, and a glide in flight is
    retargeted, never restarted. Fine-grained wheels and touchpads follow on
    (0.24, 1.0).
  - Ends: the list runs up to 120 px past an end, shown through `cards.rubber`
    as growing resistance. 90 ms after the wheel stops, it springs home on
    (0.42, 0.86), a soft landing.
  - While gliding, rows trail behind the motion in proportion to their distance
    from the pointer (up to 14 px), and row artwork tips (up to 10°) and lags
    (5 px) with the speed. Glyphs only translate.
  - Keyboard and programmatic reveals (`scrollTo`) glide too. Trips longer than
    3.5 screens (End, Home) dissolve the current rows away in the direction of
    travel (`warp_ghost`), land 2.5 screens short and glide in at speed while
    the arriving rows fade up. They never streak past thousands of rows.
  - A thin overlay thumb fades in while moving (squashing at the ends) and
    fades out 0.7 s after rest. Rows dissolve into the backdrop at the top and
    bottom edges where the list continues.
  - When a rescan updates the same view (same order, at least 60% of rows
    kept), the list keeps its place: the top row stays put. A different view
    (filter, stage, sort) starts at its first row.
  - Hover follows rows passing under a resting pointer; hover sounds stay quiet
    while the list moves fast. Uniform row sizes keep thousands of rows cheap.
- `motion.SmoothWheel` gives any other scroll area (the Settings page) the same
  glide, without elastic ends.
- Reduced motion uses Qt's normal scrolling.

## How another agent should revise it

1. Read repo `AGENTS.md` and this note. Preserve the latest user direction.
2. Tune feel with the vocabulary tokens or per-call `feel=(response, damping)`;
   keep `bounce` as the single refresh trajectory for widgets and painters.
3. Keep artwork inside its bounds, including hover rotation, squash and
   overshoot. Never move hit targets with animated offsets.
4. Any new layer must be mouse-transparent, set `motion_layer = True` (so
   cascades and glints skip it) and hide itself when it settles.
5. Preserve reduced motion: `apply_theme` calls `physics.settle()`, stops clocks,
   removes `PageEffect`s and hides layers.
6. Update this note with changes.

## Deferred final review

Review Projects, named versions, stages, working files, Favorites, Activity and
Settings, including empty pages, on a real display at 100%, 150% and 200%.
Check frame pacing of the shockwave and zoom on large windows, repeated
refreshes, rapid navigation, slow/failed storage, cancellation and reduced
motion toggled during an effect. Verify that native text stays sharp and inputs
remain usable beneath layers. Rebuild the portable preview only after final
validation is authorized.
