# sap_middleware_bapi

Middleware Python untuk menarik data dari SAP lewat **BAPI/RFC** dan menyimpannya
ke **PostgreSQL**, diekspos lewat REST API (FastAPI) sehingga bisa dipicu manual
atau dijadwalkan otomatis.

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
```

## Menjalankan dengan Docker

```bash
cp .env.example .env
docker compose up --build
```

API akan tersedia di `http://localhost:8000` (docs interaktif di `/docs`).

## Menjalankan secara lokal (tanpa Docker)

```bash
python -m venv .venv && source .venv/bin/activate
window .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Pastikan Postgres jalan dan DB sudah dibuat, lalu:
cp .env.example .env   # sesuaikan kredensial Postgres

uvicorn app.main:app --reload
```

## Menghubungkan ke SAP asli (bukan mock)

`pyrfc` adalah binding C ke **SAP NetWeaver RFC SDK**, library proprietary
milik SAP yang tidak didistribusikan lewat PyPI. Untuk pakai koneksi SAP
sungguhan:

1. Download "SAP NW RFC SDK" dari SAP Support Portal (butuh S-user).
2. Install SDK tersebut di server middleware, lalu set env `SAPNWRFC_HOME`
   dan `LD_LIBRARY_PATH` sesuai lokasi instalasinya.
3. `pip install -r requirements-sap.txt`
4. Set di `.env`:
   ```
   SAP_MOCK_MODE=false
   SAP_ASHOST=<application server SAP>
   SAP_SYSNR=<system number>
   SAP_CLIENT=<client>
   SAP_USER=<rfc user>
   SAP_PASSWD=<password>
   ```

Selama `SAP_MOCK_MODE=true`, tidak ada dependency SAP yang dibutuhkan sama
sekali — semua panggilan BAPI dilayani oleh `app/sap/mock_client.py`.

## Contoh pemakaian API

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
curl http://localhost:8000/customers
curl http://localhost:8000/materials
curl http://localhost:8000/sales-orders

# Panggil BAPI apa pun secara langsung
curl -X POST http://localhost:8000/bapi/call \
     -H "X-API-Key: change-me" -H "Content-Type: application/json" \
     -d '{"bapi_name": "BAPI_CUSTOMER_GETLIST", "params": {"MAXROWS": 10}}'
```

## Menjalankan test

```bash
pip install -r requirements.txt
createdb sap_middleware_test   # sekali saja, butuh Postgres lokal
pytest
```

Test memakai `SAP_MOCK_MODE=true` sehingga tidak butuh koneksi SAP, tapi
tetap butuh Postgres asli karena upsert memakai fitur
`INSERT ... ON CONFLICT` khusus dialek PostgreSQL.
