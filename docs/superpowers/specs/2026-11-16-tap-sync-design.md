# Sinkronisasi lirik dengan klik (tap-sync): desain singkat

## Tujuan
Pengguna menambahkan lirik biasa (tanpa timestamp), memutar lagunya, lalu menandai tiap baris dengan mengklik baris itu saat dinyanyikan. Aplikasi menyimpan posisi lagu sebagai timestamp dan menulis file `.lrc` sehingga lirik tersorot mengikuti lagu.

## Yang diputuskan pengguna
- Menandai dengan klik pada baris. Koreksi cukup dengan **klik ulang** baris itu. **Tidak ada tombol geser ±0,1 detik.**

## Anti-tujuan / bukan tujuan
- Tidak ada tombol geser per baris, tidak ada tumpukan undo, tidak ada kontrol pemutaran (seek) ke Firefox, tidak ada sinkron ulang untuk lirik yang sudah bertimestamp (untuk itu pakai ✎).
- Tidak ada pengenalan suara otomatis.

## Pendekatan
- Dipilih: mode sinkron di dalam jendela PiP yang sudah ada.
- Ditolak: jendela editor terpisah dengan garis waktu; lebih berat dan tidak sejalan dengan "klik saja, tanpa tombol geser".

## Pilihan saya (belum disetujui)
- **Masuk mode:** tombol **⏱** di header muncul saat lirik yang tampil adalah lirik biasa (dari file pribadi `.txt` atau LRCLIB tanpa timestamp). Baris kosong dilewati (tidak ditandai).
- **Tampilan mode sinkron:** semua baris tampil; baris yang sudah ditandai menampilkan timestamp kecil abu-abu di depannya; baris "berikutnya" (indeks terkecil yang belum ditandai) disorot. Bilah di atas menampilkan `Sinkron: N/M baris` dengan tombol **Simpan** dan **Batal**.
- **Menandai:** klik sebuah baris menandainya dengan posisi lagu saat itu; klik ulang menimpa. Selain klik, tombol **Spasi** menandai baris "berikutnya". Untuk itu jendela hanya selama mode sinkron menerima fokus keyboard, dan dikembalikan tidak menerima fokus saat keluar mode.
- **Posisi dan kompensasi:** posisi dari `PositionEstimator` dikurangi `sync_offset` (detik, bawaan 0,3, di `config.json`) untuk waktu reaksi klik; hasil tidak kurang dari 0. Disimpan dengan 2 digit pecahan (`[mm:ss.xx]`).
- **Simpan:** aktif bila semua baris tidak-kosong sudah ditandai. Timestamp harus tidak menurun menurut urutan baris; kalau tidak, penyimpanan ditolak dan baris pertama yang bermasalah ditandai dengan pesan. Hasilnya ditulis lewat `save_custom` sebagai `.lrc` ke `lyrics/`, lalu lirik dimuat ulang seperti biasa (sorotan langsung jalan).
- **Batal / lagu berganti:** Batal membuang tanda tanpa menyimpan. Jika lagu berganti saat mode sinkron aktif, mode dibatalkan dengan pesan dan tanda dibuang.
- **Struktur:** logika murni (menandai, baris berikutnya, validasi urutan, format `.lrc`) di modul baru `lyrics_pip/syncer.py` yang bisa diuji tanpa GUI; UI dan rangkaian di `ui.py` dan `app.py`.

## Diserahkan ke pembangun
Tata letak bilah dan gaya timestamp, nama kunci config selain `sync_offset`, pesan galat persis.
