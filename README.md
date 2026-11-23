# Lyrics PiP (Wayland)

**English** | [Bahasa Indonesia](README.id.md)

A small lyrics window that stays on top of other windows (like picture-in-picture) for the song playing in **YouTube Music in Firefox**. Lyrics are synced: the line being sung is highlighted and scrolled into view automatically.

This version is for **Pop!_OS 24.04 with the COSMIC desktop (Wayland)**. It is derived from `lyrics-app` (the XFCE/X11 version). It stays lightweight: Python + GTK3, no pip packages.

> The app's interface (buttons and messages) is in Indonesian. Button names are given below with an English translation.

### Differences from the X11 version

On Wayland, regular applications are not allowed to choose their own position, force themselves on top, or appear on every workspace. So the lyrics window is a **layer surface** (the `wlr-layer-shell` protocol, via `gtk-layer-shell`), the same mechanism the COSMIC panel uses:

- The window lives on the *overlay* layer: always above other windows (including fullscreen video) and visible on every workspace.
- Dragging and resizing are implemented by the app itself, because the compositor does not provide them for layer surfaces.
- Transparency is applied to the background and contents, because Wayland windows cannot be given an opacity.
- Wayland does not report the `Ctrl` key state to an unfocused window, so transparency can also be adjusted by scrolling over the title row.
- If `gtk-layer-shell` is not installed, the app still runs as a normal window (not always on top) and prints a warning in the terminal.

## How it works

- **Song detection:** reads MPRIS over D-Bus (`Gio`). Firefox reports the title, artist, duration, and playback position, so no browser extension or scraping is needed.
- **Lyrics:** fetched from [LRCLIB](https://lrclib.net) (free, no API key). If no timestamped lyrics exist, plain lyrics are shown without highlighting.
- **Cache:** results are stored in `~/.cache/lyrics-pip-wayland/`.

## Requirements

- Pop!_OS 24.04 / COSMIC (Wayland), or another Wayland compositor that supports `wlr-layer-shell` (sway, Hyprland, KDE)
- Python 3.12+ with PyGObject and GTK 3 (`python3-gi`, `gir1.2-gtk-3.0`)
- `gtk-layer-shell` for GTK3:

  ```bash
  sudo apt install gir1.2-gtklayershell-0.1
  ```
- Firefox playing YouTube Music

## Running

```bash
./lyrics-pip
```

Play a song in YouTube Music and its lyrics appear in the window.

## Controls

| Action | How |
|--------|-----|
| Move the window | drag anywhere |
| Move to another monitor | drag, then release with the pointer on the other monitor |
| Resize | drag an edge or corner |
| Adjust transparency | scroll over the title row (or `Ctrl` + scroll anywhere) |
| Close | the `×` button in the corner |

The window is always on top, visible on every workspace, never takes keyboard focus, and only one instance can run (launching it again while it is running does nothing).

## Settings

### Transparency
Scroll over the title row (the top of the window). `Ctrl` + scroll anywhere also works, but on Wayland only while the lyrics window has focus (for example during sync mode). Up = more opaque, down = more transparent, in 5% steps, within 0.3 to 1.0. The default is 0.92. The value is remembered for next time.

### Position and size
Drag the window from anywhere and resize it from an edge or corner. The window cannot leave its monitor. The values are saved when the window is closed (via `×`, `Ctrl+C`, or `kill`) to `~/.config/lyrics-pip-wayland/config.json`:

```json
{"x": 2140, "y": 60, "w": 380, "h": 300, "opacity": 0.92, "sync_offset": 0.3, "monitor": "H27G30Q"}
```

- `x`/`y` are measured from the top-left corner of the **monitor** the window is on (not the whole desktop), and `monitor` holds that monitor's model name.
- **Moving to another monitor:** drag the window toward the other monitor. While dragging, the window stops at the edge of its monitor. Release the mouse button once the pointer is on the other monitor, and the window moves there, keeping the spot you grabbed under the pointer. The move deliberately happens on release, not mid-drag, because the compositor re-creates the window when it changes monitor. If that happened while the button was still held, the drag could break.
- Releasing the button after a resize (from an edge or corner) does not change monitor.
- Default size is 380 × 300, minimum 200 × 120. The default position is near the top-right corner of the primary monitor (or the largest monitor if there is no primary).
- If the saved monitor is not connected, or is unplugged while the app runs, the window moves to another monitor at the default position.
- **Reset to defaults:** close the app and delete `~/.config/lyrics-pip-wayland/config.json`.
- Editing this file while the app is running has no effect, because it is overwritten when the app closes. Close the app first.

### Appearance (font, colors)
There is no settings file for this yet. Edit the `CSS` constant in `lyrics_pip/ui.py`:

| Selector | Controls |
|----------|----------|
| `window.lyrics` | rounded corners (the background color is `BG_RGB` in the same file) |
| `.line` | regular lyric lines (color, font size) |
| `.line.active` | the line being sung (default white, bold, 15pt) |
| `.title` | the title and artist at the top |

Restart the app after changing it.

### Lyrics cache
Stored in `~/.cache/lyrics-pip-wayland/`. Delete that folder to force all lyrics to be downloaded again, for example if a song's lyrics are wrong or have been updated on LRCLIB. Songs that were not found are only cached for 1 hour, then retried.

### Application menu entry (optional)
To open the app from the COSMIC application launcher without a terminal, create `~/.local/share/applications/lyrics-pip.desktop` (adjust the path to where the project lives):

```ini
[Desktop Entry]
Type=Application
Name=Lyrics PiP
Comment=Floating lyrics for YouTube Music songs in Firefox
Exec=/path/to/lyrics-app-wayland/lyrics-pip
Icon=multimedia-audio-player
Terminal=false
Categories=AudioVideo;Audio;Player;
```

To start it automatically at login, copy the same file to `~/.config/autostart/`.

## Custom lyrics

For songs that are not on LRCLIB, or whose lyrics are wrong, you can paste your own.

- **Add lyrics:** when "Lirik tidak ditemukan" (lyrics not found) appears, click **Tambah lirik** (add lyrics), paste the text, and click **Simpan** (save). The lyrics are shown right away.
- **Edit lyrics:** the **✎** button in the header (shown while a song is playing) opens the paste box. If the song already has custom lyrics, the box is pre-filled with them.
- **Remove custom lyrics:** empty the box and click **Simpan**. The app goes back to the lyrics from LRCLIB.
- **Reload:** the **⟳** button in the header clears the cache for the current song and fetches it again from scratch (for example after its lyrics were added to LRCLIB).

The text can be plain lyrics (shown without highlighting) or LRC format such as `[00:12.50] lyric line` (the active line is highlighted and follows the song). The format is detected automatically.

Custom lyrics are saved as files in the `lyrics/` folder inside the project, named `Artist - Title.lrc` or `Artist - Title.txt`. You can also put files there by hand. Custom files always take priority over LRCLIB.

> **The `lyrics/` folder is ignored by git on purpose and must not be committed.** Song lyrics are copyrighted, so keep them out of the repository, especially a public one. To back them up, use a separate private repository or copy them manually.

## Syncing lyrics (tap-sync)

If the lyrics are plain text (no timestamps), you can mark the timing yourself while listening, and the app saves the result as `.lrc`.

1. Show the lyrics (paste them via **Tambah lirik** / **✎**, or use plain lyrics from LRCLIB). The **⏱** button appears in the header while the lyrics have no timestamps.
2. Play the song **from the beginning**, then click **⏱**.
3. When a line is sung, **click that line**, or press **Space** to mark the highlighted line (the next unmarked line). Marked lines show their timestamp in front.
4. Marked one wrong? **Click the line again** to overwrite its time. There are no per-line nudge buttons.
5. Once every line is marked, click **Simpan** (save). The result is `Artist - Title.lrc` in `lyrics/`, and the highlighting starts working right away. **Batal** (cancel) discards all marks without saving.

Notes:
- Empty lines are skipped and are not marked.
- **Simpan** is refused if the times are not increasing (for example if you re-clicked an early line too late). The offending line is highlighted in red with a message.
- When you click **⏱**, the lyrics window takes **all** keyboard input so that **Space** marks lines (instead of pausing the song in Firefox). While sync mode is on you cannot type in other applications. Holding Space counts as one press. When sync mode ends (Simpan, Batal, or the song changes), the keyboard is released and the compositor returns focus to the previous window. If it does not, click the Firefox window once.
- **Song changes during sync mode:** if every line is marked and the order is correct (for example the song ended before you clicked Simpan), the result is **saved automatically** for the song that was being synced. If it is incomplete or out of order, the marks are discarded. Firefox briefly stalling or reporting a different duration does not cancel the session.
- **Reaction time compensation:** timestamp = song position minus `sync_offset` seconds, because you click slightly after a line starts being sung. Set it in `~/.config/lyrics-pip-wayland/config.json` (default `0.3`, range `0` to `2`; invalid values are treated as `0.3`). If results are consistently too early, lower the value; if too late, raise it. Close the app before editing this file.

## Tests

```bash
python3 -m unittest discover -s tests
```

## Layout

```
lyrics_pip/
  lrc.py      LRC parser and active-line lookup
  lyrics.py   LRCLIB client (with fallbacks) and disk cache
  mpris.py    MPRIS reader for Firefox
  clock.py    position estimator (Firefox only reports whole seconds)
  custom.py   custom lyrics (lyrics/ folder) and lookup order
  syncer.py   tap-sync logic (marking, order validation, .lrc output)
  ui.py       GTK window (layer-shell on Wayland, normal window as fallback)
  app.py      wiring and main()
  instance.py single-instance guard (file lock)
tests/        unittest tests
docs/superpowers/   design and implementation plans (in Indonesian)
```

## Limitations

- Firefox only (MPRIS bus `org.mpris.MediaPlayer2.firefox*`).
- Requires a compositor with `wlr-layer-shell`. GNOME (Mutter) does not support it, so on GNOME the window cannot stay on top.
- Dragging relies on how COSMIC reports pointer positions during a drag (relative to where the window was when the drag started). It has only been tested on COSMIC; other compositors may behave differently.
- The **Tambah lirik / ✎** box is a normal window, so the lyrics window can cover it if they overlap. The box opens in the center of the screen.
- Not every song is on LRCLIB. Songs that are not found show "Lirik tidak ditemukan".
- RAM and CPU usage should be about the same as the X11 version (around 58 MB, about 1% CPU), but it has not been measured again on COSMIC.
