# Báo cáo kiểm thử bề mặt Warp (read-only)

- Thời điểm: 2026-09-25
- Chế độ: **quan sát client + checklist server**
- Không thực hiện: ghi memory, gọi hàm warp, gửi packet, auto-warp

JSON chi tiết: `warp-surface-test-report.json`

## 1. Kết quả dump IL2CPP (tĩnh)

| Kiểm tra | Kết quả |
|---|---|
| Class `MapServerMove` | PASS |
| UI `TeleportWindow` / `MTeleportWindow` | PASS |
| `TableWorld.Move` | PASS |
| `TableWorld.Gate` | PASS |
| Field `Game._MapServerMove` @ `0xC0` | PASS |
| Field `Game._World` @ `0x200` | PASS |
| `LocalCharacterBody.AutoMoveWorking` | PASS |
| Chữ ký `MapServerMove(... IpAddress, ServerPort, ServerCode, keys)` | PASS |
| `MTeleportWindow.MaxPinnedWorld = 5` | PASS |

**Kết luận dump:** client có đủ 3 bề mặt liên quan chuyển map: Teleport UI, bảng Move/Gate, và `MapServerMove` (đổi map-server).

## 2. Kết quả quan sát process live (5 MEGAMU)

Tất cả 5 process: **PASS** đọc object graph.

| PID | Map (`SceneIndex`) | Coord live | AutoMove | MapServerMove.active | AuthKeys |
|---|---|---|---|---|---|
| 4732 | 2 (Devias) | 91,197 | 0 | 0 | có pointer |
| 6128 | 2 (Devias) | 91,196 | 0 | 0 | có pointer |
| 15160 | 2 (Devias) | 90,197 | 0 | 0 | có pointer |
| 25616 | 2 (Devias) | 91,198 | 0 | 0 | có pointer |
| 26556 | 2 (Devias) | 93,199 | 0 | 0 | có pointer |

Quan sát thêm:

- `Game.Instance`, `_World`, `_Player`, `_MapServerMove` đều resolve được
- Lúc idle: `MapServerMove._IsActive = 0`, `IsServerChange = 0`
- `AutoMoveWorking = 0`, `AutoMoveType = -1`
- `LastServerCoordinates` đang `(0,0)` trên mẫu này (sentinel / chưa sync hữu ích)
- `AuthKeys` pointer khác null trên mọi client → object MSM đã khởi tạo

**Kết luận live:** bề mặt warp **đọc được ổn định**. Đây là bằng chứng threat Bậc 2 (quan sát), chưa phải bằng chứng warp thành công từ tool.

## 3. Việc chưa kiểm được trong phiên này

| Hạng mục | Lý do |
|---|---|
| Server accept/reject warp thiếu điều kiện | Cần môi trường server/test harness nội bộ |
| Teleport UI → request thật | Cần thao tác trong game + log server |
| Gate enter ngoài tầm / sai map nguồn | Cần QA trên server |
| MapServerMove khi đổi map-server | Cần case chuyển map sang server khác |
| Auto-warp / bỏ UI | Ngoài phạm vi; không chạy |

## 4. Checklist server (team tự chạy)

Điền Pass/Fail trên môi trường test. Mọi case đều kỳ vọng **server là nguồn chân lý**.

### A. Teleport UI / lệnh move hợp lệ

| ID | Case | Kỳ vọng |
|---|---|---|
| T1 | Teleport đúng đích, đủ level/zen/item | Accept, nhân vật vào đúng map/tọa độ server |
| T2 | Thiếu zen / thiếu ticket | Reject, map không đổi |
| T3 | Level thấp hơn yêu cầu | Reject |
| T4 | Dest map id không có trong bảng hợp lệ | Reject |
| T5 | Spam teleport liên tục | Rate-limit / reject / kick tùy policy |
| T6 | Teleport khi đang combat / trade / dead (nếu rule cấm) | Reject đúng rule |

### B. Gate

| ID | Case | Kỳ vọng |
|---|---|---|
| G1 | Đứng đúng ô gate, đủ điều kiện | Accept |
| G2 | Ngoài vùng gate, vẫn gửi request vào map đích | Reject |
| G3 | Sai map nguồn so với gate config | Reject |
| G4 | Gate event đã đóng | Reject |

### C. MapServerMove (đổi map-server)

| ID | Case | Kỳ vọng |
|---|---|---|
| M1 | Chuyển map hợp lệ cần đổi GS | Server cấp session/keys mới đúng quy trình |
| M2 | Client tự ý “active” MSM / dùng keys cũ | Reject / disconnect |
| M3 | Sai `ServerCode` / port / IP không thuộc cluster | Reject |
| M4 | Replay auth keys | Reject |
| M5 | Báo đã ở map B trước khi GS xác nhận | Server state thắng; client bị resync |

### D. Toàn cục

| ID | Case | Kỳ vọng |
|---|---|---|
| X1 | Mọi cổng (UI/Gate/MSM) đi chung validator map | Không có cổng bypass |
| X2 | Log from-map, to-map, account, reason | Đủ để điều tra |
| X3 | Combat/loot không tin `SceneIndex` client | Chỉ tin server world |

## 5. Khuyến nghị ưu tiên vá

1. **P0** — Validator warp chung cho Teleport / Gate / MapServerMove  
2. **P0** — Reject đích/điều kiện thiếu; không tin state client  
3. **P1** — Rate-limit + log risk theo pattern multi-box warp  
4. **P1** — Kiểm tra auth keys MapServerMove (one-time / expiry)  
5. **P2** — Telemetry khi nhiều process cùng máy đổi map cùng nhịp

## 6. Cách dùng báo cáo này

1. Giữ file JSON/MD trong repo như evidence “client surface đọc được”  
2. Giao checklist mục 4 cho Server/QA  
3. Sau mỗi patch client: chạy lại script quan sát xem offset/RVA còn sống không  
4. Đo thành công bảo mật bằng số case reject trên server, không bằng “user không đọc được RAM”
