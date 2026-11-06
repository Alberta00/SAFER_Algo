# วิธีทดลอง deterministic core v1

## Clock, workload และ observation

ใช้ integer milliseconds ช่วง observation [0, duration_ms]; สร้างข้อความเฉพาะเวลา
created_ms < duration_ms. ไม่ใช้ wall clock; เวลาจริงอยู่เฉพาะ metadata.json
workload เป็น periodic samples ต่อ device แบ่ง EVENT ตาม event_probability แล้วสลับ
LIVE_STATE/HISTORY สำหรับ non-events; payload size สุ่ม uniform ตาม config
state key หนึ่งต่อ device; sequence เพิ่มทีละหนึ่ง; ไม่มี compaction

trace.json เก็บ config, messages, link segments และ seed; algorithm ไม่อยู่ใน trace
จึง replay ด้วย scheduler อื่นได้ด้วย input เดิมและ trace_hash เท่ากัน
link jitter/loss ใช้ SHA-256(seed, global attempt ordinal, field) ให้แต่ละ policy ได้
random variates ลำดับเดียวกัน แม้การเลือกข้อความ/เวลาออกส่งอาจต่างกัน

## Event order และ transport

เมื่อเวลาเท่ากัน: link transition/recovery snapshot → arrivals → remote commits → ACKs
→ timeouts → dispatch. FIFO tie-break (queued_ms, trace input ordinal).
links เป็น segments [start,end); ที่ observation end ใช้ segment สุดท้ายเพื่อตัดสินผล
หนึ่ง request ครอง in-flight slot จน ACK หรือ timeout. serialization เป็น payload bits /
bandwidth แบบ piecewise ตาม segment ปัด ms ขึ้น; downstream delay เป็น one-way latency
บวก seeded uniform jitter ไม่ติดลบ; ACK ใช้ one-way delay เดียวกัน ไม่คิด ACK bytes

down ระหว่าง serialize/propagate ทำให้ไม่ commit; down เฉพาะทาง ACK ทำให้ remote
ยังถือว่ารับแล้ว แต่ Edge ต้อง retry. loss probability ของ data และ ACK แยกกัน
timeout เริ่มหลัง serialization (M1 ไม่จำลอง connection setup stall);
timeout ที่สั้นกว่า round trip ทำให้ retry ได้ แต่ scheduled late commit/ACK ยังเกิดจริง
ACK ของ attempt เก่าทำให้ข้อความ ACKED ได้; ไม่ยกเลิก commit ที่ส่งออกไปแล้ว
ไม่เลือกข้อความ ACKED อีก และไม่ insert ซ้ำ. backoff exponential capped
คงลำดับ FIFO เดิมเมื่อ retry. link down ไม่เริ่มส่งใหม่. หมดเวลาทดลองคง pending ไว้

## Metrics

- Event latency = first remote commit - created_ms เฉพาะที่ commit แล้ว;
  mean และ p50/p95/p99 ใช้ linear interpolation (n-1)*q; null ถ้ายังไม่มี delivered event
- Deadline miss: commit > deadline หรือยังไม่ commit และ deadline <= observation end;
  เท่ากับ deadline ถือว่าทัน; denominator คือ events ทั้งหมดใน observation
  event ที่ deadline ยังมาไม่ถึงและไม่ delivered รายงาน censored แยก ไม่ถือว่าทันแล้ว
- AoI ต่อ state_key: เริ่มวัดที่ first live commit (ไม่มี initial state สมมติ),
  integral ของ t - latest delivered sample; ไม่ลด latest sample เมื่อเก่ามาถึงทีหลัง
  time-average หารด้วย covered duration, aggregate แบบเฉลี่ยเท่ากันต่อ observed key
  รายงาน coverage และ keys ที่ยังไม่มี sample ด้วย; null ถ้าไม่มี covered duration
- History recovery snapshot ก่อน arrivals ที่ restore timestamp: HISTORY ที่ created < restore
  และยังไม่ ACK ในขณะนั้น; คำนวณครบชุดแยกแต่ละ restoration ไม่รวม traffic หลัง restore
  recovery time = last target ACK - restore; null/status=incomplete ถ้ายังไม่ครบ
  empty target: completeness=null, status=empty; ไม่สร้างหลักฐานว่า recover สำเร็จ 100%
- throughput = unique ACKed payload bytes / observation seconds; unique commits กับ ACKs แยกกัน
- max_wait_ms = ACK - queued หรือ observation end - queued สำหรับ pending (รวม service/retry)
  ไม่ทิ้งข้อความที่รอนาน และรายงาน oldest_pending_age_ms แยก
- backlog series เก็บเมื่อ state เปลี่ยน: pending count/bytes, acked bytes, oldest pending age

ไม่มี warmup นอกจาก per-key AoI first-delivery convention. M1 ยังไม่รายงาน AoI p95,
service-share windows, resource cost, confidence intervals หรือ comparative research conclusions
hand-calculated fixtures เป็น unit-test input; ผล CLI เป็น engine output จริง ไม่ใช่ mock metrics
