# Lirik pribadi lewat kotak tempel: desain singkat

## Tujuan
Pengguna bisa menambah (atau menimpa) lirik sebuah lagu langsung dari jendela lirik dengan menempel teks. Untuk lagu yang tidak ada di LRCLIB atau yang liriknya salah.

## Yang diputuskan pengguna
- Pendekatan: kotak tempel di dalam aplikasi, memakai penyimpanan berupa folder lirik pribadi (percakapan 2026-11-16).

## Anti-tujuan
- Tidak membuat editor timestamp. Teks tanpa timestamp ditampilkan tanpa sorotan.
- Tidak mengunggah lirik ke layanan mana pun.

## Pilihan saya (belum disetujui)
- **Lokasi dan hak cipta:** repo GitHub pengguna berstatus Public dan lirik berhak cipta, jadi folder `lyrics/` ditambahkan ke `.gitignore` dan tidak pernah di-commit. Cadangan, jika diinginkan, lewat repo Private terpisah atau salinan manual (di luar lingkup ini). Folder dicari relatif terhadap lokasi proyek (`<proyek>/lyrics/`) dan dibuat otomatis saat pertama kali menyimpan.
- **Penyimpanan:** `<proyek>/lyrics/` (bukan `~/.local/share/...`), satu file per lagu bernama `Artis - Judul.lrc` (jika teksnya berisi timestamp LRC) atau `Artis - Judul.txt` (teks biasa). Nama dibersihkan dari karakter yang tidak valid untuk nama file. Judul yang dipakai adalah judul yang sudah dibersihkan `clean_title`. Pengguna juga bisa menaruh file di folder ini secara manual. README mencatat bahwa folder ini sengaja di-ignore karena hak cipta.
- **Prioritas pencarian:** file pribadi dicek lebih dulu, sebelum cache dan LRCLIB. File pribadi selalu menang, termasuk atas lirik online yang salah.
- **Tombol:** tombol "Tambah lirik" di bawah pesan "Lirik tidak ditemukan", dan tombol kecil ✎ di header (selalu tersedia saat ada lagu) untuk menimpa lirik yang salah.
- **Kotak tempel:** dialog GTK berisi kotak teks, tombol Batal dan Simpan. Terisi dulu dengan lirik pribadi yang sudah ada (jika ada). Dialog tetap di atas dan bisa menerima fokus (jendela utama tidak menerima fokus).
- **Menyimpan:** teks kosong pada lagu yang punya lirik pribadi menghapus file itu (kembali ke lirik online). Teks kosong pada lagu tanpa lirik pribadi tidak melakukan apa-apa. Setelah menyimpan, lirik langsung dimuat ulang di jendela.
- **Deteksi LRC:** jika `parse_lrc` menghasilkan minimal satu baris, disimpan sebagai `.lrc` dan disorot; jika tidak, `.txt` tanpa sorotan.

- **Muat ulang lirik (disetujui pengguna):** tombol ⟳ di header yang menghapus cache lagu yang sedang diputar (termasuk penanda "tidak ketemu") lalu mengambil ulang dari awal. Berguna setelah menyumbang lirik ke LRCLIB atau saat cache "tidak ketemu" masih berlaku.

## Bukan bagian ini
Penyesuaian timing per lagu (dibahas terpisah, belum diputuskan).

## Diserahkan ke pembangun
Tata letak dialog, pembersihan nama file, penanganan galat tulis file.
