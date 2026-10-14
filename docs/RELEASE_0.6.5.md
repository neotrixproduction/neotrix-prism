# Neotrix Prism 0.6.5

Stable portable Windows release, 14 October 2026.

## Improvements

- Native grayscale FreeType text rendering with bundled Manrope, clearer input
  weights and brighter search placeholders; artwork, layout and motion preserved.
- Separate work-area cards, expanded AI-file browsing and shared file comments.
- Spring-based refresh responses and immersive interface sound.
- Per-user favorites with concurrent-save protection, backups and restoration.
- GitHub updates with checksum verification, cancellation, install on close,
  restart and rollback after a failed replacement or runtime self-test.

## Install

Extract the entire Windows ZIP and run **Neotrix Prism.exe**. Python, Qt, fonts,
assets and application integration packages are included. Use 64-bit Windows
10 or 11. Production storage and creative applications are configured in Settings.

The 0.6.0 preview predates the updater. Install 0.6.5 manually once; use
Settings → App updates for future releases. Development checkouts support update
checks but deliberately disable automatic installation to preserve local edits.

The ZIP's matching .sha256 file verifies download integrity. The release is not
code-signed. Creative applications and Relay credentials are not included.

## Validation

96 automated tests passed, including Windows replacement and failed-runtime
rollback. Native typography was inspected at 100%, 150% and 200% scaling.
Full-package runtime and live GitHub update results are recorded in release notes.
