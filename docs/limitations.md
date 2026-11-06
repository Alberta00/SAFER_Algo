# ข้อจำกัด

- M0/M1 เป็น software simulation เท่านั้น ยังไม่มี MQTT, SQLite durability, HTTP, PostgreSQL, UI
- ยังไม่มี SAFER candidate, benchmark matrix, confidence interval หรือข้อสรุปวิจัยว่า policy ใดดีกว่า
- หนึ่ง in-flight request; payload service budget ไม่รวม TCP/TLS/HTTP/ACK bytes; packetization ไม่จำลอง
- Memory queue ไม่ทดสอบ restart/disk full จริง; fail loudly เมื่อ queue limit เกิน
- ยังไม่วัด CPU/RSS/SQLite size และไม่อ้าง resource cost จาก simulation clock
- Docker build ล้มที่ storage ของ Engine: metadata_v2.db read-only file system;
  Compose config ผ่าน แต่ยังยืนยัน container runtime/Python 3.12 tests ไม่ได้
- ยังไม่ตรวจ clean clone, GitHub Actions execution หรือ Python 3.12 บนเครื่องนี้
- ไม่มี public endpoint, cloud resource หรือการแก้ GitHub remote
- Stop-and-wait หนึ่ง request รวมเวลารอ ACK ทำให้ throughput ต่ำกว่า nominal bandwidth ได้มาก
  ไม่ใช้ผลนี้อ้างว่า link utilization เหมาะสมแล้ว; เพิ่ม parallel transport ใน milestone หลัง M1
- คิวและ backlog series scan แบบ linear ต่อ event เหมาะ correctness-first prototype
  ยังไม่รับรองประสิทธิภาพ workload ขนาดใหญ่นานหลายชั่วโมง
