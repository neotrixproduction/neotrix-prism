# Validation — Neotrix Prism 0.1.0 preview

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
