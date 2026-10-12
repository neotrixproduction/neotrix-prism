// Native Photoshop companion entry; fallback when Creative Cloud/UXP is absent.
// Uses the same Qt workspace and upstream COM adapter as the UXP panel.
app.system('start "" "NEOTRIXROOT/runtime/pythonw.exe" "NEOTRIXROOT/launch.py" --app Photoshop');
