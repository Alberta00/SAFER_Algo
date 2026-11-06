# ADR และสมมติฐาน

## ADR-001 — แยก deterministic core จาก integration
ใช้ stdlib Python runtime ไม่มี dependency สำหรับ simulator; pytest/Ruff/mypy เฉพาะ dev.
เริ่มที่ in-memory queue ใน M1 ตาม milestone ก่อน durability และ network I/O ของ M3.
ไม่สร้าง service เปล่าหรือ Dashboard ที่แสดงค่าปลอมเพื่อให้ดูครบ stack.

## ADR-002 — Python compatibility
Docker/CI ใช้ Python 3.12 เป็นค่าเริ่มต้นตามสเปก และ CI ตรวจ 3.11 เพิ่มด้วย
เครื่องผู้ใช้มี 3.11.9 จึงรองรับ >=3.11 เพื่อทดสอบได้ทันทีโดยไม่แก้ Python ระบบ
ไม่มี syntax หรือผลลัพธ์ที่ตั้งใจขึ้นกับ minor version; ต้องยืนยันผ่าน CI/container ภายหลัง

## ADR-003 — เวลาและ random
ใช้ integer milliseconds ปัด serialization ขึ้น (อย่างน้อย 1 ms), epoch อ้างอิง UTC คงที่
แบ่ง random stream ของ workload และ link; loss/jitter อิง seed + attempt ordinal
ไม่อิง algorithm/UUID แบบสุ่มจากระบบ. IDs reproducible เป็น UUIDv4 จาก seeded bits
ไม่ใช่ security identifiers. ส่งออก trace เพื่อ replay และ hash trace เดียวกันทุก policy

## ADR-004 — ขอบเขต transport เริ่มต้น
M1 มีหนึ่ง non-preemptive in-flight request; capacity เปลี่ยนระหว่างส่งคิดจากแต่ละ segment
link down ระหว่างส่ง/propagation/ACK ทำให้ attempt ล้มเหลวตามช่วงนั้น
retry exponential backoff มี cap; คง queue order เดิม; ไม่ทิ้ง expired events
queue จำกัดจำนวน config ได้และ fail loudly เมื่อเกิน ไม่ทำ silent compaction
SAFER, parallel transport และ real durable commit ต้องทำ milestone ถัดไป

## ADR-005 — repository และ license
โฟลเดอร์เริ่มต้นไม่ใช่ Git repository จึงยังไม่มี commit hash/branch/PR/remote
บันทึก git_commit เป็น null อย่างชัดเจน ไม่เลือก license แทนเจ้าของโปรเจกต์
dependency versions pin ใน pyproject และ npm lock; container base tag ยังไม่ pin digest

## ADR-006 — ย้ายเข้าที่เก็บ Git ของเจ้าของโปรเจกต์
หลังการส่งมอบ M0/M1 เจ้าของสร้าง repo ที่ `SAFER/SAFER_Algo` และขอให้ย้ายโปรเจกต์เข้าไป
ย้าย source/config/tests/docs และผลรันจริงเข้า repo โดยคง `.git` และ `.gitattributes` เดิม
คัดลอก project spec เป็นเอกสารอ้างอิงใน repo; เอกสารสัมภาษณ์และไฟล์ต้นฉบับอยู่ที่ parent เดิม
สร้าง `.venv` ใหม่ภายใน repo เพราะ environment เดิมมี absolute paths ไม่เหมาะกับการย้ายตรง ๆ
สถานะไม่มี Git repository ในรายงาน M0/M1 หมายถึงเวลาตรวจครั้งแรกก่อนการย้ายครั้งนี้
ยังไม่ stage/commit/push หรือแก้ Git remote
