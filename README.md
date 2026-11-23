# Lyrics PiP (Wayland)

Jendela lirik kecil yang selalu di atas jendela lain (seperti picture-in-picture) untuk lagu yang sedang diputar di **YouTube Music di Firefox**. Lirik tersinkron: baris yang sedang dinyanyikan disorot dan di-scroll otomatis.

Versi ini untuk **Pop!_OS 24.04 dengan desktop COSMIC (Wayland)**. Turunan dari `lyrics-app` (versi XFCE/X11). Tetap ringan: Python + GTK3, tanpa paket pip.

### Beda dengan versi X11

Di Wayland, aplikasi biasa tidak boleh memilih posisinya sendiri, memaksa diri selalu di atas, atau tampil di semua workspace. Karena itu jendela lirik dibuat sebagai **layer surface** (protokol `wlr-layer-shell`, lewat `gtk-layer-shell`), mekanisme yang juga dipakai panel COSMIC:

- Jendela ada di lapisan *overlay*: selalu di atas jendela lain (termasuk video layar penuh) dan tampil di semua workspace.
- Fitur seret dan ubah ukuran dibuat sendiri di aplikasi, karena compositor tidak menyediakannya untuk layer surface.
- Transparansi diatur lewat warna latar dan isi, karena di Wayland jendela tidak bisa diberi opacity.
- Saat jendela tidak fokus, Wayland tidak memberi tahu status tombol `Ctrl`. Karena itu transparansi juga bisa diatur dengan scroll di baris judul.
- Kalau `gtk-layer-shell` tidak terpasang, aplikasi tetap jalan sebagai jendela biasa (tidak selalu di atas) dan memberi peringatan di terminal.

## Cara kerja

- **Deteksi lagu:** membaca MPRIS lewat D-Bus (`Gio`). Firefox melaporkan judul, artis, durasi, dan posisi lagu, jadi tidak perlu ekstensi browser atau scraping.
- **Lirik:** diambil dari [LRCLIB](https://lrclib.net) (gratis, tanpa API key). Kalau lirik bertimestamp tidak ada, ditampilkan lirik biasa tanpa sorotan.
- **Cache:** hasil disimpan di `~/.cache/lyrics-pip/`.

## Kebutuhan

- Pop!_OS 24.04 / COSMIC (Wayland), atau compositor Wayland lain yang mendukung `wlr-layer-shell` (sway, Hyprland, KDE)
- Python 3.12+ dengan PyGObject dan GTK 3 (`python3-gi`, `gir1.2-gtk-3.0`)
- `gtk-layer-shell` untuk GTK3:

  ```bash
  sudo apt install gir1.2-gtklayershell-0.1
  ```
- Firefox yang memutar YouTube Music

## Menjalankan

```bash
./lyrics-pip
```

Putar lagu di YouTube Music, lalu liriknya muncul di jendela.

## Kontrol

| Aksi | Cara |
|------|------|
| Pindahkan jendela | seret di mana saja |
| Ubah ukuran | seret tepi atau sudut jendela |
| Atur transparansi | scroll mouse di baris judul (atau `Ctrl` + scroll di mana saja) |
| Tutup | tombol `×` di pojok |

Jendela selalu di atas jendela lain, tampil di semua workspace, tidak mengambil fokus keyboard, dan hanya bisa dibuka satu kali (membuka lagi saat sudah berjalan tidak melakukan apa-apa).

## Pengaturan

### Transparansi
Scroll mouse di baris judul (bagian atas jendela). `Ctrl` + scroll di mana saja juga bisa, tapi di Wayland hanya saat jendela lirik sedang fokus (misalnya selama mode sinkron). Naik = lebih pekat, turun = lebih transparan, per langkah 5%, dalam rentang 0,3 sampai 1,0. Bawaannya 0,92. Nilainya diingat untuk pembukaan berikutnya.

### Posisi dan ukuran
Geser jendela dari mana saja, ubah ukurannya dari tepi atau sudut. Jendela tidak bisa keluar dari monitor. Nilainya disimpan saat jendela ditutup (lewat `×`, `Ctrl+C`, atau `kill`) di `~/.config/lyrics-pip-wayland/config.json`:

```json
{"x": 2140, "y": 60, "w": 380, "h": 300, "opacity": 0.92, "sync_offset": 0.3, "monitor": "H27G30Q"}
```

- `x`/`y` dihitung dari pojok kiri atas **monitor** tempat jendela berada (bukan seluruh layar), dan `monitor` berisi nama model monitor itu.
- Jendela tidak bisa diseret ke monitor lain. Untuk pindah monitor, ganti `monitor` dengan nama model lain (lihat contoh nama di file config setelah aplikasi ditutup), lalu buka lagi.
- Ukuran bawaan 380 × 300, minimal 200 × 120. Posisi bawaan dekat pojok kanan atas monitor utama (kalau tidak ada monitor utama, monitor terbesar).
- Kalau monitor yang tersimpan tidak tersambung, atau dicabut saat aplikasi berjalan, jendela pindah ke monitor lain di posisi bawaan.
- **Reset ke bawaan:** tutup aplikasi lalu hapus `~/.config/lyrics-pip-wayland/config.json`.
- Mengedit file ini sambil aplikasi berjalan tidak ada gunanya, karena akan ditimpa saat aplikasi ditutup. Tutup aplikasi dulu.

### Tampilan (font, warna)
Belum ada pengaturan lewat file. Ubah konstanta `CSS` di `lyrics_pip/ui.py`:

| Selector | Mengatur |
|----------|----------|
| `window.lyrics` | warna latar jendela dan sudut membulat |
| `.line` | baris lirik biasa (warna, ukuran font) |
| `.line.active` | baris yang sedang dinyanyikan (bawaan putih, tebal, 15pt) |
| `.title` | judul dan artis di bagian atas |

Restart aplikasi setelah mengubahnya.

### Cache lirik
Disimpan di `~/.cache/lyrics-pip-wayland/`. Hapus folder itu untuk memaksa semua lirik diunduh ulang, misalnya kalau lirik sebuah lagu salah atau sudah diperbarui di LRCLIB. Lagu yang tidak ditemukan hanya di-cache 1 jam, lalu dicoba lagi.

### Entri menu aplikasi (opsional)
Supaya bisa dibuka dari menu aplikasi COSMIC tanpa terminal, buat `~/.local/share/applications/lyrics-pip.desktop` (ganti path sesuai lokasi proyek Anda):

```ini
[Desktop Entry]
Type=Application
Name=Lyrics PiP
Comment=Lirik mengambang untuk lagu YouTube Music di Firefox
Exec=/home/jhonsalya/Documents/Projects/lyrics-app-wayland/lyrics-pip
Icon=multimedia-audio-player
Terminal=false
Categories=AudioVideo;Audio;Player;
```

Untuk menyala otomatis saat login, salin file yang sama ke `~/.config/autostart/`.

## Lirik pribadi

Untuk lagu yang tidak ditemukan di LRCLIB, atau yang liriknya salah, Anda bisa menempel lirik sendiri.

- **Tambah lirik:** saat muncul "Lirik tidak ditemukan", klik tombol **Tambah lirik**, tempel teksnya, klik **Simpan**. Lirik langsung tampil.
- **Ubah lirik:** tombol **✎** di header (muncul saat ada lagu) membuka kotak tempel. Kalau lagu itu sudah punya lirik pribadi, kotaknya terisi lirik tersebut.
- **Hapus lirik pribadi:** kosongkan kotak lalu **Simpan**. Aplikasi kembali memakai lirik dari LRCLIB.
- **Muat ulang:** tombol **⟳** di header menghapus cache lagu yang sedang diputar dan mengambilnya lagi dari awal (misalnya setelah liriknya ditambahkan ke LRCLIB).

Teks boleh berupa lirik biasa (tampil tanpa sorotan) atau format LRC seperti `[00:12.50] baris lirik` (baris aktif tersorot dan mengikuti lagu). Formatnya dikenali otomatis.

Lirik pribadi disimpan sebagai file di folder `lyrics/` di dalam proyek, bernama `Artis - Judul.lrc` atau `Artis - Judul.txt`. Anda juga bisa menaruh file di sana secara manual. File pribadi selalu dipakai lebih dulu daripada LRCLIB.

> **Folder `lyrics/` sengaja di-ignore git dan tidak boleh di-commit.** Lirik lagu berhak cipta, dan repo ini Public. Kalau ingin mencadangkannya, pakai repo Private terpisah atau salin manual.

## Sinkronisasi lirik (tap-sync)

Kalau liriknya masih teks biasa (tanpa timestamp), Anda bisa menandai waktunya sendiri sambil mendengarkan lagu, lalu aplikasi menyimpannya sebagai `.lrc`.

1. Tampilkan liriknya (tempel lewat **Tambah lirik** / **✎**, atau pakai lirik biasa dari LRCLIB). Tombol **⏱** muncul di header selama liriknya belum bertimestamp.
2. Putar lagunya **dari awal**, lalu klik **⏱**.
3. Saat sebuah baris dinyanyikan, **klik baris itu**, atau tekan **Spasi** untuk menandai baris yang sedang disorot (baris berikutnya yang belum bertanda). Baris yang sudah ditandai menampilkan timestamp-nya di depan.
4. Salah menandai? **Klik ulang** barisnya untuk menimpa waktunya. Tidak ada tombol geser per baris.
5. Setelah semua baris bertanda, klik **Simpan**. Hasilnya `Artis - Judul.lrc` di `lyrics/`, dan sorotan lirik langsung berjalan. **Batal** membuang semua tanda tanpa menyimpan.

Catatan:
- Baris kosong dilewati dan tidak ikut ditandai.
- **Simpan** ditolak kalau urutan waktunya tidak naik (misalnya Anda mengklik ulang baris awal terlalu belakangan). Baris yang bermasalah ditandai merah dengan pesannya.
- Saat Anda klik **⏱**, jendela lirik mengambil **semua** input keyboard supaya **Spasi** menandai baris (bukan menjeda lagu di Firefox). Selama mode sinkron Anda tidak bisa mengetik di aplikasi lain. Spasi yang ditahan dihitung satu kali. Saat mode sinkron berakhir (Simpan, Batal, atau lagu berganti), keyboard dilepas dan compositor mengembalikan fokus ke jendela sebelumnya. Kalau tidak kembali, klik sekali di jendela Firefox.
- **Lagu berganti saat mode sinkron:** kalau semua baris sudah bertanda dan urutannya benar (misalnya lagu selesai sebelum sempat klik Simpan), hasilnya **otomatis disimpan** untuk lagu yang tadi disinkronkan. Kalau belum lengkap atau urutannya salah, tanda dibuang. Firefox yang macet sebentar atau perubahan durasi yang dilaporkan tidak membatalkan sesi.
- **Kompensasi waktu reaksi:** timestamp = posisi lagu dikurangi `sync_offset` detik, karena Anda mengklik sedikit setelah baris mulai dinyanyikan. Atur di `~/.config/lyrics-pip/config.json` (bawaan `0.3`, rentang `0` sampai `2`; nilai tidak valid dianggap `0.3`). Kalau hasilnya konsisten terlalu awal, kurangi nilainya; kalau terlalu terlambat, tambah. Tutup aplikasi sebelum mengedit file ini.

## Tes

```bash
python3 -m unittest discover -s tests
```

## Struktur

```
lyrics_pip/
  lrc.py      parser LRC dan pencarian baris aktif
  lyrics.py   klien LRCLIB (dengan fallback) dan cache disk
  mpris.py    pembaca MPRIS dari Firefox
  clock.py    penaksir posisi (Firefox hanya melaporkan detik bulat)
  custom.py   lirik pribadi (folder lyrics/) dan urutan pencarian
  syncer.py   logika tap-sync (penandaan waktu, validasi urutan, format .lrc)
  ui.py       jendela GTK (layer-shell di Wayland, jendela biasa sebagai cadangan)
  app.py      perangkai dan main()
  instance.py penjaga instance tunggal (file lock)
tests/        tes unittest
docs/superpowers/   desain dan rencana pembuatan
```

## Batasan

- Hanya Firefox (bus MPRIS `org.mpris.MediaPlayer2.firefox*`).
- Butuh compositor dengan `wlr-layer-shell`. GNOME (Mutter) tidak mendukungnya, jadi di GNOME jendela tidak bisa selalu di atas.
- Kotak **Tambah lirik / ✎** adalah jendela biasa, jadi bisa tertutup jendela lirik kalau letaknya bertumpuk. Kotak itu dibuka di tengah layar.
- Tidak semua lagu ada di LRCLIB. Lagu yang tidak ditemukan menampilkan "Lirik tidak ditemukan".
- Pemakaian RAM dan CPU kira-kira sama dengan versi X11 (sekitar 58 MB, CPU sekitar 1%), tapi belum diukur ulang di COSMIC.
