# แผนและประตูตรวจรับ

1. M0: architecture/ADR/contracts/tooling/Compose/CI; รัน config, lint, types และ bootstrap test
   ก่อนพัฒนา M1; บันทึกข้อจำกัด environment แยกจากผลผ่านจริง
2. M1: workload/link traces → discrete-event queue/transport → baselines → metrics → CLI/replay
   → hand-calculated tests → deterministic output checks; ไม่มี SAFER candidate ในขั้นนี้
3. M2: SAFER policy/deficit และ benchmark 4 policies × S0–S6 × อย่างน้อย 10 seeds พร้อม plots
4. M3: MQTT/SQLite/HTTP/PostgreSQL จริงและ crash/retry tests
5. M4: Next.js Dashboard และ bounded experiment controls
6. M5: quality/performance/clean checkout verification
7. M6: Cloud เฉพาะเมื่ออนุญาตและเตรียมค่าใช้จ่าย/cleanup แล้ว
8. M7: research report พร้อม negative results และ reproducible artifacts

ขอบเขตคำขอปัจจุบันหยุดที่ M1 ไม่เชื่อม GitHub remote ไม่ deploy และไม่สรุปว่า SAFER ชนะ
สถานะและหลักฐานแต่ละ milestone อยู่ใน `docs/milestones/`.
