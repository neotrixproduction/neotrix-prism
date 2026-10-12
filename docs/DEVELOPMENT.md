# Development

Use Python 3.13 on Windows for the packaged runtime. Install
requirements-neotrix.txt and pytest into a development environment. Python 3.11
also runs the service/UI tests; the Blender integration targets host Python 3.13.

    python -m pytest tests -q
    python launch.py

The portable runtime is built from Python's official Windows embeddable
distribution plus pinned binary wheels. runtime/python313._pth includes Lib,
win32, win32/lib and pywin32_system32. Keep the DLL search-directory handles alive
for pywin32. Never commit runtime binaries or machine-specific preferences.

    python scripts/build_integrations.py integration-packages
    python scripts/build_windows.py

The build copies the pinned upstream source, Neotrix modules, runtime, integration
sources, licenses and guides. Runtime dependency licenses are collected from
their wheel metadata. Verify the resulting SHA-256 and launch from a different
directory before publishing.

Modules:

- indexer: filesystem-only parsing, exclusion rules and local cache.
- versions: cooperative SMB reservations and callback-based in-memory saves.
- project_metadata: shared stage labels, relative paths, locks and conflict checks.
- storage: local preferences, atomic JSON documents and exclusive locks.
- integration/bridge: upstream adapters, separate GUI entry points and whitelisted
  localhost Adobe commands.
- ui/project_browser/design: Qt workspace, uniform cards, native file rows and visual tokens.

Keep the upstream projectBrowser API unchanged for production tools. Neotrix
entry points use core.neotrixBrowser instead. This prevents SDK callers expecting
the native browser's fields and selection API from breaking.
