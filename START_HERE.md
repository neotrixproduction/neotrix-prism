# Neotrix Prism — another Windows PC

1. Extract the **whole ZIP** to a stable local folder, such as Documents/Neotrix Prism.
2. Double-click **Neotrix Prism.exe**. Keep the runtime, assets and other folders beside it.
3. Open Settings and check storage roots and application executable paths.
4. Optionally run **Create Desktop Shortcut.cmd** for a shortcut with the app icon.

## Installation requirements

The explorer is portable: no Python, Qt or font installation, no administrator
installation step, and no Blender requirement for browsing. Python 3.13, Qt,
Manrope and runtime DLLs are included.

Use **64-bit Windows 10 or 11**. The small executable launcher uses the .NET
Framework supplied with these Windows versions. The CMD launcher and runtime
remain in the package; this is a folder-based portable application, not a single
standalone executable. Run it after extraction, not from inside the ZIP.

Creative applications must be installed separately to open their documents.
Settings detects common installations; change a path when an application is
installed somewhere else. Video previews open with the PC's associated player.

The default project share is `\\NeoVault\Relay`. The new PC needs network/VPN
access and the user's own share permissions. Mapping R: or N: is not required
for this UNC root. Additional project roots can be added in Settings. Credentials
and another workstation's personal preferences are not included in the package.

Preferences, history and caches are per user in `%LOCALAPPDATA%\NeotrixPrism`.
Cached browsing becomes available after that PC has indexed a project. New saves
and shared stage edits require writable connected project storage.

## Optional application panels

Run **Install Integrations.cmd** only if you want the Neotrix panels inside
Blender, Photoshop or After Effects. Standalone browsing/opening does not require
this step. See `docs/SETUP.md` for installation, panel limitations and enabling
the Blender add-on. Integration installation points to this extracted folder;
if you move it afterward, rerun the integration installer and shortcut creator.

The preview executable is unsigned. Windows may show its usual downloaded-app
reputation prompt; this package is not code-signed or a Microsoft Store installer.

This package was checked on the development workstation from a separate extracted
location. A clean physical second-PC check remains part of deployment validation.
