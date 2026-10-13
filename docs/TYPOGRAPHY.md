# Native text rendering

The standalone Windows launcher selects Qt's built-in FreeType font engine before
creating QApplication. Manrope remains the bundled UI font. Text uses grayscale
antialiasing and no hinting so translucent widgets and cached card labels composite
without RGB fringes. Input controls use weight 500 and an explicit #bfc2d8
placeholder color; layout, font sizes, artwork and motion are preserved.

An explicit QT_QPA_PLATFORM setting takes precedence. For a diagnostic comparison,
set it to windows:fontengine=directwrite before launching. Hosted panels retain
their application's existing font engine; they receive the typography settings
but cannot switch an already-created QApplication's platform.

This path does not depend on MacType injection or its security bypass options.

Validation on 2026-10-14: native Qt captures inspected at device pixel ratios
1.0, 1.5 and 2.0; UI and project-browser tests: 27 passed. Captures and font
resolution diagnostics are in artifacts/typography. The active standalone window
was gracefully restarted to load the renderer. No release package was rebuilt.
