# SAFER — Software-Only IoT Scheduling Research

เริ่มพัฒนา M0/M1: deterministic simulation ก่อน network integration จริง ไม่มี hardware
อ่าน [Architecture](docs/architecture.md), [แผน](docs/plan.md), [ADR](docs/decisions.md),
[ข้อจำกัด](docs/limitations.md) และ [API ที่วางแผนไว้](docs/api.md).

## เริ่มบน Windows / VS Code

เปิด VS Code → File → Open Folder → เลือกโฟลเดอร์ `SAFER_Algo` นี้
ตำแหน่งปัจจุบัน: `C:\Users\DELL\Desktop\GithubDesk\SAFER\SAFER_Algo`
รันคำสั่งทั้งหมดด้านล่างจากโฟลเดอร์นี้
Codex session ปัจจุบันเข้าถึงโฟลเดอร์นี้ได้แล้ว สามารถอ่าน/แก้ไฟล์และรัน terminal commands
ไฟล์จะปรากฏใน VS Code โดยไม่ต้องเปิด remote desktop หรือส่งรหัสผ่าน

PowerShell (แนะนำ Python 3.12; รองรับ 3.11):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
npm.cmd ci
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
npm.cmd run lint
npm.cmd run typecheck
docker compose config --quiet
```

Linux/WSL ใช้ `.venv/bin/python` แทน `.venv\Scripts\python.exe` และ `npm` แทน `npm.cmd`
Docker Desktop ต้องเปิด Linux Engine ก่อน build/run; Compose ไม่มี exposed ports

```powershell
docker compose --profile test run --build --rm tests
```

## รันการทดลอง M1

```powershell
.\.venv\Scripts\python.exe -m safer_sim run --scenario S1 --algorithm fifo --seed 42 --output results/s1-fifo
.\.venv\Scripts\python.exe -m safer_sim run --trace results/s1-fifo/trace.json --algorithm priority --output results/s1-priority
.\.venv\Scripts\python.exe -m safer_sim run --trace results/s1-fifo/trace.json --algorithm edf --output results/s1-edf
.\.venv\Scripts\python.exe -m safer_sim run --config experiments/configs/smoke.json --algorithm fifo --output results/smoke
```

S1 default จำลอง outage จริง 600 วินาทีบน simulation clock ภายใน observation 720 วินาที
ไม่ต้องรอเวลาจริง 12 นาที; แต่ละ policy ควรใช้ output directory แยกกัน
`--trace` ห้ามใช้ร่วมกับ config/seed/scenario override เพื่อไม่ให้ replay เปลี่ยน input เงียบ ๆ
S0–S6 มี input profiles สำหรับทดสอบ Core; matrix benchmarking และ SAFER เป็น M2
S4 บังคับ latency อย่างน้อย 350ms, jitter อย่างน้อย 150ms, loss อย่างน้อย 5%
S5 เพิ่ม EVENT burst 5 วินาทีหลัง restore; S6 ใช้ interval ไม่เกิน 100ms กับ degraded capacity
รายละเอียดค่าที่ใช้จริงดู `trace.json` และ [วิธีวัด](docs/experiment_methodology.md)

ไฟล์ผลจาก engine:

- `metrics.json`: identity/config + metrics จริงของ simulation
- `trace.json`: input replay ครบทั้ง workload และ link segments
- `messages.csv`, `attempts.csv`: timestamps, retry, commit, ACK และ fault รายข้อความ
- `series.json`, `backlog.csv`: queue/throughput/oldest age over time
- `metadata.json`: wall-clock start time และ Git commit (null หากยังไม่มี repository)

seed/config/trace/algorithm เดิมต้องได้ทุกไฟล์เหมือนกันระดับ bytes ยกเว้น metadata.json

```powershell
.\.venv\Scripts\python.exe -m safer_sim run --scenario S1 --algorithm fifo --seed 42 --output results/s1-repeat
.\.venv\Scripts\python.exe scripts/verify_outputs.py results/s1-fifo results/s1-repeat
```

AoI เริ่มที่ first delivered sample ต่อ state key และรายงาน coverage; event ที่ยังไม่ถึง deadline
เมื่อจบการทดลองรายงาน censored; incomplete recovery ใช้ null ไม่แสดงเป็นสำเร็จ

Docker CLI (เปิด Docker Desktop Linux Engine ก่อน):

```powershell
docker compose run --build --rm simulator run --scenario S1 --algorithm fifo --seed 42 --output /results/s1-fifo
```

บน Linux ให้สร้าง `results/` และกำหนดสิทธิ์ให้ UID 10001 เขียนได้ก่อน bind mount
ไม่มีการใช้ MQTT/HTTP/DB ใน M1; [ข้อจำกัด](docs/limitations.md) ระบุงาน milestone ถัดไป
รายงาน M0/M1 อยู่ใน [docs/milestones](docs/milestones)

CI workflow เตรียมไว้ใน `.github/workflows/ci.yaml` แต่ยังไม่ได้ส่งขึ้น GitHub
ไม่มีการเลือก license จนกว่าเจ้าของโปรเจกต์ตัดสินใจ
