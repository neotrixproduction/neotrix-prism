# Functional audit — 2026-10-13

**Later follow-up:** the new project entry choices (Versions / Working files,
Assets, Preview) passed the expanded **52-test suite**, the bundled runtime smoke,
and their dedicated navigation tests at 150% and 200%. The original audit below
describes the earlier 49-test revision. The new level reuses the accepted visual
and animation components; see [SETUP.md](SETUP.md) for its flow.

## Result

The current source passed **49 automated tests**. All **16 UI tests** also
passed separately at 150% and 200% display scaling. The default-scale run
covered the same UI tests at 100%.

The audit preserved Claude's accepted visuals and animation implementation.
No artwork, palette, typography, geometry, motion curves or choreography was
changed. A SHA-256 baseline was captured before testing for all assets and
visual/animation modules. The only change in `ui.py` was the functional refresh
routing condition described below; reversing that one condition produces the
original baseline hash exactly.

## Functional fixes

| Issue reproduced by a regression test | Fix |
| --- | --- |
| Refresh at the project library reopened the previously selected project. | Rescan the selected project only when its work panel is visible; otherwise refresh the library. |
| Valid JSON with malformed preference types could crash startup. | Recover supported preference fields to their defaults while preserving valid settings. |
| Malformed shared stage documents could raise uncaught AttributeError or TypeError. | Validate the document and stage value types and raise an actionable ValueError through the existing error path. |
| Malformed activity records could crash Activity. | Ignore records with invalid shape, timestamps or path/application/stage field types; retain valid records. |
| Adobe bridge requests containing a JSON array or null dropped the connection. | Return HTTP 400 for non-object commands; retain the existing command whitelist. |

Fixes are confined to `storage.py`, `project_metadata.py`, `bridge.py` and the
single refresh-routing condition in `ui.py`. Visual and animation source files
and all assets match their pre-audit hashes.

## Automated coverage

- Mixed creative formats, deep folders, exclusions, outputs, cache use,
  cancellation and inaccessible storage notices.
- Project → named version → stage → files navigation, General alongside named
  variants, breadcrumbs, search, application filters and keyboard activation.
- Single and bulk stage assignments, inferred stages, read-only/offline labels,
  shared locking, stale-edit rejection and stage inheritance.
- Favorites, file launching, Open With, Reveal Folder, Copy Path and activity
  target opening. Launch arguments are kept separate and use `shell=False`.
- All-page Refresh availability, Settings-only Prism tools, worker cancellation,
  fixed action-button position, window controls and interrupted navigation.
- Version families, padding/case, unsaved document data, never-saved documents,
  cancellation, application failure, active-document changes and collisions
  introduced after the save preview.
- Corrupt preferences, malformed stage documents, invalid activity records and
  Adobe bridge validation.

Earlier tests still expected Home, tables, old sidebar widths and a template-only
artwork fallback. They were updated to the approved current UI without changing
the application to satisfy obsolete expectations. Tests wait for spring
settlement rather than assuming a fixed transition duration. A historical graph
offline test now simulates an unreachable root instead of depending on Windows
allowing an immediate directory rename while a scanner may hold it open.

## Real application and runtime checks

| Application / subsystem | Observed result |
| --- | --- |
| Blender 5.2.1 LTS | Saved unsaved scene edits through the adapter, reopened the new .blend, verified the edit and inherited stage. |
| Photoshop 2026, 27.6.0 | Saved an unsaved layer through the adapter, reopened the new .psd and verified the layer and inherited stage. |
| After Effects 2026 | Installed Neotrix CEP transport saved unsaved composition edits, reopened the new .aep and verified its layers and inherited stage. |
| Illustrator 2026, 30.3.0 | Created a dedicated .ai fixture, opened it through the launch service and verified the active document path. |
| Standalone Fusion 21 | Opened a valid dedicated .comp and verified the corresponding native window title. |
| Prism managed projects | Native managed browser initialized; managed Blender version save retained the upstream save workflow and reopened with its scene edit. |
| Bundled Python 3.13.7 runtime | Launched the current source from outside the repository, browsed a fixture project, selected a stage, refreshed every page and closed without captured errors. |
| Actual Relay SMB share | Two independent processes competed for a version reservation; exactly one succeeded. Shared stage locking and stale-edit rejection also passed. |

Host and Relay smoke-test results are stored locally in ignored `artifacts/`.
Dedicated QA documents were used for host writes. Relay writes were confined to
the separate `_NEOTRIX_PRISM/QA` area. Production documents were not used as save
targets.

## Reproduction

From the repository, using the existing development environment:

```powershell
.\.build-env\Scripts\python.exe -m pytest tests -q --tb=short
$env:QT_SCALE_FACTOR='1.5'
.\.build-env\Scripts\python.exe -m pytest tests/test_ui.py -q --tb=short
$env:QT_SCALE_FACTOR='2'
.\.build-env\Scripts\python.exe -m pytest tests/test_ui.py -q --tb=short
Remove-Item Env:QT_SCALE_FACTOR
.\runtime\python.exe scripts/functional_runtime_smoke.py
```

Host smoke scripts live under `scripts/`; inspect their test-file paths before
running them. The new runtime smoke creates its project and preferences in a
temporary directory.

## Practical limits

- Relay concurrency was exercised by two processes on **one workstation**. A
  physical two-workstation test remains outstanding.
- Host tests establish the listed save/open behavior. They do not certify every
  Adobe panel command, native Prism render/export operation, or application version.
- This audit applies to the current source and existing bundled runtime. No new
  portable package was built, published or installed, so the earlier public ZIP
  does not include these latest source changes.
- The visual design was preserved, not redesigned or given a new aesthetic review.
