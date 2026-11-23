# Lyrics PiP: desain singkat

## Tujuan
Jendela kecil mengambang (seperti PiP) yang selalu di atas jendela lain dan menampilkan lirik lagu yang sedang diputar di YouTube Music (Firefox), dengan baris aktif tersorot mengikuti posisi lagu. Untuk pemakaian pribadi di laptop ini.

## Mengapa
Pengguna bekerja dengan banyak jendela terbuka dan ingin melihat lirik sekilas tanpa pindah tab. Laptop sering kehabisan RAM sampai memakai swap, jadi aplikasi harus sangat ringan.

## Tujuan / bukan tujuan / anti-tujuan
- Tujuan: ringan (target < 50 MB RAM), selalu di atas, lirik tersinkron, tanpa sudo atau instalasi paket.
- Bukan tujuan: dukungan player lain, multi-OS, mengedit lirik, akun pengguna, distribusi ke orang lain.
- Anti-tujuan: aplikasi yang memakan RAM besar atau butuh unduhan ratusan MB, meskipun tampilannya bagus.

## Kendala
- XFCE di X11 (always-on-top didukung). Python 3 dan `gi` sudah ada. `playerctl` tidak ada, dan tidak dipakai.
- Tanpa dependensi pip yang berat. Jaringan hanya untuk LRCLIB.

## Pendekatan yang dipertimbangkan
- A. Electron: tampilan paling mudah dipoles, tapi ~150 MB RAM dan ~250-300 MB disk. Ditolak karena RAM.
- **B. Python + GTK (dipilih pengguna):** ringan, jendela asli, tanpa unduhan besar. Tampilan dibatasi CSS GTK.
- C. Halaman web di jendela Firefox: tidak mirip PiP, "selalu di atas" manual. Ditolak.

## Desain (pilihan saya, belum disetujui)
- **Deteksi lagu:** baca MPRIS lewat `Gio` D-Bus. Cari bus bernama `org.mpris.MediaPlayer2.firefox*`. Ambil `Metadata` (judul, artis, album, durasi) dan `Position` lewat polling ringan (sekitar 4x per detik, untuk sorotan baris). Perubahan lagu dideteksi lewat sinyal `PropertiesChanged`.
- **Lirik:** `GET https://lrclib.net/api/get` (judul, artis, album, durasi). Pakai `syncedLyrics` (format LRC) jika ada, jika tidak pakai `plainLyrics` tanpa sorotan. Jika tidak ketemu, tampilkan "Lirik tidak ditemukan".
- **Cache:** simpan hasil di `~/.cache/lyrics-pip/` agar tidak mengunduh ulang. Hasil "tidak ditemukan" juga di-cache sebentar.
- **Jendela:** GTK, tanpa dekorasi, selalu di atas, bisa digeser dan di-resize, transparansi bisa diatur. Menampilkan beberapa baris dengan baris aktif di tengah dan lebih terang, di-scroll otomatis. Ukuran dan posisi diingat.
- **Saat tidak ada musik:** tampilkan "Tidak ada lagu diputar" dan hentikan polling cepat.
- **Struktur:** satu paket Python kecil dengan modul terpisah untuk MPRIS, LRCLIB+cache, parser LRC, dan UI, supaya parser dan cache bisa diuji tanpa GUI.

## Diserahkan ke pembangun
Detail CSS, tombol kontrol (tutup, transparansi), pengaturan polling, cara menjalankan (skrip peluncur atau entri menu XFCE), dan penanganan galat jaringan.
