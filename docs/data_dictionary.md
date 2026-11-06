# พจนานุกรมข้อมูล

เวลาใน core เป็น integer ms หลัง epoch `2026-11-06T00:00:00Z`; ไม่มีเวลาจากเครื่องใน metrics
schema ของ trace กับ API แยกกันโดยเจตนา API adapter จะเพิ่มใน M3

| Field | ความหมาย |
|---|---|
| message_id | UUIDv4 reproducible จาก seed, unique ภายใน trace |
| device_id / sequence_no | อุปกรณ์จำลอง / ลำดับที่เพิ่มต่ออุปกรณ์ |
| category | EVENT, LIVE_STATE, HISTORY |
| created_ms / queued_ms | เวลาสร้าง / เข้าคิว (M1 เท่ากัน) |
| payload_bytes | ขนาดข้อมูลสำหรับ serialization budget ไม่รวม protocol overhead |
| payload_value | ค่า sensor ที่ generator สร้างจริงจาก seed |
| deadline_ms / severity | metadata ที่ EVENT ต้องมี; พ้น deadline ยังเก็บข้อความ |
| state_key / sample_ms | metadata ของ LIVE_STATE สำหรับ AoI |
| first_sent_ms / committed_ms / acked_ms | ส่งครั้งแรก / remote model รับครั้งแรก / Edge รับ ACK |
| attempt_count / next_attempt_ms | จำนวนครั้งที่ส่ง / เวลาที่ retry ได้ |
| config_hash / trace_hash | SHA-256 canonical JSON สำหรับ reproducibility |
| mode | `simulated` ใน M1; `integration_emulated` สงวนสำหรับ M3 |

สถานะ queue คำนวณจาก record: queued/retryable, in-flight, ACKED; ไม่มีการลบรายการสำเร็จ
Remote simulation เก็บ first commit ต่อ ID เท่านั้น ACK retry ไม่เพิ่ม unique received count
