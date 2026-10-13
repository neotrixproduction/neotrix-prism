# Neotrix GitHub updates

The development implementation adds **Settings → App updates**. Portable builds
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
The existing 0.6.0 GitHub ZIP predates this updater; these changes require a new
portable build and release before other PCs receive them.

Validated with mocked downloads/checksums, cancellation and hostile archive paths;
real Windows helper tests cover successful replacement and failed-runtime rollback
in temporary folders. The public GitHub release listing was also checked live.
A download/install/restart against a newly published full-runtime release remains
a release-validation step.
