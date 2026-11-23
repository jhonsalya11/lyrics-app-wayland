# Lyrics PiP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jendela GTK kecil yang selalu di atas dan menampilkan lirik tersinkron untuk lagu yang sedang diputar di YouTube Music (Firefox).

**Architecture:** Modul murni (parser LRC, klien LRCLIB + cache) dipisah dari modul sistem (MPRIS via Gio, UI GTK) agar yang murni bisa diuji dengan `unittest` tanpa GUI. `app.py` merangkai: poll MPRIS -> ambil lirik di thread latar -> perbarui UI di main loop GTK.

**Tech Stack:** Python 3.12, PyGObject (`gi`) dengan Gtk 3.0 dan Gio, stdlib `urllib`, `json`, `unittest`. Tanpa dependensi pip.

**Spec:** `docs/superpowers/specs/2026-11-16-lyrics-pip-design.md`

## Global Constraints

- Target RAM < 50 MB; tanpa paket pip, tanpa sudo, tanpa `playerctl`.
- Gtk 3.0 (`gi.require_version('Gtk', '3.0')`); XFCE di X11. Pytest tidak terpasang, pakai `unittest` (`python3 -m unittest discover -s tests`).
- Bus MPRIS: nama berawalan `org.mpris.MediaPlayer2.firefox`. Objek `/org/mpris/MediaPlayer2`, antarmuka `org.mpris.MediaPlayer2.Player`, `Position` dalam mikrodetik.
- LRCLIB: `GET https://lrclib.net/api/get` dengan parameter `track_name`, `artist_name`, `album_name`, `duration` (detik). Pakai `syncedLyrics`, jika kosong `plainLyrics`.
- Cache di `~/.cache/lyrics-pip/`. Konfigurasi jendela di `~/.config/lyrics-pip/config.json`.
- Teks UI dalam Bahasa Indonesia: "Tidak ada lagu diputar", "Lirik tidak ditemukan".
- Folder proyek bukan repo git: langkah commit dilewati.

## Review Focus

- Judul lagu YouTube Music berisi tambahan seperti "(Official Video)" atau artis kosong: tetap coba cari, jangan crash.
- Tab Firefox lain memutar video non-musik (artis kosong, durasi panjang): tampilkan "Lirik tidak ditemukan", jangan error.
- Jaringan mati atau LRCLIB lambat/error: UI tetap hidup, tampil "Lirik tidak ditemukan", tidak membeku.
- Pergantian lagu cepat (skip beruntun): hasil unduhan lagu lama tidak boleh menimpa lirik lagu baru.
- Firefox ditutup atau MPRIS hilang saat berjalan: kembali ke "Tidak ada lagu diputar", tanpa crash.
- Baris LRC rusak, timestamp ganda, atau lirik kosong: parser tidak melempar error.

## File Structure

- `lyrics_pip/__init__.py`: kosong.
- `lyrics_pip/lrc.py`: parser LRC dan pencarian baris aktif.
- `lyrics_pip/lyrics.py`: klien LRCLIB, cache disk, tipe `Lyrics`.
- `lyrics_pip/mpris.py`: pembaca MPRIS.
- `lyrics_pip/ui.py`: jendela GTK.
- `lyrics_pip/app.py`: perangkai dan `main()`.
- `lyrics-pip`: skrip peluncur (`python3 -m lyrics_pip.app`).
- `tests/test_lrc.py`, `tests/test_lyrics.py`, `tests/test_mpris.py`.

---

### Task 1: Parser LRC

**Files:**
- Create: `lyrics_pip/__init__.py`, `lyrics_pip/lrc.py`
- Test: `tests/test_lrc.py`

**Interfaces:**
- Produces: `parse_lrc(text: str) -> list[tuple[float, str]]` (detik, teks; terurut naik); `active_index(lines: list[tuple[float, str]], position: float) -> int` (indeks baris aktif, `-1` jika posisi sebelum baris pertama atau `lines` kosong).

- [ ] **Step 1: Tulis tes yang gagal** di `tests/test_lrc.py`:
  - `test_parse_basic`: `"[00:12.50]Halo\n[01:02.00]Dunia"` -> `[(12.5, "Halo"), (62.0, "Dunia")]`.
  - `test_parse_multiple_timestamps`: `"[00:01.00][00:05.00]Ulang"` -> dua entri bertuliskan "Ulang", terurut.
  - `test_parse_ignores_metadata_and_garbage`: baris `[ar:Artis]`, `[ti:Judul]`, baris tanpa timestamp, dan string kosong tidak menghasilkan entri dan tidak melempar error.
  - `test_parse_skips_empty_text_lines_but_keeps_them_as_gaps`: `"[00:10.00]"` menghasilkan `(10.0, "")` (jeda instrumental tetap ada).
  - `test_active_index`: untuk `[(1.0,"a"),(5.0,"b")]`: posisi 0.5 -> -1; 1.0 -> 0; 4.99 -> 0; 5.0 -> 1; 99 -> 1; daftar kosong -> -1.
- [ ] **Step 2: Jalankan, pastikan gagal**: `python3 -m unittest tests.test_lrc -v` -> ImportError/FAIL.
- [ ] **Step 3: Implementasikan** `parse_lrc` dan `active_index` di `lyrics_pip/lrc.py`. Gunakan regex untuk timestamp `[mm:ss.xx]` (fraksi 2 atau 3 digit, opsional); `active_index` pakai `bisect`.
- [ ] **Step 4: Jalankan, pastikan lulus**: `python3 -m unittest tests.test_lrc -v` -> OK.

### Task 2: Klien LRCLIB dan cache

**Files:**
- Create: `lyrics_pip/lyrics.py`
- Test: `tests/test_lyrics.py`

**Interfaces:**
- Consumes: `parse_lrc` dari Task 1.
- Produces:
  - `@dataclass Lyrics: lines: list[tuple[float, str]]; synced: bool` (untuk lirik biasa, `synced=False` dan setiap baris berstempel `0.0`).
  - `clean_title(title: str) -> str`: buang akhiran seperti "(Official Video)", "[Lyrics]", "(Audio)" dan spasi sisa.
  - `fetch_lyrics(title: str, artist: str, album: str, duration: float, cache_dir: Path, opener=urllib.request.urlopen) -> Lyrics | None`: cek cache dulu; jika tidak ada panggil LRCLIB; simpan hasil ke cache (termasuk hasil "tidak ditemukan" yang disimpan sebagai penanda, kedaluwarsa 1 jam); `None` jika tidak ketemu atau terjadi error jaringan. Tidak pernah melempar error. `opener` bisa diganti di tes.

- [ ] **Step 1: Tulis tes yang gagal** di `tests/test_lyrics.py` dengan `opener` palsu dan `tempfile.TemporaryDirectory()`:
  - `test_clean_title`: `"Judul (Official Video)"` -> `"Judul"`; `"Judul [Lyrics]"` -> `"Judul"`; `"Judul"` tetap.
  - `test_fetch_synced`: respons `{"syncedLyrics": "[00:01.00]a", "plainLyrics": "a"}` -> `Lyrics([(1.0,"a")], True)`; URL yang dipanggil memuat `track_name`, `artist_name`, `album_name`, `duration`.
  - `test_fetch_plain_fallback`: `syncedLyrics` kosong/null, `plainLyrics` "a\nb" -> `synced=False`, dua baris.
  - `test_cache_hit_skips_network`: panggilan kedua dengan `opener` yang melempar error tetap mengembalikan hasil sama.
  - `test_not_found_returns_none_and_is_cached`: respons HTTP 404 -> `None`; panggilan kedua tidak memanggil `opener`.
  - `test_network_error_returns_none_not_raise`: `opener` melempar `URLError` -> `None`, dan hasilnya tidak di-cache.
  - `test_empty_artist_still_works`: `artist=""` tidak melempar error.
- [ ] **Step 2: Jalankan, pastikan gagal**: `python3 -m unittest tests.test_lyrics -v`.
- [ ] **Step 3: Implementasikan** di `lyrics_pip/lyrics.py`. Nama berkas cache dari hash SHA1 `(title|artist|duration)`; isi JSON. Timeout jaringan 8 detik; header `User-Agent: lyrics-pip/0.1`.
- [ ] **Step 4: Jalankan, pastikan lulus**: `python3 -m unittest tests.test_lyrics -v` -> OK.

### Task 3: Pembaca MPRIS

**Files:**
- Create: `lyrics_pip/mpris.py`
- Test: `tests/test_mpris.py`

**Interfaces:**
- Produces:
  - `@dataclass Track: title: str; artist: str; album: str; length: float` (detik).
  - `@dataclass PlayerState: track: Track | None; position: float; playing: bool`.
  - `parse_metadata(meta: dict) -> Track | None`: dari dict metadata MPRIS (`xesam:title`, `xesam:artist` berupa list, `xesam:album`, `mpris:length` dalam mikrodetik); `None` jika tidak ada judul.
  - `class MprisReader: read() -> PlayerState | None`: mencari bus `org.mpris.MediaPlayer2.firefox*` lewat `Gio.DBusProxy`/`Gio.bus_get_sync`, membaca `Metadata`, `PlaybackStatus`, `Position`. Mengembalikan `None` bila tidak ada pemain atau terjadi error D-Bus (tidak melempar error).

- [ ] **Step 1: Tulis tes yang gagal** untuk `parse_metadata` saja (bagian D-Bus diuji manual di Task 5): metadata lengkap -> `Track("Judul","Artis","Album",215.0)` dari `mpris:length=215000000`; artis list kosong -> `artist=""`; tanpa judul -> `None`; `mpris:length` hilang -> `length=0.0`.
- [ ] **Step 2: Jalankan, pastikan gagal**: `python3 -m unittest tests.test_mpris -v`.
- [ ] **Step 3: Implementasikan** `parse_metadata` dan `MprisReader`. Pilih pemain Firefox yang sedang `Playing` jika ada beberapa, jika tidak ada yang `Playing` pakai yang pertama.
- [ ] **Step 4: Jalankan tes, lulus**: `python3 -m unittest tests.test_mpris -v` -> OK.
- [ ] **Step 5: Verifikasi manual**: putar lagu di YouTube Music di Firefox, lalu jalankan `python3 -c "from lyrics_pip.mpris import MprisReader; print(MprisReader().read())"` dan pastikan menampilkan judul, artis, dan posisi yang sesuai. Jika kosong, periksa `dbus-send --session --dest=org.freedesktop.DBus --print-reply /org/freedesktop/DBus org.freedesktop.DBus.ListNames | grep mpris` dan laporkan ke pengguna.

### Task 4: Jendela GTK

**Files:**
- Create: `lyrics_pip/ui.py`

**Interfaces:**
- Consumes: tipe `Lyrics` (Task 2).
- Produces: `class LyricsWindow(Gtk.Window)` dengan metode:
  - `set_status(text: str) -> None`: tampilkan pesan satu baris (mis. "Tidak ada lagu diputar", "Lirik tidak ditemukan", "Mencari lirik...").
  - `set_lyrics(lyrics: Lyrics, title: str, artist: str) -> None`: tampilkan lirik dengan judul kecil di atas.
  - `set_active(index: int) -> None`: sorot baris `index` (-1 = tanpa sorotan) dan scroll sehingga baris itu di tengah; tidak berefek bila `lyrics.synced` False.
  - Perilaku jendela: tanpa dekorasi, `set_keep_above(True)`, bisa digeser (seret di mana saja) dan di-resize (pegangan tepi/sudut), transparansi diatur dengan scroll mouse + Ctrl (0.3-1.0), tombol tutup kecil (×) di pojok, ukuran/posisi/opasitas disimpan ke `~/.config/lyrics-pip/config.json` saat ditutup dan dipulihkan saat dibuka. Latar semi-transparan gelap, baris aktif putih tebal dan lebih besar, baris lain abu-abu.

- [ ] **Step 1: Implementasikan** `LyricsWindow` dengan CSS GTK (`Gtk.CssProvider`). Gunakan RGBA visual agar transparan. Satu `Gtk.Label` per baris di dalam `Gtk.ScrolledWindow` tanpa scrollbar tampak.
- [ ] **Step 2: Verifikasi manual** dengan skrip sementara di scratchpad yang membuat `LyricsWindow`, memanggil `set_lyrics` dengan ~20 baris contoh, lalu `set_active` bergantian lewat `GLib.timeout_add`. Konfirmasi di layar: jendela di atas jendela lain, bisa digeser/di-resize, transparansi berubah dengan Ctrl+scroll, sorotan bergerak dan baris aktif tetap di tengah, posisi diingat setelah dibuka ulang. Hapus skrip sementara setelah selesai.

### Task 5: Perangkai aplikasi dan peluncur

**Files:**
- Create: `lyrics_pip/app.py`, `lyrics-pip` (skrip, executable), `lyrics_pip/__main__.py` (memanggil `app.main()`)
- Test: manual end-to-end

**Interfaces:**
- Consumes: `MprisReader`/`PlayerState`/`Track` (Task 3), `fetch_lyrics`/`Lyrics` (Task 2), `active_index` (Task 1), `LyricsWindow` (Task 4).
- Produces: `main() -> None`.

- [ ] **Step 1: Implementasikan `main()`** dengan perilaku berikut:
  - Timer GLib 250 ms memanggil `MprisReader.read()`; bila `None` atau `track is None` -> `set_status("Tidak ada lagu diputar")` dan turunkan interval polling ke 2 detik sampai ada lagu lagi.
  - Bila identitas lagu (`title`, `artist`, `length`) berubah: `set_status("Mencari lirik...")` dan jalankan `fetch_lyrics` di thread latar; hasil dikirim ke main loop via `GLib.idle_add` dengan token lagu, dan **dibuang bila token sudah usang** (lagu sudah berganti). `None` -> `set_status("Lirik tidak ditemukan")`.
  - Saat lirik tersinkron tersedia dan `playing`: `set_active(active_index(lines, position))` setiap tick; jika dijeda, sorotan tetap di posisi terakhir.
  - Judul dibersihkan dengan `clean_title` sebelum pencarian.
  - Semua pengecualian di tick ditangkap agar jendela tetap hidup.
- [ ] **Step 2: Buat peluncur** `lyrics-pip` (`#!/usr/bin/env bash`, `cd` ke folder skrip, `exec python3 -m lyrics_pip`) dan `chmod +x`.
- [ ] **Step 3: Verifikasi end-to-end** dengan pengguna: jalankan `./lyrics-pip` saat YouTube Music memutar lagu populer. Periksa: lirik muncul dan baris aktif mengikuti lagu; seek maju/mundur di YouTube Music langsung diikuti; skip beruntun cepat tidak menampilkan lirik lagu lama; tutup Firefox -> "Tidak ada lagu diputar"; matikan Wi-Fi lalu putar lagu baru yang belum ada di cache -> "Lirik tidak ditemukan" tanpa membeku.
- [ ] **Step 4: Ukur RAM**: `ps -o rss= -p $(pgrep -f lyrics_pip)` saat berjalan; target < 50 MB (nilai dalam KB). Laporkan angka sebenarnya ke pengguna, termasuk bila melebihi target.
- [ ] **Step 5: Jalankan seluruh tes**: `python3 -m unittest discover -s tests -v` -> semua OK.
