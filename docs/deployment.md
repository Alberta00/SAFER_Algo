# การรันและ deployment

M0/M1 รันเป็น local CLI และ Compose เท่านั้น ไม่มี API หรือ UI ที่เปิด port
เปิด Docker Desktop และ Linux Engine แล้วใช้คำสั่งใน README
runtime ของ simulator ปิด network; ระหว่าง build ต้องดาวน์โหลด Python image/dependencies

ผลบนเครื่องนี้: Compose config ผ่าน; container build เคยดาวน์โหลด/ติดตั้ง Python packages ได้
แต่ Docker storage error ที่ `/var/lib/docker/buildkit/metadata_v2.db: read-only file system`
จึงยังไม่ถือว่า container tests ผ่าน. ต้องให้เจ้าของตรวจสถานะ Docker Desktop/WSL และพื้นที่ดิสก์
แล้วรันคำสั่งเดิมซ้ำ ไม่ควรใช้ prune/reset/delete volume โดยไม่ตรวจข้อมูลที่มีอยู่

M6 เป็นแผนในอนาคต: deploy เฉพาะ stateless FastAPI/Dashboard และ managed PostgreSQL
เมื่อได้รับอนุญาตพร้อม budget, Secret Manager, least privilege และ teardown/rollback guide
Local Edge/SQLite/MQTT ต้องไม่อาศัย ephemeral storage ของ Cloud Run
ยังไม่มี cloud resources หรือ credential ใดถูกสร้าง
