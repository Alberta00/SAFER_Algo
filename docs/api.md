# API contract (แผน M3 ยังไม่มี HTTP server)

`POST /api/v1/ingest` ต้อง authenticated และจำกัด body size รับ run_id, message_id,
device_id, category, source_created_at_utc, payload, schema_version และ category metadata
EVENT ต้องมี severity/deadline; LIVE_STATE ต้องมี state_key/sample timestamp แบบ UTC
message_id dedup ภายใต้ run_id; ID เดิมและเนื้อหาเดิมตอบ ACKED duplicate=true หลัง commit
เนื้อหาขัดแย้งตอบ 409 ไม่ overwrite; DB error ตอบ 5xx ไม่ ACK; ไม่มี auth ตอบ 401/403
schema validation 422, oversize 413. ต้องสร้าง OpenAPI จาก FastAPI implementation ใน M3

ACK response: message_id, status=ACKED, duplicate, server_received_at_utc
read APIs: `/healthz` liveness, authenticated `/api/v1/status`, `/messages` แบบ pagination,
`/experiments`, `/experiments/{run_id}`, `/experiments/{run_id}/series`.
POST experiments จำกัด local/dev หรือ role และ bounded config. ไม่มี endpoint เปิดใน M0/M1
