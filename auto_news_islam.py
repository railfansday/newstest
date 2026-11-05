import feedparser
import time
import sqlite3
from datetime import datetime

# ============================================
# KONFIGURASI
# ============================================
DB_FILE = "berita_islam.db"
INTERVAL_MENIT = 30
OUTPUT_FILE = "berita_islam.html"
MAX_BERITA_PER_SUMBER = 8
LIMIT_TAMPIL = 60

# Seed data: fokus berita Islam Indonesia
RSS_SEED = [
    ("Republika Online", "https://www.republika.co.id/rss"),
    # Tambahkan sumber lain di sini kalau URL RSS-nya sudah kamu verifikasi:
    # ("Islampos", "https://www.islampos.com/feed/"),
    # ("Hidayatullah", "https://hidayatullah.com/feed/"),
    # ("Eramuslim", "https://www.eramuslim.com/feed/"),
    # ("Muslim.or.id", "https://muslim.or.id/feed/"),
    # ("NU Online", "https://www.nu.or.id/rss"),
    # ("Muhammadiyah", "https://muhammadiyah.or.id/feed/"),
]


# ============================================
# SETUP DATABASE
# ============================================
def init_db():
    """Buat tabel & seed data kalau database belum ada."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rss_sumber (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL,
            aktif INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS berita (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sumber_id INTEGER,
            judul TEXT,
            link TEXT UNIQUE,
            waktu_publish TEXT,
            ringkasan TEXT,
            diambil_pada TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sumber_id) REFERENCES rss_sumber(id)
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM rss_sumber")
    if cursor.fetchone()[0] == 0:
        for nama, url in RSS_SEED:
            cursor.execute(
                "INSERT OR IGNORE INTO rss_sumber (nama, url) VALUES (?, ?)",
                (nama, url)
            )
        print("[OK] Seed data RSS Islam dimasukkan.")

    conn.commit()
    conn.close()


# ============================================
# FUNGSI DATABASE
# ============================================
def get_rss_aktif():
    """Ambil semua sumber RSS yang aktif."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nama, url FROM rss_sumber WHERE aktif = 1")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "nama": r[1], "url": r[2]} for r in rows]


def simpan_berita(sumber_id, entry):
    """Simpan berita ke database (skip kalau link sudah ada)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO berita
            (sumber_id, judul, link, waktu_publish, ringkasan)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sumber_id,
            entry.get("title", "Tanpa Judul"),
            entry.get("link", "#"),
            entry.get("published", "-"),
            entry.get("summary", "")[:300],
        ))
        conn.commit()
    except Exception as e:
        print(f"    [WARN] Gagal simpan: {e}")
    finally:
        conn.close()


def ambil_berita_terbaru(limit=LIMIT_TAMPIL):
    """Ambil berita terbaru dari database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.nama, b.judul, b.link, b.waktu_publish, b.ringkasan
        FROM berita b
        JOIN rss_sumber s ON b.sumber_id = s.id
        ORDER BY b.diambil_pada DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {"sumber": r[0], "judul": r[1], "link": r[2],
         "waktu": r[3], "ringkasan": r[4]}
        for r in rows
    ]


# ============================================
# FUNGSI AMBIL BERITA
# ============================================
def ambil_berita():
    """Ambil berita dari semua RSS aktif, simpan ke DB."""
    rss_list = get_rss_aktif()
    total = 0
    for rss in rss_list:
        try:
            feed = feedparser.parse(rss["url"])
            entries = feed.entries[:MAX_BERITA_PER_SUMBER]
            for entry in entries:
                simpan_berita(rss["id"], entry)
            total += len(entries)
            print(f"  ✓ {rss['nama']}: {len(entries)} berita")
        except Exception as e:
            print(f"  ✗ {rss['nama']}: Gagal - {e}")
    return total


# ============================================
# EXPORT HTML
# ============================================
def buat_html(berita_list):
    """Membuat file HTML dari daftar berita."""
    waktu_update = datetime.now().strftime("%d %B %Y, %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="1800">
    <title>Berita Islam Indonesia - {waktu_update}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f7f0; margin: 0; padding: 20px; }}
        .header {{ background: #1b5e20; color: white; padding: 25px; border-radius: 10px; margin-bottom: 20px; text-align: center; }}
        .header h1 {{ margin: 0; }}
        .header p {{ margin: 8px 0 0; color: #c8e6c9; }}
        .berita {{ background: white; padding: 18px 22px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); border-left: 5px solid #2e7d32; }}
        .berita h2 {{ margin: 0 0 10px; font-size: 18px; line-height: 1.4; }}
        .berita h2 a {{ color: #1b5e20; text-decoration: none; }}
        .berita h2 a:hover {{ color: #e94560; }}
        .sumber {{ display: inline-block; background: #2e7d32; color: white; padding: 3px 12px; border-radius: 12px; font-size: 12px; margin-bottom: 10px; font-weight: bold; }}
        .waktu {{ color: #888; font-size: 13px; margin-bottom: 10px; }}
        .ringkasan {{ color: #444; font-size: 14px; line-height: 1.6; }}
        .footer {{ text-align: center; color: #888; font-size: 13px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🕌 Berita Islam Indonesia</h1>
        <p>Terakhir diperbarui: {waktu_update} | Auto-refresh tiap 30 menit</p>
    </div>
"""

    if not berita_list:
        html += """
    <div class="berita">
        <p style="text-align:center; color:#888;">Belum ada berita. Menunggu pengambilan berikutnya...</p>
    </div>
"""
    else:
        for b in berita_list:
            html += f"""
    <div class="berita">
        <span class="sumber">{b['sumber']}</span>
        <h2><a href="{b['link']}" target="_blank">{b['judul']}</a></h2>
        <div class="waktu">{b['waktu']}</div>
        <div class="ringkasan">{b['ringkasan']}...</div>
    </div>
"""

    html += f"""
    <div class="footer">Total {len(berita_list)} berita ditampilkan.</div>
</body>
</html>"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] '{OUTPUT_FILE}' dibuat pada {waktu_update}")


# ============================================
# MAIN LOOP
# ============================================
def main():
    print("🚀 Auto News Islam Indonesia dimulai. Ctrl+C untuk berhenti.\n")

    init_db()

    while True:
        print(f"🔄 Mengambil berita... ({datetime.now().strftime('%H:%M:%S')})")
        total = ambil_berita()
        print(f"📥 {total} berita diproses.")

        berita = ambil_berita_terbaru()
        buat_html(berita)

        print(f"⏰ Menunggu {INTERVAL_MENIT} menit...\n")
        time.sleep(INTERVAL_MENIT * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Program dihentikan.")