# Shared file comments

In Prism, select a working file and choose **Read / write comments** in the
details panel. Refresh fetches comments from other workstations. Each saved
file/version has its own discussion. Comments do not change the creative document.

All hosts share `<full filename>.neotrix/comments/<UUID>.json`, including existing
Blender Neotrix System comments. R: and its UNC alias naturally access the same
sidecar on the server. There is no Relay-root restriction. Keep the sidecar folder
with the document when copying, moving or archiving it.

Schema 1 requires string fields `id`, `author`, `text`, `created` (ISO 8601 UTC),
and integer `schema: 1`. `application` is optional. Each append writes a new UUID
record to a temporary file, then atomically renames it to `.json`. Never rewrite
the whole discussion; concurrent artists can append independently. Readers ignore
pending files and report malformed JSON records without hiding valid comments.

Python hosts can import `neotrix_prism.comments.load_comments(filepath)` and
`add_comment(filepath, author, message, application)`. Other apps can use:

```powershell
runtime\python.exe -m neotrix_prism.comments "N:\Project\shot.comp"
runtime\python.exe -m neotrix_prism.comments "N:\Project\shot.comp" --author "Artist" --message "Ready for review" --application "Fusion"
runtime\pythonw.exe launch.py --comments "N:\Project\shot.comp" --comment-app "Fusion"
```

The AE panel opens the current saved project's discussion. The Blender Prism
panel and Neotrix System read/write the same format. Fusion's **Script > Comp >
Neotrix File Comments** opens the saved `.comp` discussion. Resolve's unsaved
timeline compositions need a saved `.comp` export for file-based discussion.

This protocol reads Neotrix comments from every file type; it does not extract
arbitrary native AE markers, Fusion node notes, or unrelated embedded metadata.
Windows Explorer Properties integration is a separate property-handler extension
and is not installed by this change.
