# Neotrix GitHub updates

Version 0.6.5 includes **Settings → App updates**. Portable builds
check the public `neotrixproduction/neotrix-prism` releases quietly after startup;
an available update is announced in the workspace status. Checks never install
anything automatically. Settings also provides a manual Check for updates action.
Published preview releases are included; drafts, older versions and releases
without the Windows ZIP and matching checksum are skipped.

Download update runs in a worker, supports cancellation, and verifies the ZIP's
SHA-256 before extracting beside the installation. Downloads use GitHub HTTPS
without account tokens. Archive paths, duplicate names, symlinks, expanded size,
product identity, platform, required runtime files and version are validated.
The checksum detects download corruption; releases are not code-signed.

When verification finishes, choose:

- **Update & restart:** close Prism, install the update and restart it.
- **Install on close:** keep working; install when Prism is closed, then reopen
  it manually. A verified download remains staged if you haven't chosen either.

Current scans/saves must finish or be cancelled before scheduling installation.
A helper outside the app waits for both the app and executable launcher to exit.
It replaces the folder at the same path, preserving shortcut targets and integration
root references, and runs the new package's runtime self-test before commit.
The previous folder is retained beside it as `*.previous-*`. A replacement or
runtime-check failure restores the old folder when possible and records the error
under `%LOCALAPPDATA%/NeotrixPrism/updates` for the next launch. Failure to restart
does not delete the installed package.

Preferences, history and caches remain in the user's local data directory.
Relay projects, their icons, shared labels and comments are not update targets.
Installed creative-application panels outside the app are not automatically
reinstalled; use Install Integrations if a release changes those panels.
Close applications using the portable app's runtime if Windows reports locked files;
the updater never force-closes creative applications.

## Packaging and development

New portable builds contain `portable.json` with product `Neotrix.Prism`, platform
`windows-x64` and the app version. The build script includes the replacement
helper, and the launcher passes its PID to the app. Each GitHub release must attach
`Neotrix-Prism-<version>-Windows.zip` and
`Neotrix-Prism-<version>-Windows.sha256`; publish a new version for each update.

The installer is disabled in a source checkout or an older package without the
portable manifest. It requires a writable installation parent and uses staging
on the same volume. This protects local development edits and allows folder swaps.
The published 0.6.0 GitHub ZIP predates this updater. Download and extract the
0.6.5 release manually once; subsequent releases can use the in-app updater.

Validated with mocked downloads/checksums, cancellation and hostile archive paths;
real Windows helper tests cover successful replacement and failed-runtime rollback
in temporary folders. The public GitHub release listing was also checked live.
Live validation against the published 0.6.5 ZIP passed on 14 October 2026 for
both Update & restart and Install on close. The update-enabled 0.6.0 development
baseline discovered and downloaded the public release, verified its SHA-256,
installed the complete runtime, passed the executable self-test and preserved
preferences, favorites, storage roots and project files. Restart reopened 0.6.5;
Install on close did not reopen it. Previous installations remained available
for rollback, and 0.6.5 correctly reported up to date. No updater repair was needed.
See [the validation record](UPDATE_VALIDATION_0.6.5.json). The original published
0.6.0 preview was not this baseline and still requires manual installation.
