import json
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

try:  # wlr-layer-shell: the only way to stay on top / pick a position on Wayland
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell  # noqa: E402
except (ValueError, ImportError):
    GtkLayerShell = None

CONFIG_PATH = Path.home() / ".config" / "lyrics-pip-wayland" / "config.json"
# x/y: on Wayland (layer shell) the offset from the monitor's top-left corner,
# on the X11 fallback the absolute screen position.
DEFAULT_CONFIG = {"x": None, "y": None, "w": 380, "h": 300, "opacity": 0.92,
                  "sync_offset": 0.3, "monitor": None}
EDGE = 8
MIN_W, MIN_H = 200, 120
DEFAULT_RIGHT_GAP, DEFAULT_TOP_GAP = 40, 60
BG_RGB = "18, 18, 22"

CSS = b"""
window.lyrics { border-radius: 10px; }
.title { color: #9aa0aa; font-size: 10pt; }
.status { color: #c9ced6; font-size: 12pt; }
.line { color: #6f7682; font-size: 12pt; }
.line.active { color: #ffffff; font-size: 15pt; font-weight: bold; }
.sync-row { padding: 2px 4px; border-radius: 4px; }
.sync-row.next { background-color: rgba(255, 255, 255, 0.12); }
.sync-row.bad { background-color: rgba(255, 80, 80, 0.30); }
.sync-stamp { color: #7d8590; font-size: 9pt; }
.sync-text { color: #c9ced6; font-size: 12pt; }
.sync-bar label { color: #c9ced6; font-size: 10pt; }
button.close { color: #9aa0aa; background: none; border: none; box-shadow: none;
               padding: 0 6px; min-height: 0; min-width: 0; }
button.close:hover { color: #ff6b6b; }
"""


def load_config(path=CONFIG_PATH) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(Path(path).read_text()))
    except (OSError, ValueError):
        pass
    cfg["opacity"] = min(1.0, max(0.3, float(cfg.get("opacity") or 0.92)))
    try:
        offset = float(cfg.get("sync_offset"))
    except (TypeError, ValueError):
        offset = DEFAULT_CONFIG["sync_offset"]
    cfg["sync_offset"] = min(2.0, max(0.0, offset))  # 0 is a valid value
    return cfg


def save_config(cfg: dict, path=CONFIG_PATH) -> None:
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(cfg))
    except OSError:
        pass


def is_visible_position(x, y, w, h, monitors) -> bool:
    """True if enough of the window would land on one of the monitors."""
    if not monitors:
        return True
    for mx, my, mw, mh in monitors:
        ow = min(x + w, mx + mw) - max(x, mx)
        oh = min(y + h, my + mh) - max(y, my)
        if ow >= 80 and oh >= 40:
            return True
    return False


def layer_shell_available() -> bool:
    """True when running on a Wayland compositor that offers wlr-layer-shell."""
    if GtkLayerShell is None:
        return False
    try:
        return bool(GtkLayerShell.is_supported())
    except Exception:
        return False


def clamp_margin(x, y, w, h, mon_w, mon_h):
    """Keep a w x h window, placed at (x, y) inside a monitor, fully on it."""
    x = max(0, min(int(x), mon_w - w))
    y = max(0, min(int(y), mon_h - h))
    return x, y


def default_margin(w, h, mon_w, mon_h):
    """Default spot: near the top-right corner of the monitor."""
    return clamp_margin(mon_w - w - DEFAULT_RIGHT_GAP, DEFAULT_TOP_GAP, w, h, mon_w, mon_h)


def pick_monitor(saved_model, models):
    """Index of the monitor saved last time, or None if it is not connected."""
    if saved_model is None:
        return None
    try:
        return list(models).index(saved_model)
    except ValueError:
        return None


def drag_geometry(edge, start, dx, dy, min_w=MIN_W, min_h=MIN_H):
    """New (x, y, w, h) after dragging by (dx, dy).

    edge is None for a move, otherwise a set of sides being dragged
    ({"left"}, {"bottom", "right"}, ...). The opposite side stays put.
    """
    x, y, w, h = start
    if not edge:
        return x + dx, y + dy, w, h
    if "right" in edge:
        w = max(min_w, w + dx)
    if "bottom" in edge:
        h = max(min_h, h + dy)
    if "left" in edge:
        nw = max(min_w, w - dx)
        x, w = x + (w - nw), nw
    if "top" in edge:
        nh = max(min_h, h - dy)
        y, h = y + (h - nh), nh
    return x, y, w, h


def monitor_at(px, py, rects):
    """Index of the monitor rect (x, y, w, h) containing the point, or None."""
    for i, (mx, my, mw, mh) in enumerate(rects):
        if mx <= px < mx + mw and my <= py < my + mh:
            return i
    return None


def drop_margin(px, py, grab_x, grab_y, target):
    """Margins on the target monitor that put the grabbed spot under the pointer.

    (px, py) is the pointer in layout coordinates, (grab_x, grab_y) where the
    window was grabbed (relative to the window), target the monitor rect."""
    return int(px - target[0] - grab_x), int(py - target[1] - grab_y)


_EDGE_SIDES = {
    "NORTH": {"top"}, "SOUTH": {"bottom"}, "EAST": {"right"}, "WEST": {"left"},
    "NORTH_WEST": {"top", "left"}, "NORTH_EAST": {"top", "right"},
    "SOUTH_WEST": {"bottom", "left"}, "SOUTH_EAST": {"bottom", "right"},
}


def _label(text, css_class, selectable=False):
    lab = Gtk.Label(label=text)
    lab.set_line_wrap(True)
    lab.set_justify(Gtk.Justification.CENTER)
    lab.set_xalign(0.5)
    lab.get_style_context().add_class(css_class)
    return lab


class LyricsWindow(Gtk.Window):
    def __init__(self, config_path=CONFIG_PATH):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._config_path = config_path
        self._cfg = load_config(config_path)
        self._labels: list = []
        self._synced = False
        self._active = -1
        self._scroll_target = None
        self._scroll_timer = 0
        self.on_edit = None
        self.on_reload = None
        self.on_sync = None
        self.in_sync_mode = False
        self._saved_vis = {}
        self._sync_cbs = {}
        self._sync_rows = []
        self._sync_stamps = []
        self._prev_active = None
        self._space_down = False
        self._layer = layer_shell_available()
        self._monitor = None  # Gdk.Monitor the layer surface lives on
        self._geom = None  # (x, y, w, h) inside the monitor, layer mode only
        self._drag = None

        self.set_decorated(False)
        self.set_title("Lyrics PiP")
        self.set_resizable(True)
        self.set_default_size(self._cfg["w"], self._cfg["h"])
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.get_style_context().add_class("lyrics")

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        # Window opacity is ignored on Wayland, so fade the background and the
        # contents instead (looks the same and works on X11 too).
        self._bg_provider = Gtk.CssProvider()
        self.get_style_context().add_provider(
            self._bg_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )

        if self._layer:
            self._init_layer_shell()
        else:
            self.set_keep_above(True)
            self.set_skip_taskbar_hint(True)
            self.stick()  # visible on every workspace
            self.set_accept_focus(False)  # never steal keyboard focus from the user's work

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        outer.set_margin_top(6)
        outer.set_margin_bottom(8)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._title = Gtk.Label(label="")
        self._title.set_xalign(0)
        self._title.set_ellipsize(3)  # Pango.EllipsizeMode.END
        self._title.get_style_context().add_class("title")
        header.pack_start(self._title, True, True, 0)
        self._header = header
        close = Gtk.Button(label="×")
        close.get_style_context().add_class("close")
        close.set_relief(Gtk.ReliefStyle.NONE)
        close.set_can_focus(False)
        close.connect("clicked", lambda *_: self.close())
        header.pack_end(close, False, False, 0)
        self._edit_btn = self._header_button("✎", "Ubah lirik", lambda: self.on_edit)
        header.pack_end(self._edit_btn, False, False, 0)
        self._reload_btn = self._header_button("⟳", "Muat ulang lirik", lambda: self.on_reload)
        header.pack_end(self._reload_btn, False, False, 0)
        self._sync_btn = self._header_button("⏱", "Sinkronkan lirik", lambda: self.on_sync)
        header.pack_end(self._sync_btn, False, False, 0)
        outer.pack_start(header, False, False, 0)

        self._sync_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._sync_bar.get_style_context().add_class("sync-bar")
        self._sync_bar.set_no_show_all(True)
        self._sync_label = Gtk.Label(label="")
        self._sync_label.set_xalign(0)
        self._sync_label.set_line_wrap(True)
        self._sync_bar.pack_start(self._sync_label, True, True, 0)
        self._save_btn = Gtk.Button(label="Simpan")
        self._cancel_btn = Gtk.Button(label="Batal")
        for btn, key in ((self._cancel_btn, "cancel"), (self._save_btn, "save")):
            btn.set_can_focus(False)  # so Space never activates a button
            btn.connect("clicked", lambda *_a, k=key: self._sync_cb(k))
            self._sync_bar.pack_end(btn, False, False, 0)
        outer.pack_start(self._sync_bar, False, False, 0)

        self._scroller = Gtk.ScrolledWindow()
        self._scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._scroller.add(self._box)
        outer.pack_start(self._scroller, True, True, 0)
        self.add(outer)
        self._outer = outer
        self._apply_opacity()

        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
        )
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("scroll-event", self._on_scroll)
        # The ScrolledWindow would otherwise swallow Ctrl+scroll over the lyrics.
        self._scroller.connect("scroll-event", self._on_scroll)
        self.connect("key-press-event", self._on_key)
        self.connect("key-release-event", self._on_key_release)
        self.connect("focus-out-event", self._on_focus_out)
        self.connect("delete-event", self._on_delete)

        if not self._layer and self._cfg["x"] is not None and self._cfg["y"] is not None:
            x, y = int(self._cfg["x"]), int(self._cfg["y"])
            display = self.get_display()
            monitors = []
            for i in range(display.get_n_monitors()):
                g = display.get_monitor(i).get_geometry()
                monitors.append((g.x, g.y, g.width, g.height))
            if is_visible_position(x, y, self._cfg["w"], self._cfg["h"], monitors):
                self.move(x, y)

    # ---- layer shell (Wayland) ----------------------------------------
    def _init_layer_shell(self) -> None:
        L = GtkLayerShell
        L.init_for_window(self)
        L.set_namespace(self, "lyrics-pip")
        L.set_layer(self, L.Layer.OVERLAY)  # above normal and fullscreen windows
        L.set_anchor(self, L.Edge.TOP, True)
        L.set_anchor(self, L.Edge.LEFT, True)
        L.set_exclusive_zone(self, 0)  # float over other windows, never push them
        L.set_keyboard_mode(self, L.KeyboardMode.NONE)  # never steal keyboard focus

        display = self.get_display()
        monitors = [display.get_monitor(i) for i in range(display.get_n_monitors())]
        index = pick_monitor(self._cfg.get("monitor"), [m.get_model() for m in monitors])
        restore = index is not None and self._cfg["x"] is not None and self._cfg["y"] is not None
        if index is None:  # primary monitor, else the biggest one
            areas = [m.get_geometry().width * m.get_geometry().height for m in monitors]
            index = next((i for i, m in enumerate(monitors) if m.is_primary()),
                         areas.index(max(areas)) if areas else 0)
        self._place_on(monitors[index] if monitors else None, restore)
        display.connect("monitor-removed", self._on_monitor_removed)

    def _monitor_size(self):
        if self._monitor is None:
            return 1920, 1080
        g = self._monitor.get_geometry()
        return g.width, g.height

    def _place_on(self, monitor, restore: bool) -> None:
        self._monitor = monitor
        if monitor is not None:
            GtkLayerShell.set_monitor(self, monitor)
        mw, mh = self._monitor_size()
        w = max(MIN_W, min(int(self._cfg["w"]), mw))
        h = max(MIN_H, min(int(self._cfg["h"]), mh))
        if restore:
            x, y = clamp_margin(self._cfg["x"], self._cfg["y"], w, h, mw, mh)
        else:
            x, y = default_margin(w, h, mw, mh)
        self._apply_geometry(x, y, w, h)

    def _apply_geometry(self, x, y, w, h) -> None:
        mw, mh = self._monitor_size()
        w, h = min(w, mw), min(h, mh)
        x, y = clamp_margin(x, y, w, h, mw, mh)
        if self._geom is None or self._geom[2:] != (w, h):
            # A layer surface is as big as its contents ask for: request the size.
            self.set_size_request(w, h)
            self.resize(w, h)
        self._geom = (x, y, w, h)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, x)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, y)

    def _on_monitor_removed(self, _display, monitor) -> None:
        if monitor != self._monitor:
            return
        # Our output is gone: move to whatever monitor is left, at the default spot.
        display = self.get_display()
        left = [display.get_monitor(i) for i in range(display.get_n_monitors())]
        left = [m for m in left if m != monitor]
        self.hide()
        self._place_on(left[0] if left else None, restore=False)
        self.show()

    def _apply_opacity(self) -> None:
        a = self._cfg["opacity"]
        self._bg_provider.load_from_data(
            f"window.lyrics {{ background-color: rgba({BG_RGB}, {a:.2f}); }}".encode()
        )
        self._outer.set_opacity(min(1.0, a + 0.05))  # keep text a touch crisper

    # ---- content -------------------------------------------------------
    def _clear(self):
        for child in self._box.get_children():
            self._box.remove(child)
        self._labels = []
        self._active = -1
        self._synced = False

    def _header_button(self, label, tooltip, get_callback):
        btn = Gtk.Button(label=label)
        btn.get_style_context().add_class("close")
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_can_focus(False)
        btn.set_tooltip_text(tooltip)
        btn.set_no_show_all(True)  # hidden until set_song_controls(True)

        def clicked(*_):
            cb = get_callback()
            if cb is not None:
                cb()

        btn.connect("clicked", clicked)
        return btn

    def _set_header_visible(self, btn, visible: bool) -> None:
        if self.in_sync_mode:  # applied when sync mode ends
            self._saved_vis[btn] = visible
        elif visible:
            btn.show()
        else:
            btn.hide()

    def set_song_controls(self, visible: bool) -> None:
        for btn in (self._edit_btn, self._reload_btn):
            self._set_header_visible(btn, visible)

    def set_sync_button_visible(self, visible: bool) -> None:
        self._set_header_visible(self._sync_btn, visible)

    # ---- sync mode -----------------------------------------------------
    def _sync_cb(self, key):
        cb = self._sync_cbs.get(key)
        if cb is not None:
            cb()

    def enter_sync_mode(self, texts, on_mark, on_mark_next, on_save, on_cancel) -> None:
        self._clear()
        self.in_sync_mode = True
        self._sync_cbs = {"next": on_mark_next, "save": on_save, "cancel": on_cancel}
        self._saved_vis = {
            b: b.get_visible() for b in (self._edit_btn, self._reload_btn, self._sync_btn)
        }
        for btn in self._saved_vis:
            btn.hide()
        self._space_down = False
        if self._layer:
            # Take the keyboard now, or Space would still reach Firefox (play/pause).
            # The compositor hands focus back to the previous window when we let go.
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        else:
            # Remember who had focus (Firefox) so it can be handed back on exit.
            try:
                prev = self.get_screen().get_active_window()
            except Exception:
                prev = None
            own = self.get_window()
            self._prev_active = None if (prev is None or prev == own) else prev
            self.set_accept_focus(True)  # needed for the Space shortcut; undone on exit
            stamp = Gtk.get_current_event_time()
            if stamp:
                self.present_with_time(stamp)
            else:
                self.present()
        self._box.set_valign(Gtk.Align.START)
        self._box.set_margin_top(4)
        self._box.set_margin_bottom(4)
        self._sync_stamps = []
        for i, text in enumerate(texts):
            row = Gtk.EventBox()
            row.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            row.get_style_context().add_class("sync-row")
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            stamp = Gtk.Label(label="")
            stamp.set_width_chars(10)
            stamp.set_xalign(1)
            stamp.get_style_context().add_class("sync-stamp")
            line = Gtk.Label(label=text)
            line.set_line_wrap(True)
            line.set_xalign(0)
            line.get_style_context().add_class("sync-text")
            hbox.pack_start(stamp, False, False, 0)
            hbox.pack_start(line, True, True, 0)
            row.add(hbox)

            def pressed(_w, ev, index=i):
                if ev.button == 1:
                    on_mark(index)
                return True  # never start a window drag from a lyric row

            row.connect("button-press-event", pressed)
            self._sync_stamps.append(stamp)
            self._labels.append(row)
            self._box.pack_start(row, False, False, 0)
        self._box.show_all()
        self._sync_bar.show()
        self._sync_label.show()
        self._save_btn.show()
        self._cancel_btn.show()
        self._save_btn.set_sensitive(False)
        self._scroller.get_vadjustment().set_value(0)

    def set_sync_row(self, index: int, stamp_text) -> None:
        if 0 <= index < len(self._sync_stamps):
            self._sync_stamps[index].set_text(stamp_text or "")

    def set_sync_state(self, next_index, done: int, total: int, message: str = "",
                       bad_index=None) -> None:
        if not self.in_sync_mode:
            return
        text = f"Sinkron: {done}/{total} baris"
        self._sync_label.set_text(f"{text} — {message}" if message else text)
        self._save_btn.set_sensitive(total > 0 and done == total)
        for i, row in enumerate(self._labels):
            ctx = row.get_style_context()
            ctx.remove_class("next")
            ctx.remove_class("bad")
            if i == next_index:
                ctx.add_class("next")
            if i == bad_index:
                ctx.add_class("bad")
        if next_index is not None and 0 <= next_index < len(self._labels):
            self._active = next_index
            GLib.idle_add(self._scroll_to_active)

    def exit_sync_mode(self) -> None:
        if not self.in_sync_mode:
            return
        self.in_sync_mode = False
        if self._layer:
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
        else:
            self.set_accept_focus(False)
        self._space_down = False
        prev, self._prev_active = self._prev_active, None
        if prev is not None:  # hand focus back so Space/media keys reach Firefox again
            try:
                prev.focus(Gtk.get_current_event_time())
            except Exception:
                pass
        self._sync_bar.hide()
        self._sync_cbs = {}
        self._sync_stamps = []
        for btn, visible in self._saved_vis.items():
            btn.show() if visible else btn.hide()
        self._saved_vis = {}
        self._clear()

    def _on_key(self, _w, ev):
        if self.in_sync_mode and ev.keyval == Gdk.KEY_space:
            if not self._space_down:  # a held key auto-repeats: count one press only
                self._space_down = True
                self._sync_cb("next")
            return True
        return False

    def _on_key_release(self, _w, ev):
        if ev.keyval == Gdk.KEY_space:
            self._space_down = False
        return False

    def _on_focus_out(self, *_):
        self._space_down = False  # the release may go to another window
        return False

    def set_status(self, text: str, action=None) -> None:
        self._clear()
        self._title.set_text("")
        self._box.set_margin_top(0)
        self._box.set_margin_bottom(0)
        self._box.set_valign(Gtk.Align.CENTER)
        self._box.pack_start(_label(text, "status"), False, False, 0)
        if action is not None:
            label, callback = action
            btn = Gtk.Button(label=label)
            btn.set_can_focus(False)
            btn.set_halign(Gtk.Align.CENTER)
            btn.connect("clicked", lambda *_: callback())
            self._box.pack_start(btn, False, False, 0)
        self._box.show_all()

    def set_lyrics(self, lyrics, title: str, artist: str) -> None:
        self._clear()
        self._title.set_text(f"{title} — {artist}" if artist else title)
        self._synced = bool(lyrics.synced)
        self._box.set_valign(Gtk.Align.START)
        pad = 110 if self._synced else 4
        self._box.set_margin_top(pad)
        self._box.set_margin_bottom(pad)
        for _, text in lyrics.lines:
            lab = _label(text or "♪", "line")
            self._labels.append(lab)
            self._box.pack_start(lab, False, False, 0)
        self._box.show_all()
        self._scroller.get_vadjustment().set_value(0)

    def set_active(self, index: int) -> None:
        if not self._synced or index == self._active:
            return
        if 0 <= self._active < len(self._labels):
            self._labels[self._active].get_style_context().remove_class("active")
        self._active = index
        if not (0 <= index < len(self._labels)):
            return
        self._labels[index].get_style_context().add_class("active")
        GLib.idle_add(self._scroll_to_active)

    def _scroll_to_active(self):
        if not (0 <= self._active < len(self._labels)):
            return False
        lab = self._labels[self._active]
        coords = lab.translate_coordinates(self._box, 0, 0)
        if coords is None:
            return False
        y = coords[1] + self._box.get_margin_top() + lab.get_allocated_height() / 2
        adj = self._scroller.get_vadjustment()
        self._scroll_target = max(0, y - adj.get_page_size() / 2)
        if not self._scroll_timer:
            self._scroll_timer = GLib.timeout_add(16, self._scroll_step)
        return False

    def _scroll_step(self):
        adj = self._scroller.get_vadjustment()
        diff = self._scroll_target - adj.get_value()
        if abs(diff) < 1:
            adj.set_value(self._scroll_target)
            self._scroll_timer = 0
            return False
        adj.set_value(adj.get_value() + diff * 0.25)
        return True

    # ---- window behaviour ---------------------------------------------
    def _edge_at(self, x, y):
        w, h = self.get_size()
        left, right = x < EDGE, x > w - EDGE
        top, bottom = y < EDGE, y > h - EDGE
        E = Gdk.WindowEdge
        if top and left:
            return E.NORTH_WEST
        if top and right:
            return E.NORTH_EAST
        if bottom and left:
            return E.SOUTH_WEST
        if bottom and right:
            return E.SOUTH_EAST
        if left:
            return E.WEST
        if right:
            return E.EAST
        if top:
            return E.NORTH
        if bottom:
            return E.SOUTH
        return None

    def _local(self, ev):
        """Event position relative to our surface, whichever child window got it.

        GDK cannot know where a layer surface sits on screen, so its "root"
        coordinates are really surface coordinates."""
        if self._layer:
            return ev.x_root, ev.y_root
        return ev.x, ev.y

    def _on_press(self, _w, ev):
        if ev.button != 1:
            return False
        lx, ly = self._local(ev)
        edge = self._edge_at(lx, ly)
        if self._layer:
            # Layer surfaces cannot use the compositor's move/resize: do it ourselves
            # by changing the margins (position) and size while the button is held.
            mx, my = self._geom[0], self._geom[1]
            self._drag = {
                "sides": _EDGE_SIDES[edge.value_nick.upper().replace("-", "_")] if edge else None,
                "start": self._geom,
                "px": mx + lx, "py": my + ly,  # pointer in monitor coordinates
            }
        elif edge is not None:
            self.begin_resize_drag(edge, ev.button, int(ev.x_root), int(ev.y_root), ev.time)
        else:
            self.begin_move_drag(ev.button, int(ev.x_root), int(ev.y_root), ev.time)
        return True

    def _drag_to(self, d, lx, ly) -> None:
        """Follow the pointer.

        While the button is held, COSMIC reports the pointer relative to where the
        surface was when the drag started, not where we have moved it since. So the
        pointer in monitor coordinates is the start position plus the event position.
        (Adding the current margins instead counts every step twice, and the window
        runs away from the pointer.)"""
        x0, y0 = d["start"][0], d["start"][1]
        dx, dy = int(x0 + lx - d["px"]), int(y0 + ly - d["py"])
        self._apply_geometry(*drag_geometry(d["sides"], d["start"], dx, dy))

    def _on_release(self, _w, ev):
        if ev.button == 1 and self._drag is not None:
            d, self._drag = self._drag, None
            lx, ly = self._local(ev)
            if d["sides"] is None:  # a move, not a resize
                self._maybe_switch_monitor(lx, ly, d)
            return True
        return False

    def _maybe_switch_monitor(self, lx, ly, d) -> None:
        """Dropped with the pointer over another monitor: move the window there.

        Done only on release, never mid-drag: re-creating the surface while the
        button is held could lose the pointer grab."""
        if self._monitor is None:
            return
        display = self.get_display()
        monitors = [display.get_monitor(i) for i in range(display.get_n_monitors())]
        rects = [(g.x, g.y, g.width, g.height) for g in (m.get_geometry() for m in monitors)]
        cur = self._monitor.get_geometry()
        # Pointer in layout coordinates: monitor origin + where the drag started
        # (see _drag_to) + position in the event.
        px, py = cur.x + d["start"][0] + lx, cur.y + d["start"][1] + ly
        index = monitor_at(px, py, rects)
        if index is None or monitors[index] == self._monitor:
            return
        grab_x = d["px"] - d["start"][0]
        grab_y = d["py"] - d["start"][1]
        x, y = drop_margin(px, py, grab_x, grab_y, rects[index])
        self._monitor = monitors[index]
        GtkLayerShell.set_monitor(self, self._monitor)
        self._apply_geometry(x, y, self._geom[2], self._geom[3])  # clamps to the new monitor

    def _on_motion(self, _w, ev):
        lx, ly = self._local(ev)
        if self._drag is not None and not (ev.state & Gdk.ModifierType.BUTTON1_MASK):
            self._drag = None  # the release was lost somewhere: stop following the pointer
        if self._drag is not None:
            self._drag_to(self._drag, lx, ly)
            return True
        edge = self._edge_at(lx, ly)
        win = self.get_window()
        if win is None:
            return False
        if edge is None:
            win.set_cursor(None)
        else:
            name = {
                Gdk.WindowEdge.NORTH: "n-resize", Gdk.WindowEdge.SOUTH: "s-resize",
                Gdk.WindowEdge.EAST: "e-resize", Gdk.WindowEdge.WEST: "w-resize",
                Gdk.WindowEdge.NORTH_WEST: "nw-resize", Gdk.WindowEdge.NORTH_EAST: "ne-resize",
                Gdk.WindowEdge.SOUTH_WEST: "sw-resize", Gdk.WindowEdge.SOUTH_EAST: "se-resize",
            }[edge]
            win.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), name))
        return False

    def _over_header(self, ev) -> bool:
        _lx, ly = self._local(ev)
        a = self._header.get_allocation()
        return ly <= a.y + a.height + 4

    def _on_scroll(self, w, ev):
        # Wayland only tells the focused window about Ctrl, and this window is never
        # focused, so scrolling over the title row works as well as Ctrl + scroll.
        ctrl = bool(ev.state & Gdk.ModifierType.CONTROL_MASK)
        if not ctrl and (w is self._scroller or not self._over_header(ev)):
            return False
        step = 0.05 if ev.direction == Gdk.ScrollDirection.UP else -0.05
        if ev.direction == Gdk.ScrollDirection.SMOOTH:
            step = -0.05 * ev.delta_y
        elif ev.direction not in (Gdk.ScrollDirection.UP, Gdk.ScrollDirection.DOWN):
            return True
        self._cfg["opacity"] = min(1.0, max(0.3, self._cfg["opacity"] + step))
        self._apply_opacity()
        return True

    def _on_delete(self, *_):
        if self._layer:
            x, y, w, h = self._geom
            model = self._monitor.get_model() if self._monitor is not None else None
            self._cfg.update({"x": x, "y": y, "w": w, "h": h, "monitor": model})
        else:
            x, y = self.get_position()
            w, h = self.get_size()
            self._cfg.update({"x": x, "y": y, "w": w, "h": h})
        save_config(self._cfg, self._config_path)
        return False


class LyricsPasteDialog(Gtk.Dialog):
    """Paste box for custom lyrics (plain text or LRC)."""

    def __init__(self, parent, heading: str, initial: str = ""):
        # A layer-shell surface cannot be a dialog parent on Wayland.
        layered = GtkLayerShell is not None and getattr(parent, "_layer", False)
        super().__init__(title="Ubah lirik", transient_for=None if layered else parent,
                         modal=True)
        self.set_keep_above(True)  # X11: the lyrics window is always on top; so are we
        if layered:
            self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(440, 380)
        self.add_button("Batal", Gtk.ResponseType.CANCEL)
        self.add_button("Simpan", Gtk.ResponseType.OK)
        area = self.get_content_area()
        area.set_spacing(6)
        area.set_border_width(8)
        area.pack_start(Gtk.Label(label=heading, xalign=0), False, False, 0)
        area.pack_start(
            Gtk.Label(label="Tempel lirik biasa, atau format LRC ([mm:ss.xx] teks) agar tersorot.",
                      xalign=0), False, False, 0)
        self._view = Gtk.TextView()
        self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        scroller = Gtk.ScrolledWindow()
        scroller.add(self._view)
        area.pack_start(scroller, True, True, 0)
        self.set_text(initial)
        area.show_all()

    def set_text(self, text: str) -> None:
        self._view.get_buffer().set_text(text)

    def get_text(self) -> str:
        buf = self._view.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)


def ask_lyrics_text(parent, heading: str, initial: str):
    """Show the paste dialog. Returns the text on Simpan (may be empty), None on cancel."""
    dialog = LyricsPasteDialog(parent, heading, initial)
    try:
        response = dialog.run()
        return dialog.get_text() if response == Gtk.ResponseType.OK else None
    finally:
        dialog.destroy()
