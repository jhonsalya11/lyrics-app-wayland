# Lirik Pribadi (Kotak Tempel) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pengguna bisa menambah, mengubah, atau menghapus lirik pribadi sebuah lagu dari jendela lirik lewat kotak tempel, dan memuat ulang lirik lagu yang sedang diputar.

**Architecture:** Modul baru `custom.py` menyimpan dan membaca lirik pribadi sebagai file di `<proyek>/lyrics/` dan menyediakan `resolve_lyrics` (file pribadi dulu, lalu `fetch_lyrics` yang sudah ada). `ui.py` mendapat tombol header ⟳ dan ✎, tombol aksi di pesan status, dan dialog tempel. `app.py` merangkai: simpan, hapus cache, ambil ulang.

**Tech Stack:** Python 3.12, PyGObject (Gtk 3.0), `unittest`. Tanpa dependensi baru.

**Spec:** `docs/superpowers/specs/2026-11-16-custom-lyrics-paste-design.md`

## Global Constraints

- Folder lirik pribadi: `<proyek>/lyrics/`, ditambahkan ke `.gitignore`, tidak pernah di-commit (repo Public, lirik berhak cipta).
- Nama file: `Artis - Judul.lrc` (teks berisi timestamp LRC) atau `Artis - Judul.txt` (teks biasa). Judul adalah hasil `clean_title(title, artist)`.
- File pribadi dicek **sebelum** cache dan LRCLIB; selalu menang.
- Teks kosong saat menyimpan lagu yang punya lirik pribadi menghapus file itu; pada lagu tanpa lirik pribadi tidak melakukan apa-apa.
- Teks UI Bahasa Indonesia: "Tambah lirik", "Muat ulang lirik", "Ubah lirik", "Gagal menyimpan lirik".
- Jendela utama tidak menerima fokus (`set_accept_focus(False)`); dialog tempel harus menerima fokus dan tetap di atas.
- Tes memakai `unittest` (`python3 -m unittest discover -s tests`). Commit per tugas; **jangan push** (tanyakan pengguna di akhir).
- Tanpa dependensi pip baru.

## Review Focus

- Judul/artis dengan karakter khusus atau jalur berbahaya (`AC/DC`, `Why?`, `../x`): file tersimpan langsung di `lyrics/`, tidak membuat subfolder, tidak crash. (Task 1)
- File pribadi tidak terbaca atau bukan UTF-8: dilewati dan jatuh ke LRCLIB, tidak crash. (Task 1)
- Teks tempel dengan CRLF, baris kosong di awal/akhir, atau `.lrc` tanpa timestamp: tersimpan dan terbaca sebagai teks biasa yang rapi. (Task 1)
- Lagu berganti saat dialog terbuka: lirik disimpan untuk lagu saat dialog dibuka, tanpa memuat ulang lagu yang sekarang. (Task 3)
- Menyimpan teks kosong: hanya menghapus file lagu itu; tanpa file pribadi tidak error; kegagalan tulis file ditampilkan, bukan crash. (Task 1 dan 3)

---

### Task 1: Penyimpanan lirik pribadi dan lupakan cache

**Files:**
- Create: `lyrics_pip/custom.py`, `tests/test_custom.py`
- Modify: `lyrics_pip/lyrics.py` (tambah `forget_cached`), `tests/test_lyrics.py`, `.gitignore`

**Interfaces:**
- Consumes: `Lyrics`, `fetch_lyrics`, `NETWORK_ERROR`, `_cache_path` dari `lyrics_pip/lyrics.py`; `parse_lrc` dari `lyrics_pip/lrc.py`.
- Produces (`lyrics_pip/custom.py`):
  - `CUSTOM_DIR: Path` = `Path(__file__).resolve().parent.parent / "lyrics"`
  - `safe_filename(artist: str, title: str) -> str`
  - `load_custom(title: str, artist: str, directory: Path) -> Lyrics | None`
  - `read_custom_text(title: str, artist: str, directory: Path) -> str`
  - `save_custom(title: str, artist: str, text: str, directory: Path) -> Path | None` (melempar `OSError` bila gagal menulis)
  - `resolve_lyrics(title, artist, album, duration, cache_dir, custom_dir, opener=urllib.request.urlopen) -> Lyrics | None | NETWORK_ERROR`
- Produces (`lyrics_pip/lyrics.py`): `forget_cached(title: str, artist: str, duration: float, cache_dir: Path) -> None`.

- [ ] **Step 1: Tulis tes yang gagal** di `tests/test_custom.py` (direktori sementara via `tempfile`) dan tambah ke `tests/test_lyrics.py`:
  - `test_safe_filename_basic`: `("Alesana","Song")` -> `"Alesana - Song"`; `("","Song")` -> `"Song"`.
  - `test_safe_filename_replaces_unsafe_chars`: `("AC/DC","Back In Black")` -> `"AC_DC - Back In Black"`; `("A","Why?: yes")` -> `"A - Why__ yes"`.
  - `test_safe_filename_never_escapes_or_hides`: `("..","../x")` tidak mengandung `/`, tidak diawali `.`; `("","")` -> `"untitled"`; panjang hasil <= 150.
  - `test_save_plain_text_writes_txt_and_load_reads_it`: teks `"a\r\n\r\nb\r\n"` disimpan -> file `Artis - Judul.txt`; `load_custom` -> `Lyrics([(0.0,"a"),(0.0,""),(0.0,"b")], False)`.
  - `test_save_lrc_text_writes_lrc_and_is_synced`: `"[00:01.00]hi"` -> `.lrc`; `load_custom` -> `Lyrics([(1.0,"hi")], True)`.
  - `test_saving_other_kind_removes_the_old_file`: simpan `.txt` lalu `.lrc` -> hanya `.lrc` ada, dan sebaliknya.
  - `test_save_empty_deletes_and_returns_none`: setelah menyimpan lirik, `save_custom(..., "  \n")` -> `None`, file hilang, `load_custom` -> `None`; pada lagu tanpa file tidak error.
  - `test_save_never_escapes_directory`: `save_custom("../x", "..", "teks", d)` membuat file yang `parent == d`.
  - `test_load_ignores_unreadable_or_non_utf8`: file berisi `b"\xff\xfe\x00"` -> `load_custom` -> `None`, `read_custom_text` -> `""`.
  - `test_read_custom_text_returns_raw_text_or_empty`.
  - `test_resolve_prefers_custom_without_network`: dengan file pribadi, `opener` yang melempar -> mengembalikan lirik pribadi, `opener` tidak dipanggil.
  - `test_resolve_falls_back_to_lrclib`: tanpa file pribadi -> memanggil `opener` dan mengembalikan hasilnya; file non-UTF8 juga jatuh ke `opener`.
  - Di `tests/test_lyrics.py`, `test_forget_cached_forces_refetch`: setelah `fetch_lyrics` tersimpan, `forget_cached(...)` lalu `fetch_lyrics` lagi memanggil `opener` lagi; `test_forget_cached_clears_not_found_marker`; `test_forget_cached_missing_file_is_noop`.
- [ ] **Step 2: Jalankan, pastikan gagal**: `python3 -m unittest tests.test_custom tests.test_lyrics -v` -> ImportError/FAIL.
- [ ] **Step 3: Implementasikan** modul sesuai antarmuka. `safe_filename`: ganti `<>:"/\|?*` dan karakter kontrol dengan `_` per komponen (artis, judul), buang titik dan spasi di awal tiap komponen, gabung `"{artis} - {judul}"` (atau judul saja bila artis kosong), potong 150 karakter, `"untitled"` bila kosong. Baca/tulis UTF-8 ketat; `load_custom`/`read_custom_text` menelan `OSError` dan `UnicodeDecodeError`. `.lrc` dicek lebih dulu daripada `.txt`; `.lrc` tanpa timestamp diperlakukan sebagai teks biasa. Normalisasi teks: ganti `\r\n` dengan `\n`, `strip()`. `forget_cached` menghapus file dari `_cache_path(...)` dengan `missing_ok`.
- [ ] **Step 4: Tambah `lyrics/` ke `.gitignore`**, lalu verifikasi: `mkdir -p lyrics && touch lyrics/x.lrc && git check-ignore -v lyrics/x.lrc` mencetak aturan `.gitignore`; `git status --short` tidak menampilkan `lyrics/`; hapus `lyrics/x.lrc`.
- [ ] **Step 5: Jalankan, pastikan lulus**: `python3 -m unittest discover -s tests` -> semua OK.
- [ ] **Step 6: Commit**: `git add lyrics_pip/custom.py lyrics_pip/lyrics.py tests .gitignore && git commit -m "Penyimpanan lirik pribadi dan forget_cached"`.

### Task 2: Tombol header, tombol aksi, dan dialog tempel (UI)

**Files:**
- Modify: `lyrics_pip/ui.py`

**Interfaces:**
- Consumes: tipe `Lyrics` (tidak berubah).
- Produces:
  - `LyricsWindow.on_edit: Callable[[], None] | None` dan `LyricsWindow.on_reload: Callable[[], None] | None` (dipanggil saat tombol ✎ / ⟳ diklik; tidak melakukan apa-apa bila `None`).
  - `LyricsWindow.set_song_controls(visible: bool) -> None`: menampilkan/menyembunyikan tombol ⟳ dan ✎ (tombol × selalu tampil). Awalnya tersembunyi.
  - `LyricsWindow.set_status(text: str, action: tuple[str, Callable[[], None]] | None = None) -> None`: bila `action` diberikan, tampilkan tombol berlabel `action[0]` di bawah pesan yang memanggil `action[1]` saat diklik.
  - `class LyricsPasteDialog(Gtk.Dialog)` dengan `set_text(text: str) -> None` dan `get_text() -> str`.
  - `ask_lyrics_text(parent: Gtk.Window, heading: str, initial: str) -> str | None`: dialog modal (Batal / Simpan), tetap di atas, menerima fokus; mengembalikan teks (boleh kosong) saat Simpan, `None` saat Batal atau ditutup.

- [ ] **Step 1: Implementasikan** perubahan di `ui.py`. Tombol header memakai kelas CSS `close` yang sudah ada, urutan: judul, ⟳ (tooltip "Muat ulang lirik"), ✎ (tooltip "Ubah lirik"), ×. Kotak teks dialog di dalam `Gtk.ScrolledWindow` (sekitar 420 × 320), `set_keep_above(True)`, `set_transient_for(parent)`. `set_status` tanpa `action` berperilaku persis seperti sekarang.
- [ ] **Step 2: Verifikasi di Xvfb** dengan skrip sementara di scratchpad (`xvfb-run -a python3 skrip.py`), bukan di layar pengguna. Expected (cetak dari skrip): tombol ⟳/✎ awalnya tidak terlihat dan terlihat setelah `set_song_controls(True)`; mengklik (`button.clicked()`) memanggil `on_reload` / `on_edit`; `set_status("x", ("Tambah lirik", f))` menampilkan tombol dan mengkliknya memanggil `f`; `LyricsPasteDialog` menerima `set_text("a\nb")` lalu `get_text()` -> `"a\nb"`. Hapus skrip sementara.
- [ ] **Step 3: Jalankan seluruh tes**: `python3 -m unittest discover -s tests` -> OK (tidak ada tes lama yang rusak).
- [ ] **Step 4: Commit**: `git add lyrics_pip/ui.py && git commit -m "UI: tombol muat ulang, ubah lirik, dan dialog tempel"`.

### Task 3: Rangkaian di aplikasi

**Files:**
- Modify: `lyrics_pip/app.py`, `tests/test_app.py` (perluas `FakeWin`)
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `resolve_lyrics`, `save_custom`, `read_custom_text`, `CUSTOM_DIR` (Task 1); `forget_cached` (Task 1); `ask_lyrics_text`, `LyricsWindow.on_edit/on_reload/set_song_controls/set_status(action)` (Task 2).
- Produces: `App.current: Track | None`; `App._edit() -> None`; `App._reload() -> None`; konstanta `MSG_SAVE_FAILED = "Gagal menyimpan lirik"`. `_start_fetch` memakai `resolve_lyrics(..., CACHE_DIR, CUSTOM_DIR)`.

- [ ] **Step 1: Tulis tes yang gagal.** Perluas `FakeWin`: `set_status(self, text, action=None)` mencatat `text` di `statuses` dan `action` di `actions`; tambah `set_song_controls(v)` yang mencatat ke `controls`. `make_app()` menambah `a.current = TRACK`. Tes baru (tiap tes mem-patch `appmod.CUSTOM_DIR` ke folder sementara, `appmod.ask_lyrics_text`, dan `a._start_fetch`; `threading.Thread` di-patch bila `_start_fetch` asli dipakai):
  - `test_not_found_offers_add_lyrics_action`: `_deliver(1, None, TRACK)` -> `statuses == [MSG_NOT_FOUND]` dan `actions[-1] == ("Tambah lirik", a._edit)`.
  - `test_edit_saves_and_refetches`: `ask` mengembalikan `"[00:01.00]hi"` -> file `A - T.lrc` ada di folder sementara; `_start_fetch` dipanggil sekali dengan `(KEY, TRACK)`.
  - `test_edit_dialog_is_prefilled_with_existing_custom_text`: file `A - T.txt` berisi `"lama"` -> `ask` dipanggil dengan `initial == "lama"`.
  - `test_edit_cancel_changes_nothing`: `ask` -> `None` -> tidak ada file, `_start_fetch` tidak dipanggil.
  - `test_edit_empty_text_removes_custom_and_refetches`.
  - `test_edit_when_song_changed_during_dialog_saves_original_without_refetch`: `ask` (side effect) mengubah `a.track_key` dan `a.current` ke lagu lain -> file tersimpan untuk `TRACK` asli, `_start_fetch` tidak dipanggil.
  - `test_edit_save_failure_shows_message`: `save_custom` di-patch melempar `OSError` -> `statuses[-1] == MSG_SAVE_FAILED`, tidak crash.
  - `test_edit_without_song_is_noop`: `a.current = None` -> `ask` tidak dipanggil.
  - `test_reload_forgets_cache_and_refetches`: `forget_cached` di-patch -> dipanggil dengan `(clean_title(TRACK.title, TRACK.artist), TRACK.artist, TRACK.length, CACHE_DIR)`; `_start_fetch` sekali.
  - `test_controls_follow_song_state`: `_poll` dengan lagu baru -> `controls == [True]`; tiga kegagalan berturut-turut -> `controls == [True, False]`.
- [ ] **Step 2: Jalankan, pastikan gagal**: `python3 -m unittest tests.test_app -v`.
- [ ] **Step 3: Implementasikan** di `app.py`: simpan `self.current` di `_start_fetch` dan kosongkan di `_reset`; panggil `set_song_controls(True/False)` di keduanya; pasang `win.on_edit = self._edit` dan `win.on_reload = self._reload` di `__init__`; `_deliver` memberi `action=("Tambah lirik", self._edit)` pada `MSG_NOT_FOUND`. `_edit`: tangkap `track` dan kuncinya di awal, hitung judul bersih, `initial = read_custom_text(...)`, `text = ask_lyrics_text(self.win, "<judul> — <artis>", initial)`; `None` -> selesai; `save_custom` (tangkap `OSError` -> `MSG_SAVE_FAILED`); lalu `_start_fetch` hanya bila `self.track_key` masih sama dengan kunci yang ditangkap. `_reload`: `forget_cached(...)` lalu `_start_fetch(self.track_key, self.current)`; keduanya no-op bila `self.current` kosong.
- [ ] **Step 4: Jalankan, pastikan lulus**: `python3 -m unittest discover -s tests` -> semua OK.
- [ ] **Step 5: Commit**: `git add lyrics_pip/app.py tests/test_app.py && git commit -m "Rangkai lirik pribadi, ubah lirik, dan muat ulang di aplikasi"`.

### Task 4: Dokumentasi dan verifikasi bersama pengguna

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Perbarui README**: tambah bagian "Lirik pribadi" yang menjelaskan tombol ⟳ dan ✎, tombol "Tambah lirik", lokasi `lyrics/` dan format nama file, `.lrc` vs `.txt`, teks kosong menghapus, file pribadi mengalahkan LRCLIB, dan **catatan bahwa `lyrics/` sengaja di-ignore git karena hak cipta (jangan di-commit ke repo Public)**; tambahkan `custom.py` ke daftar struktur.
- [ ] **Step 2: Jalankan seluruh tes**: `python3 -m unittest discover -s tests` -> semua OK.
- [ ] **Step 3: Restart aplikasi** (`pkill -TERM -f "[p]ython3 -m lyrics_pip"`, lalu `./lyrics-pip`) dan **minta pengguna** mencoba: (a) lagu tanpa lirik -> "Tambah lirik" -> tempel -> Simpan -> lirik langsung tampil; (b) ✎ pada lagu yang sudah punya lirik pribadi -> kotak terisi, ubah, simpan; (c) kosongkan lalu Simpan -> kembali ke lirik online/tidak ditemukan; (d) ⟳ memuat ulang; (e) mengklik tombol tidak ikut menggeser jendela; (f) saat mengetik di jendela lain, jendela lirik tidak mencuri fokus; (g) `git status` tidak menampilkan `lyrics/`.
- [ ] **Step 4: Commit**: `git add README.md && git commit -m "README: lirik pribadi"`.
