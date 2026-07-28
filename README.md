# sap_middleware_bapi

Middleware Python untuk menarik data dari SAP lewat **BAPI/RFC** dan menyimpannya
ke **PostgreSQL**, diekspos lewat REST API (FastAPI) sehingga bisa dipicu manual
atau dijadwalkan otomatis.

## Daftar isi

- [Fitur](#fitur)
- [Struktur proyek](#struktur-proyek)
- [Prasyarat](#prasyarat)
- [Instalasi](#instalasi)
  - [Opsi A — Docker Compose (disarankan)](#opsi-a--docker-compose-disarankan)
  - [Opsi B — Instalasi lokal (tanpa Docker)](#opsi-b--instalasi-lokal-tanpa-docker)
- [Konfigurasi (environment variables)](#konfigurasi-environment-variables)
- [Menghubungkan ke SAP asli (non-mock)](#menghubungkan-ke-sap-asli-non-mock)
- [Deployment ke server produksi](#deployment-ke-server-produksi)
- [Penggunaan API](#penggunaan-api)
- [Menjalankan test](#menjalankan-test)
- [Troubleshooting](#troubleshooting)

## Fitur

- Koneksi ke SAP via `pyrfc` (RFC/BAPI) dengan connection pooling sederhana.
- **Mode mock** (`SAP_MOCK_MODE=true`, default) — middleware jalan penuh tanpa
  akses ke SAP asli, cocok untuk development/demo/testing.
- BAPI yang sudah diimplementasikan:
  - `BAPI_CUSTOMER_GETLIST` → tabel `customers`
  - `BAPI_MATERIAL_GET_DETAIL` (per material) → tabel `materials`
  - `BAPI_SALESORDER_GETLIST` + `BAPI_SALESORDER_GETDETAILEDLIST` → tabel
    `sales_orders` + `sales_order_items`
  - `BAPI_SALESORDER_CREATEFROMDAT2` + `BAPI_TRANSACTION_COMMIT` (contoh
    write-back dari middleware ke SAP)
  - Endpoint generik `POST /bapi/call` untuk memanggil BAPI apa pun.
- Upsert idempoten ke Postgres (`INSERT ... ON CONFLICT DO UPDATE`).
- Audit log setiap sinkronisasi di tabel `sync_logs`.
- Scheduler opsional (APScheduler) untuk sync berkala.
- Auth sederhana pakai header `X-API-Key` untuk endpoint yang mengubah data.
- Dokumentasi API otomatis (Swagger UI) di `/docs`.

## Struktur proyek

```
app/
  config.py          # Settings (Postgres, SAP, API key) dari env/.env
  main.py             # FastAPI app + lifespan (init DB, buat BAPIClient, scheduler)
  scheduler.py         # APScheduler untuk sync berkala
  db/
    database.py        # Engine/session SQLAlchemy
    models.py           # Customer, Material, SalesOrder, SalesOrderItem, SyncLog
    repository.py        # Fungsi upsert Postgres
  sap/
    connection.py        # Connection manager pyrfc (butuh SAP NW RFC SDK)
    mock_client.py        # Simulasi RFC untuk mode mock
    bapi_client.py         # Wrapper BAPI level tinggi (dipakai mock maupun real)
    exceptions.py
  services/
    sync_service.py        # Orkestrasi: panggil BAPI -> upsert DB -> log
  api/
    routes.py              # Endpoint REST
    schemas.py               # Pydantic request/response
scripts/init_db.py     # Buat tabel manual (opsional, app juga auto create saat start)
tests/                  # Unit & integration test (pakai mode mock)
docker-compose.yml      # Postgres + app
Dockerfile              # Image aplikasi
requirements.txt        # Dependency inti (mode mock jalan tanpa tambahan apa pun)
requirements-sap.txt    # Dependency tambahan untuk koneksi SAP asli (pyrfc)
```

## Prasyarat

| Komponen | Versi minimal | Wajib untuk |
|---|---|---|
| Python | 3.11+ | Instalasi lokal |
| PostgreSQL | 13+ (dites dengan 16) | Semua mode |
| Docker & Docker Compose | 24+ | Opsi instalasi Docker |
| SAP NW RFC SDK + `pyrfc` | — | Hanya jika koneksi ke SAP **asli** (bukan mock) |

Secara default aplikasi berjalan dalam **mode mock** (`SAP_MOCK_MODE=true`),
jadi tidak butuh instalasi SAP NW RFC SDK sama sekali untuk mencoba,
mengembangkan, atau men-demo-kan aplikasi ini.

## Instalasi

### Opsi A — Docker Compose (disarankan)

Cara tercepat, otomatis menyiapkan PostgreSQL + aplikasi sekaligus.

```bash
git clone <url-repo-ini>
cd sap_middleware_bapi

cp .env.example .env
# (opsional) edit .env untuk ganti API_KEY, kredensial Postgres, dll.

docker compose up --build -d
```

Cek status container:

```bash
docker compose ps
docker compose logs -f app
```

API tersedia di `http://localhost:8000`, dokumentasi interaktif di
`http://localhost:8000/docs`. Database Postgres otomatis dibuat lewat
service `postgres` di `docker-compose.yml` dan tabel dibuat otomatis oleh
aplikasi saat startup.

Untuk berhenti:

```bash
docker compose down          # stop, data Postgres tetap ada (volume)
docker compose down -v       # stop + hapus data Postgres
```

### Opsi B — Instalasi lokal (tanpa Docker)

**1. Siapkan PostgreSQL**

Pastikan server PostgreSQL sudah berjalan, lalu buat database. **Aplikasi
ini hanya membuat tabel secara otomatis — database-nya sendiri (mis.
`sap_middleware`) harus sudah ada lebih dulu**, kalau belum akan muncul
error `database "sap_middleware" does not exist` saat startup.

```bash
# Linux (Debian/Ubuntu), jika Postgres belum berjalan:
sudo pg_ctlcluster 16 main start   # sesuaikan versi cluster

# Buat database & user (contoh, sesuaikan dengan kredensial Anda)
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
sudo -u postgres createdb sap_middleware
```

```powershell
# Windows, lewat "SQL Shell (psql)" atau psql yang ada di PATH
psql -U postgres -h localhost -c "CREATE DATABASE sap_middleware;"
```

Atau lewat pgAdmin: klik kanan **Databases** → **Create** → **Database...**,
isi nama `sap_middleware` (harus sama persis dengan `POSTGRES_DB` di
`.env`), lalu **Save**.

**2. Clone repo & buat virtual environment**

```bash
git clone <url-repo-ini>
cd sap_middleware_bapi

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

**3. Konfigurasi environment**

```bash
cp .env.example .env
```

Edit `.env`, minimal sesuaikan bagian PostgreSQL agar cocok dengan langkah 1:

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=sap_middleware
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

**4. (Opsional) buat tabel secara manual**

Aplikasi otomatis membuat tabel saat startup, tapi bisa juga dijalankan
manual:

```bash
python -m scripts.init_db
```

**5. Jalankan aplikasi**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Buka `http://localhost:8000/docs` untuk mencoba API lewat Swagger UI.

## Konfigurasi (environment variables)

Semua variabel dibaca dari file `.env` di root proyek (lihat `.env.example`)
atau dari environment variable OS secara langsung — cocok untuk kebutuhan
Docker/Kubernetes/CI.

| Variabel | Default | Keterangan |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | Host PostgreSQL |
| `POSTGRES_PORT` | `5432` | Port PostgreSQL |
| `POSTGRES_DB` | `sap_middleware` | Nama database |
| `POSTGRES_USER` | `postgres` | User PostgreSQL |
| `POSTGRES_PASSWORD` | `postgres` | Password PostgreSQL |
| `SAP_MOCK_MODE` | `true` | `true` = pakai fake BAPI response, `false` = konek ke SAP asli via `pyrfc` |
| `SAP_ASHOST` | *(kosong)* | Application server SAP (hanya dipakai jika `SAP_MOCK_MODE=false`) |
| `SAP_SYSNR` | `00` | System number SAP |
| `SAP_CLIENT` | `100` | Client/mandant SAP |
| `SAP_USER` | *(kosong)* | User RFC di SAP |
| `SAP_PASSWD` | *(kosong)* | Password user RFC |
| `SAP_LANG` | `EN` | Logon language |
| `SAP_POOL_SIZE` | `2` | Jumlah koneksi RFC yang di-pool |
| `API_KEY` | `change-me` | Nilai header `X-API-Key` yang harus dikirim klien untuk endpoint yang mengubah data (`POST /sync/*`, `POST /bapi/call`) |
| `LOG_LEVEL` | `INFO` | Level logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `SYNC_INTERVAL_MINUTES` | `0` | Interval sync otomatis (menit). `0` = scheduler nonaktif, sync hanya lewat API |

> **Penting untuk produksi:** selalu ganti `API_KEY` dan `POSTGRES_PASSWORD`
> dari nilai default, dan jangan commit file `.env` ke git (sudah masuk
> `.gitignore`).

## Menghubungkan ke SAP asli (non-mock)

`pyrfc` adalah binding C ke **SAP NetWeaver RFC SDK**, library proprietary
milik SAP yang tidak didistribusikan lewat PyPI — jadi tidak otomatis
terpasang lewat `requirements.txt`. Untuk pakai koneksi SAP sungguhan:

1. Download **"SAP NW RFC SDK"** dari SAP Support Portal (butuh S-user SAP).
2. Ekstrak SDK tersebut ke server middleware, misalnya ke `/opt/sapnwrfcsdk`,
   lalu set environment variable:
   ```bash
   export SAPNWRFC_HOME=/opt/sapnwrfcsdk
   export LD_LIBRARY_PATH=$SAPNWRFC_HOME/lib:$LD_LIBRARY_PATH   # Linux
   ```
3. Install dependency tambahan:
   ```bash
   pip install -r requirements-sap.txt
   ```
4. Set di `.env`:
   ```
   SAP_MOCK_MODE=false
   SAP_ASHOST=<application server SAP>
   SAP_SYSNR=<system number>
   SAP_CLIENT=<client>
   SAP_USER=<rfc user>
   SAP_PASSWD=<password>
   SAP_LANG=EN
   ```
5. Restart aplikasi. Endpoint `GET /health` akan menunjukkan
   `"sap_mock_mode": false` bila konfigurasi berhasil dibaca; koneksi RFC
   sesungguhnya baru dibuka saat BAPI pertama kali dipanggil (lazy).

Selama `SAP_MOCK_MODE=true`, tidak ada dependency SAP yang dibutuhkan sama
sekali — semua panggilan BAPI dilayani oleh `app/sap/mock_client.py`.

**Menambah BAPI lain:** tambahkan method baru di `app/sap/bapi_client.py`
(mapping field SAP → dict Python), tabel ORM terkait di `app/db/models.py`,
fungsi upsert di `app/db/repository.py`, lalu orkestrasi sync di
`app/services/sync_service.py` dan endpoint di `app/api/routes.py`. Untuk
mode mock, tambahkan handler `_<nama_bapi_lowercase>` di
`app/sap/mock_client.py` agar bisa dites tanpa SAP asli.

## Deployment ke server produksi

### Dengan Docker (disarankan)

```bash
git clone <url-repo-ini> && cd sap_middleware_bapi
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD, API_KEY, dan kredensial SAP yang kuat/rahasia

docker compose up --build -d
```

Rekomendasi untuk produksi:

- Jalankan Postgres di service terkelola (RDS, Cloud SQL, dll.) daripada
  container `postgres` di `docker-compose.yml`, lalu arahkan
  `POSTGRES_HOST`/`POSTGRES_PORT` ke sana.
- Taruh aplikasi di belakang reverse proxy (Nginx/Traefik) untuk terminasi
  TLS (HTTPS) dan rate limiting, karena `uvicorn` di container hanya serve
  HTTP polos di port 8000.
- Simpan `API_KEY`, `SAP_PASSWD`, `POSTGRES_PASSWORD` di secret manager
  (Docker secrets, Vault, AWS Secrets Manager, dsb.), bukan file `.env`
  biasa di server.
- Set `SYNC_INTERVAL_MINUTES` sesuai kebutuhan bisnis jika ingin sync
  berkala otomatis, atau panggil endpoint `/sync/*` dari scheduler
  eksternal (cron, Airflow, dll.) bila `SYNC_INTERVAL_MINUTES=0`.

### Tanpa Docker (systemd + Nginx)

Contoh menjalankan sebagai service systemd di Linux, dengan beberapa
worker Uvicorn:

```ini
# /etc/systemd/system/sap-middleware.service
[Unit]
Description=SAP BAPI Middleware
After=network.target postgresql.service

[Service]
Type=simple
User=appuser
WorkingDirectory=/srv/sap_middleware_bapi
EnvironmentFile=/srv/sap_middleware_bapi/.env
ExecStart=/srv/sap_middleware_bapi/.venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 --port 8000 --workers 4
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sap-middleware
sudo systemctl status sap-middleware
```

Lalu proxy dari Nginx ke `127.0.0.1:8000` dan aktifkan HTTPS (mis. lewat
Let's Encrypt/Certbot). Contoh minimal blok Nginx:

```nginx
server {
    listen 443 ssl;
    server_name middleware.contoh.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Skalabilitas & operasional

- **Multi-worker**: tambah `--workers N` pada Uvicorn/Gunicorn untuk
  memanfaatkan banyak core CPU (setiap worker punya `BAPIClient`/pool RFC
  sendiri).
- **Health check**: gunakan `GET /health` sebagai liveness/readiness probe
  (Docker healthcheck, Kubernetes probe, load balancer, dll.).
- **Migrasi skema**: proyek ini pakai `Base.metadata.create_all()` (skema
  sederhana, auto-create). Untuk perubahan skema di produksi dengan data
  yang sudah ada, disarankan menambahkan Alembic agar migrasi terkontrol.
- **Backup**: karena semua data hasil sync tersimpan di Postgres, cukup
  backup Postgres secara berkala (`pg_dump`/snapshot terkelola).

## Penggunaan API

Semua endpoint (kecuali `GET /health` dan endpoint `GET` pembacaan data)
membutuhkan header `X-API-Key` yang nilainya harus sama dengan `API_KEY`
di `.env`.

| Method | Endpoint | Auth | Keterangan |
|---|---|---|---|
| GET | `/health` | tidak | Status aplikasi + mode SAP (mock/real) |
| POST | `/sync/customers?max_rows=N` | ya | Tarik customer dari SAP → upsert ke `customers` |
| POST | `/sync/materials` | ya | Tarik detail material tertentu → upsert ke `materials` |
| POST | `/sync/sales-orders` | ya | Tarik sales order (header + item) → upsert ke `sales_orders`/`sales_order_items` |
| POST | `/bapi/call` | ya | Panggil BAPI apa pun secara langsung (escape hatch) |
| GET | `/customers?limit=N` | tidak | Baca data customer yang tersimpan di Postgres |
| GET | `/materials?limit=N` | tidak | Baca data material yang tersimpan di Postgres |
| GET | `/sales-orders?limit=N` | tidak | Baca data sales order yang tersimpan di Postgres |

> Endpoint `GET` pembacaan data sengaja tidak diberi auth di contoh ini
> agar mudah dicoba; untuk produksi, tambahkan proteksi yang sama
> (`Depends(require_api_key)`) atau letakkan di belakang API gateway sesuai
> kebutuhan keamanan Anda.

Dokumentasi interaktif lengkap (request/response schema, coba langsung dari
browser) selalu tersedia di **`/docs`** (Swagger UI) dan **`/redoc`**
selama aplikasi berjalan.

### Contoh pemakaian (curl)

```bash
# Health check
curl http://localhost:8000/health

# Sinkronisasi customer dari SAP -> Postgres
curl -X POST "http://localhost:8000/sync/customers?max_rows=50" \
     -H "X-API-Key: change-me"

# Sinkronisasi material tertentu
curl -X POST http://localhost:8000/sync/materials \
     -H "X-API-Key: change-me" -H "Content-Type: application/json" \
     -d '{"material_numbers": ["MAT-100", "MAT-200"]}'

# Sinkronisasi sales order milik customer tertentu
curl -X POST http://localhost:8000/sync/sales-orders \
     -H "X-API-Key: change-me" -H "Content-Type: application/json" \
     -d '{"customer_number": "1000000000"}'

# Baca data yang sudah tersimpan di Postgres
curl "http://localhost:8000/customers?limit=20"
curl "http://localhost:8000/materials?limit=20"
curl "http://localhost:8000/sales-orders?limit=20"

# Panggil BAPI apa pun secara langsung
curl -X POST http://localhost:8000/bapi/call \
     -H "X-API-Key: change-me" -H "Content-Type: application/json" \
     -d '{"bapi_name": "BAPI_CUSTOMER_GETLIST", "params": {"MAXROWS": 10}}'
```

Contoh respons `POST /sync/customers`:

```json
{
  "status": "SUCCESS",
  "bapi_name": "BAPI_CUSTOMER_GETLIST",
  "records_synced": 50,
  "started_at": "2026-07-27T20:53:46.864283",
  "finished_at": "2026-07-27T20:53:46.891227",
  "message": null
}
```

Jika `X-API-Key` salah/tidak dikirim, API membalas `401 Unauthorized`. Jika
BAPI di SAP gagal (RETURN bertipe error), endpoint sync tetap membalas
`200` dengan `"status": "FAILED"` dan `message` berisi pesan error dari
SAP (detail lengkap juga dicatat di tabel `sync_logs`); khusus
`POST /bapi/call`, kegagalan BAPI dibalas sebagai `502 Bad Gateway` dan
kegagalan koneksi SAP sebagai `503 Service Unavailable`.

## Menjalankan test

```bash
pip install -r requirements.txt
createdb sap_middleware_test   # sekali saja, butuh Postgres lokal
pytest -v
```

Test memakai `SAP_MOCK_MODE=true` sehingga tidak butuh koneksi SAP, tapi
tetap butuh Postgres asli karena upsert memakai fitur
`INSERT ... ON CONFLICT` khusus dialek PostgreSQL.

## Troubleshooting

| Gejala | Kemungkinan penyebab & solusi |
|---|---|
| `connection to server ... failed` saat start | Postgres belum jalan atau kredensial di `.env` salah. Cek `POSTGRES_HOST/PORT/USER/PASSWORD/DB`, pastikan `pg_isready` sukses. |
| `FATAL: database "sap_middleware" does not exist` | Database belum dibuat — aplikasi hanya auto-create **tabel**, bukan database-nya. Buat dulu manual: `psql -U postgres -h localhost -c "CREATE DATABASE sap_middleware;"` (lihat [Opsi B langkah 1](#opsi-b--instalasi-lokal-tanpa-docker)), pastikan namanya sama persis dengan `POSTGRES_DB` di `.env`. |
| `401 Unauthorized` di endpoint `/sync/*` atau `/bapi/call` | Header `X-API-Key` tidak dikirim atau nilainya tidak sama dengan `API_KEY` di `.env`. |
| `ModuleNotFoundError: pyrfc` | Wajar jika `SAP_MOCK_MODE=false` tapi belum `pip install -r requirements-sap.txt` dan SAP NW RFC SDK belum terpasang. Untuk mode mock, dependency ini memang tidak dipasang. |
| `records_synced` selalu 0 padahal SAP punya data | Pastikan `SAP_MOCK_MODE=false` untuk data SAP asli (mode mock hanya mengembalikan data contoh tetap); cek juga `sync_logs.message` untuk pesan error BAPI. |
| Test gagal dengan error terkait `ON CONFLICT`/dialek SQL | Test butuh PostgreSQL asli (bukan SQLite); pastikan database `sap_middleware_test` sudah dibuat dan bisa diakses. |
| Container `app` restart terus di Docker Compose | Jalankan `docker compose logs app` untuk lihat traceback; penyebab umum: Postgres belum ready (harusnya sudah ditangani `depends_on: condition: service_healthy`) atau `.env` belum di-copy dari `.env.example`. |
