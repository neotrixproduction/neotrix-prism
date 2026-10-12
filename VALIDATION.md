# Validation — Neotrix Prism 0.2.0 preview

## Verified on this workstation

- Service, save-wrapper and native Qt interaction tests: 18 passing.
- Blender 5.2.1: save active in-memory edits through the upstream adapter,
  reopen the new .blend, and verify the edited object.
- Photoshop 2026 (27.6): create a dedicated test document, add an unsaved layer,
  save through the upstream adapter, reopen, and verify that layer.
- After Effects 2026: install/open the separate CEP panel, connect through its
  isolated transport, save unsaved composition edits, reopen the new .aep, and
  verify the added layer.
- Illustrator 2026: create a valid test .ai, launch through the explorer's file
  opening service, and verify the active document path.
- Fusion 21: launch a valid minimal .comp through the file opening service and
  verify that the Fusion window displays that composition.
- Upstream managed-project creation and native managed browser initialization.
- A managed Blender asset save retained Prism's native version/metadata workflow;
  the saved scene reopened with its in-memory edit intact.
- Desktop screenshots at measured device pixel ratios 1.0, 1.5 and 2.0, plus
  dark theme and reduced motion. Screenshots use fictional indexing fixtures;
  these are not executable creative documents.
- Two independent processes over the actual SMB share: one version reservation
  succeeded, the competing reservation was blocked. Shared graph stale-write
  detection also passed.

## 0.1.1 visual revision

- All 18 existing automated service, integration and UI tests pass.
- Replaced flat surfaces with static vector gradients, luminous tiles, shaded
  original icons, an original prism mark and layered workspace artwork.
- Native desktop captures cover all six pages at 100%, 150% and 200%, light/dark,
  reduced motion and the 1024 x 720 minimum window.
- Static gradients have no refresh timer; SVG icons are cached and supersampled.
- Adobe panel CSS and integration packages were updated. This revision's live
  AE panel refresh was blocked by a pre-existing host save prompt; updated AE
  panel rendering and Photoshop UXP rendering require host verification.
## 0.1.2 full-color background

- Removed pale/white shell surfaces. Both appearances use purple/indigo
  backgrounds with white text, tinted tables, forms, sidebar and workflow nodes.
- Shared Qt palette and native Prism dialog colors match the desktop tokens,
  including placeholders and disabled text.
- All 18 tests pass. Native captures cover all six desktop pages at 100%, 150%
  and 200%, both appearances, reduced motion and the minimum window size.

## 0.2.0 animation and rounded window

- 24 automated tests pass, including interrupted page transitions, sidebar
  collapse/expand, maximize/restore masks, caption dragging, resize constraints,
  circular worker cancellation and reduced-motion behavior.
- Live Windows QA verified pointer caption drag (position changed by 80 x 40),
  right-edge resize (1280 to 1224 px), maximize and restore.
- Bundled Manrope resolves to the expected actual font family for headings,
  body and controls, following the user's final typography choice.
- Real Qt interaction frames were recorded for the motion preview. QA task
  progress is explicitly labeled as a fixture. No production files are modified.
- Desktop static captures cover all six pages, both appearances, 100%, 150% and
  200%, reduced motion and the minimum window size.
- Adobe panel animation sources were updated; live host rendering is pending.

## 0.3.0 choreographed motion

- 25 automated tests pass. New coverage checks actual home tile navigation,
  repeated scene interruption and reduced motion enabled during a transition.
- Original Manrope typography, rounded window and creative-file services remain.
- All six desktop pages were captured in both appearances at 100%, 150% and
  200%; minimum-window capture confirms wrapping and vertical scrolling. All
  nine UI tests also pass at 200% scaling.
- Motion recording uses real Qt widgets and labeled local QA tasks. No production
  files are opened or changed. A separate 16 ms event-loop probe records scheduling
  gaps without screenshot/encoding overhead; this is not a GPU frame-rate claim.
- The local probe recorded 16 ms median and 18 ms p95 scheduling gaps. Its
  maximum was 211 ms, including initial/navigation work; no 60 fps guarantee is
  inferred. The MP4 preserves original RGB captures and their timestamps,
  avoiding the GIF's limited gradient palette.
- Surface and icon motion is driven by interactions and finishes at rest. Only
  real task progress loops. Adobe CSS adds a finite sweep and perspective hover;
  this revision's live Adobe panel rendering remains pending.

## 0.3.1 fixed task-action position

- 26 tests pass. The action orb occupies a fixed center column with equally
  flexible side columns and a constant-height footer. Status text wraps;
  progress and Cancel controls cannot change the orb's anchor.
- The regression check compares the exact center coordinates before, during
  and after a canceled task, with long status text at 1360 x 900 and 1024 x 720.

## 0.4.0 card browsing and 3D app artwork

- 29 automated tests pass, including project-shelf pointer centering/opening,
  card keyboard activation, preserved filtering/actions, a virtualized 1,000-file
  gallery, end-of-list scrolling and reduced-motion interruption. The previous
  fixed Explore/Stop position checks remain in the suite.
- UI checks pass at 200% scaling. Desktop captures include the six navigation
  pages plus the project shelf, both appearances, 100/150/200% and minimum size.
- App icons were referenced from installed executables and generated individually
  with the built-in tool. All five PNGs preserve alpha; corner pixels are fully
  transparent. Their branding and thick body shapes were visually reviewed.
- High-DPI card pixmaps use the full physical source rectangle. Details previews
  fit the available logical height, including after window resizing.
- File preview decoding and icon caches remain bounded. No creative app is
  launched to create gallery thumbnails. Existing open/save services are retained.
- Advanced native Prism/DCC interfaces retain the host-validation limits below.

## Remaining host/environment checks

- A true two-workstation pilot has not been run. The SMB concurrency test used
  two processes on this workstation. Do not represent it as two workstations.
- Adobe Creative Cloud's UPI installer and UXP Developer Tool are unavailable
  here. The Photoshop UXP source and CCX package are prepared; UXP installation
  and docked-panel rendering remain unverified. A native Photoshop companion
  JSX launches the Qt workspace without requiring UXP.
- Desktop scaling coverage is complete. Native host panels have been inspected
  at this workstation's current scaling, not separately at all three scales.
- Advanced Prism tools retain their native layouts with the Neotrix theme;
  they are not a wholesale rewrite of every upstream production dialog.

## Reproduction

Install development dependencies and pytest, then run:

    python -m pytest tests -q

The scripts/ smoke checks create only dedicated QA files. They require the named
creative applications and should be run with no unrelated active AE project.
The portable runtime and test evidence live outside Git. User settings,
production files, installation paths and credentials are not release sources.
