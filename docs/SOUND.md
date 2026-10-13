# Interface sound

Updated 2026-10-13. Read this before changing any sound. Sound is part of the
motion system: every cue is timed to the animation it accompanies (see
[REFRESH_ANIMATION.md](REFRESH_ANIMATION.md)).

## Direction

The user asked for soothing, engaging and immersive sound for each animation
and click that must feel premium. The resulting rules:

- **One instrument family, one key, one room.**
  - Instruments: glass, kalimba, soft wood, felt and air.
  - Key: every note is in E-flat major pentatonic, so overlapping cues (a wave
    of plucks under a chime) stay consonant.
  - Room: every cue passes through the same synthetic space, so the set sounds
    like it lives in one place.
- **Sound follows motion.**
  - Whooshes accelerate with page exits.
  - The zoom's air peaks as the artwork flies through the camera.
  - The refresh ring widens in stereo as the shockwave spreads.
  - Each artwork plucks when the wave lifts it.
- **Space is information.** Cues are panned by where things are on screen. The
  card grid plays like a keyboard: low notes on the left, high notes on the right.
  Hovering across cards plays a soft melody.
- **Quiet by default.**
  - Hover cues sit about 10 dB under clicks.
  - Every family is rate-limited, so fast pointer sweeps, typing and key repeat
    never chatter.
  - Errors are two calm wooden notes, never a buzzer.
- **Never in the way.** Triggering a cue costs about 0.15 ms on the UI thread.
  Sound is off when muted, when no audio device is present, offscreen and under
  pytest.

## Cue map

| Interaction | Cue | Timing and placement |
| --- | --- | --- |
| App opens | `intro` | Pad rises with the first-light dawn; arpeggio as nav items pop (220–430 ms, left); chord as the orb lands (~700 ms) |
| Page change | `nav-whoosh-down` / `-up`, then `nav-<page>` | Whoosh at once (direction follows the nav order, panned from the sidebar to centre); the page's own interval 90 ms later, as the cascade starts |
| Open a card (project, section, version, stage) | `open-left`, `open-center` or `open-right` | Air rises from the card's side to centre and peaks at ~0.42 s (fly-through); a whomp as the colour field lands; a strummed bloom |
| Back up a level (button, breadcrumb, Alt+Left) | `back` | Fast falling exit, then a low settle as content cascades down |
| Refresh (orb or F5) | `refresh`, then `wave-0…6`, then `done` | Deep boom falling into E-flat 2 with a sub octave, a low fifth under the light swell, and a widening air ring with the shockwave. Reverb is a touch wetter, with bass kept out of the reverb send (140 Hz) so the low end stays tight. Each artwork plucks at its wave arrival + 95 ms launch, pitched by x (list rows climb the scale). At most 8 plucks, fading. `done` resolves when the task ends, never sooner than 1.1 s. It is a soft settle: a breath of air sinking under a warm felt fifth, bell-free, at -31 LUFS. It replaced a bright rising chime the user found annoying |
| Cancel a task | `cancel` | Two wooden notes stepping down |
| Pointer meets a card | `hover-0…4` | Glass whisper pitched and panned by the card's x (gap 70 ms) |
| Pointer meets a row or button | `hover-soft` | Air tick (gap 55 ms) |
| Press a button | `press-0…2` | Warm wooden tock, rotating through three variants (the orb is exempt) |
| Press a card | `press-card` | Deeper tock under the zoom |
| Select a row | `select` | Glass tick |
| Search or filter changes the results | `shuffle` | Handful of tiny glass ticks with the FLIP reflow (gap 160 ms) |
| Sidebar | `sidebar-open` / `-close` | Warm two-voice glide a fifth apart (up to open, down to close), like a felt-lined drawer. A whisper of air rides along, a soft detent lands with the panel (~0.2 s), and the sound pans with the sidebar's edge. It replaced a noise swish the user found cheap |
| Open a file in its app | `launch` | Short rise and bright arpeggio |
| Copy path | `copy` | Glass blip |
| Favorite / unfavorite | `favorite-add` / `-remove` | Rising sparkle / soft falling pair |
| Stage assigned, settings saved | `success` | Rolled triad |
| Error message | `alert` | Two soft wooden notes |
| Dialog, menu, combo list | `dialog`, `menu` | Soft swell, small pop |
| Checkbox in Settings | `toggle-on` / `-off` | Wood tick bending up / down |

## Implementation

| File | Responsibility |
| --- | --- |
| `scripts/build_sounds.py` | Synthesizes every cue from scratch: additive glass, kalimba, wood and felt tones, STFT-shaped air, and one synthetic room (RT60 ~1.15 s, highs decay faster). Output is 48 kHz stereo 16-bit WAV. Each cue is normalised to a role loudness (BS.1770 K-weighting, 150 ms window) with a -3 dBFS ceiling, and tails are trimmed 50 dB under the peak. Writes `assets/sounds/SOURCE.json`. Development only (numpy/scipy); the runtime just reads WAVs. |
| `neotrix_prism/sound.py`, `SoundEngine` | Loads the WAVs into memory. Plays through a pool of push-mode `QAudioSink` voices: a cue is written whole into a free voice's ring buffer, so no stream opens during animation. The pool warms 10 voices one every 220 ms from 2.5 s after launch and grows to 14 if needed. Idle voices suspend 2.5 s after the last cue, and resuming costs ~0.4 ms. Light accents (hover, wave, select, press, menu, shuffle) skip rather than open a stream mid-frame. Also handles rate limits (`GAPS`), positional families (`at`), the refresh wave (`wave`) and default-output changes. |
| `sound.wire` / `eventFilter` | Press and hover for every `QAbstractButton`, plus a pop for menus and combo popups. `silent_press = True` exempts a button. |
| `cards.CardSurface.hovered/pressed`, `FileList.hovered` | Pointer signals that drive card and row sounds. Visual behaviour is unchanged. |
| `ui.MainWindow` | Semantic cues: `navigate`, `zoom_into`, `browse_projects`, `breadcrumb_clicked`, `refresh` and `wave_arrivals`, `finished_job`, `cancel_jobs`, `search_projects`, `filter_files`, `toggle_sidebar`, file actions, favorites, `error`, dialogs and the Settings controls (`sound_changed`). |
| `storage.Settings` | `sound` (on), `sound_hover` (on), `sound_volume` (70, logarithmic slider, validated 0–100). Settings apply immediately. |

Environment override `NEOTRIX_SOUND`:

| Value | Effect |
| --- | --- |
| `0` | Off |
| `1` | Force on, even offscreen |
| `mute` | The full audio path at zero volume, for timing tests |
| `log` | Emit `played` without audio, for recording |

## Changing the sound

1. Edit the builder or target loudness in `scripts/build_sounds.py`. Then run
   `python scripts/build_sounds.py --sheet sheet.png` with a Python that has
   numpy, scipy and matplotlib, and review the sheet's envelopes and spectra.
   Keep new notes in E-flat major pentatonic and use the shared room.
2. A new interaction gets a cue named by role. Call `self.sound.play(name)`
   (or `at(family, x)` for positional cues) where the animation starts, with
   a delay that lands on the motion's key moment. Add it to the cue map above.
3. Keep hover-type cues at -35 LUFS or quieter, and add a rate limit for anything a
   user can repeat quickly.
4. Verify:
   - `tests/test_sound.py` checks every cue file, the format, rate limits, positions, the refresh wave and settings.
   - For timing, drive the window with `NEOTRIX_SOUND=mute` or `log`, record frames and the `played` log, and mix them into a preview video.
   - Listen on real speakers and headphones at the default 70% volume.

## Verified 2026-10-13

- Full suite: 66 passed, including the sound tests.
- Driven offscreen with the real audio path at zero volume, every interaction above
  fired its cue at the expected moment:
  - the intro at launch
  - the nav chime 90–100 ms after the whoosh
  - refresh plucks fanning out from the centre column
  - `done` about 1.1 s after the refresh
  - silence when sound is off
- `play()` costs a median of 0.15 ms, with a worst case of 1.7 ms, on the UI thread.
- A 30-second preview video with the mixed soundtrack was produced from a scripted tour.
- Not yet done: listening review on the user's speakers and headphones, and the
  portable package rebuild (`assets/sounds` adds about 10 MB).
