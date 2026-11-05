# Hoàn thiện chức năng "vứt đồ rác" của Moss Merchant

> Ngày: 05/11/2026 · Phạm vi: `meg_direct_engine.py`, `meg_gui.py`, `config/megamu_offsets.json`, `megamu_offsets.json`, `tools/verify_offsets.py`, test.

---

## 1. Kết quả nghiên cứu (bằng chứng từ binary thật)

### 1.1. Gói tin drop của game đã được xác nhận — app gửi ĐÚNG

Disassemble `GameAssembly.dll` (build đang cài, khớp `dump_current/dump.cs`) tại **`0x1449740`** — hàm drop thật của client (`UserInventory.KCEAGAMOOOO(int slot, Coord* target)`):

```asm
0x1449975  lea edx, [r9 + 0x23]      ; opcode 0x23
0x1449979  call 0x120ed40            ; khởi tạo packet header (C1 06 23)
0x144997e  mov  byte ptr [rsp+0x7d], sil   ; buffer[5] = slot
0x144998c  movzx eax, byte ptr [rdi+0x10]  ; buffer[3] = Coord.X
0x1449992  mov  byte ptr [rsp+0x7b], al
0x1449996  movzx eax, byte ptr [rdi+0x14]  ; buffer[4] = Coord.Y
0x144999a  mov  byte ptr [rsp+0x7c], al
0x14499ed  call 0x11f9280            ; gs_send(gs, packet, 0, 0, 0)
```

⇒ Payload chuẩn là **`C1 06 23 X Y slot`** — trùng khớp 100% với `sendDropPacket()` hiện có (`meg_direct_engine.py`). **Lỗi không nằm ở định dạng gói.**

### 1.2. Client có 2 lớp "cổng" trước khi gửi, và server chặn ở safe-zone

Ngay đầu hàm drop:

```asm
0x14497c7  call 0x1077980            ; get_user_2fa() / account
0x14497de  lea  edx, [r9 + 0xd]      ; tham số 13
0x14497e2  call 0x1402d00            ; bool Check(...) -> nếu false thì RETURN, không gửi gói
```

- Nếu `0x1402d00` trả `false`, client **im lặng bỏ qua** — không gói tin, không log.
- App hiện gửi packet trực tiếp nên **bỏ qua** cổng này, nhưng server MU vẫn từ chối rơi đồ trong **safe-zone** (làng/Elbeland). Moss NPC đứng ở `(22,225)` Elbeland — tức **luôn ở trong vùng cấm rơi đồ**.
- Hệ quả: nút "Ném" gửi gói thành công nhưng hòm đồ không đổi; code cũ quy kết "máy chủ chưa cho phép rơi" nhưng **không có phương án thay thế** ⇒ tính năng coi như không hoàn thiện.

### 1.3. App còn thiếu 3 thứ

| Thiếu | Hệ quả |
|---|---|
| Xác minh từng ô ngay sau khi gửi (code cũ chỉ đếm lại ở cuối, không retry theo ô) | Không biết ô nào bị từ chối, không báo được lý do |
| Phương án dự phòng khi không thể rơi đồ | Farm dừng khi hòm đầy |
| Chẩn đoán (GS còn sống? toạ độ? Merchant mở?) | Log chỉ nói chung chung, không hành động được |

---

## 2. Đã triển khai

### 2.1. Engine: pipeline `disposeJunkItems` (JS)

Thêm vào template Frida (`meg_direct_engine.py`):

- `readDisposalContext()` — thu thập `gsOk`, toạ độ nhân vật, `merchantOpen`, `mossOpen`.
- `runDropPass(slots, itemsArr, ctx, dx, dy)` — gửi `C1 06 23` cho từng slot, chờ 300 ms, **đọc lại RAM từng ô** để biết ô nào thực sự biến mất.
- `runSellPass(slots, itemsArr)` — gửi `C1 04 33` cho từng slot + xác minh tương tự.
- `disposeJunkItems(mode, protectedJson, category, includeExt, maxJunkLevel, maxBatch)`:
  1. Lọc ứng viên bằng đúng 3 guard cũ (slot ≥ 12, snapshot trước khi quay, `isItemProtected`).
  2. **Vứt** (2 lượt, lượt 2 đổi toạ độ `-1,+1`).
  3. Ô nào còn lại → nếu Merchant đang mở thì **bán**.
  4. Trả về JSON: `{cleaned, dropped, sold, total, failed, reason, gsOk, coord, merchantOpen, mossOpen, failedSlots, sendFailed, elapsedMs}`.
  5. `reason` ∈ `done | partial | drop_blocked | merchant_closed | no_gs_connection | send_failed | no_candidates | server_rejected | no_player | not_attempted | exception`.

`cleanInventoryJunk` cũ **giữ nguyên** (fallback + test cũ vẫn chạy).

### 2.2. Python: `clean_inventory_junk()` nâng cấp, tương thích ngược

- Map `method` → `mode`: `trash|drop|both → drop`, `sell → sell`, `auto → auto`.
- Gọi `disposeJunkItems` trước; nếu engine cũ không có hàm này thì fallback về `cleanInventoryJunk`.
- Thêm `dispose_junk_items(...)` làm API gọn cho GUI/script.

### 2.3. GUI: dùng auto + fallback bán + log chẩn đoán

- Vòng lặp quay (`start_moss`) và nhánh "quay hụt vì hòm đầy" chuyển từ `"trash"` sang **`"auto"`**.
- Thêm `_moss_log_disposal_failure(res)`: nói rõ *vì sao* — ví dụ
  `Server KHÔNG cho rơi đồ tại (22,225) — khu vực này là safe-zone…`.
- Thêm `_moss_try_sell_fallback(eng)`: khi vứt bị chặn → gọi `sell_moss_items_at_merchant()` (đi tới Merchant, bán, quay lại), **tối đa 1 lần/phiên** (`_moss_sell_escalated`), tránh vòng lặp vô tận.
- Nút "🗑️ Ném" thủ công giữ nguyên hành vi nhưng log có `reason`, `dropped/sold`.

### 2.4. Đồng bộ cấu hình offset

- `component_get_game_object` trong `megamu_offsets.json` (root) đã được đồng bộ về `0x45C8770` (trước đây root = `0x456AE90`, config = `0x45C8770` → tuỳ file được nạp mà chạy đúng/sai).

### 2.5. Công cụ mới: `tools/verify_offsets.py`

```powershell
python tools/verify_offsets.py --dll
```

- So từng RVA trong `config/megamu_offsets.json` với `dump_current/dump.cs`.
- Kiểm tra thêm trên DLL: RVA có phải **đầu hàm** (bảng `.pdata` hoặc padding `CC` phía trước).
- Kết quả hiện tại: **69 offset OK**, 2 cần xem tay, **7 offset chết**:

| key | RVA chết | Ghi chú |
|---|---|---|
| `window_show` | `0x258FBC0` | `Window` build mới nằm ở `0x25E9EE0…0x25EDCA0` |
| `window_hide` | `0x25986B0` | như trên |
| `window_set_state` | `0x258A730` | như trên |
| `window_toggle` | `0x2589E10` | như trên |
| `moss_window_close` | `0x25986B0` | đang dùng chung `Window.Hide` |
| `button_press` | `0x464E520` | Unity UI |
| `unity_event_invoke` | `0x4588220` | UnityEvent |

⇒ **`closeMoss()` hiện gọi vào giữa một hàm khác của build mới.** Đây là việc tiếp theo cần làm (xem §4).

### 2.6. Test

| File | Nội dung | Kết quả |
|---|---|---|
| `test_moss_dispose.py` **(mới)** | Trích JS thật, dựng mô hình bộ nhớ giả, chạy bằng Node: 7 kịch bản (ngoài safe-zone, safe-zone + merchant, safe-zone không merchant, không có rác, bảo vệ slot 0..11 & +7, `maxBatch`, mất GS) | ✅ PASS |
| `test_trash_in_place.py` | 6 test cũ | ✅ PASS |
| `test_moss_cleaner_protection.py` | guard `s<12`, offset struct, `isItemProtected` | ✅ PASS |
| `test_moss_fix.py`, `test_moss_comprehensive_cross_audit.py` | sinh JS + `node --check` | ✅ PASS |
| `test_moss_close_fix.py` | **viết lại**: từ hardcode RVA cũ → kiểm tra *nhất quán 3 nguồn offset* + RVA Moss đã verify | ✅ PASS (trước đó FAIL 2/4) |

---

## 3. Cách kiểm chứng trên game thật

1. Mở app, vào tab Moss, bật 1 slot ở Elbeland, bấm **"🗑️ Ném"**.
2. Xem log:
   - `Đã dọn N món rác (vứt X, bán Y, kết quả: done)` → thành công.
   - `Server KHÔNG cho rơi đồ tại (22,225) … safe-zone` → đúng như phân tích; chuyển sang bán.
3. Trong vòng auto: khi hòm gần đầy, log sẽ hiện chuỗi *dọn → (nếu bị chặn) bán cho Merchant → tiếp tục quay*.
4. Nếu log báo `no_gs_connection` → engine mất kết nối, không phải lỗi logic dọn rác.

> Lưu ý: tôi **không có phiên game đang chạy** để test end-to-end, nên phần "server có nhận hay không" cần bạn xác nhận bằng log. Mọi nhánh logic đã được test offline bằng Node.

---

## 4. Cập nhật lần 2 — sau khi chẩn đoán trên game thật

### 4.1. Dữ liệu đo được (attach Frida vào PID 18456, nhân vật ở Elbeland)

| Thông số | Giá trị |
|---|---|
| Toạ độ | **(22, 225)** — đúng bệ Moss, thuộc Elbeland (safe-zone) |
| Số ô có đồ (slot 12..139) | **19** |
| Độ dài mảng inventory | **239** (không phải 140!) |
| GS connection | OK |
| Merchant window | **đang MỞ** |
| Bảng Moss | đóng |

Hai điểm đáng chú ý:

1. **Mảng inventory dài 239** ⇒ code cũ chỉ quét `12..139`, bỏ sót các ô từ **140 trở đi** (ba lô mở rộng 2). Nếu đồ rác nằm ở đó thì "Ném" không bao giờ thấy.
2. Bộ lọc `isDivineOrDragonItem()` bảo vệ theo **tên** (`brilliant`, `lightning`, `awakening`, `dragon`…) và theo **`type >= 30`** — đây là các loại rất phổ biến của đồ Moss, nên phần lớn đồ rác bị chặn trước khi gửi packet ⇒ "không có món nào để dọn".

### 4.2. Bổ sung trong lần này

| Thay đổi | Vị trí |
|---|---|
| `analyzeJunkInventory()` — liệt kê từng món + **lý do bị giữ** (`divine_or_dragon`, `level_over_max`, `jewel_section`, …) | `meg_direct_engine.py` |
| `itemProtectionReason()` — bản "có lý do" của `isItemProtected()`, có test chống phân kỳ | `meg_direct_engine.py` |
| Tuỳ chọn **bỏ lọc tên/loại** (`ignore_type_heuristics`): chỉ giữ Exc/Set/Socket/Harmony/ngọc/cấp + | engine + GUI checkbox |
| Quét tới **240 ô** (thay vì 140) cho cả analyze và dispose | engine |
| Nút **"🔍 Phân Tích Rác"** trên toolbar + log chi tiết | `meg_gui.py` |
| Khi vứt thất bại mà **Merchant đang mở** → tự bán ngay (không cần di chuyển) | `clean_moss_inventory()` |
| Script độc lập `tools/moss_junk_report.py` (chỉ đọc, in báo cáo) | `tools/` |

### 4.3. Nút "🧹 Dọn Rác" trong app (tích hợp GUI)

Thêm vào toolbar tab Moss: mở hộp thoại **Dọn Rác Hòm Đồ** với 3 bước ngay trong app:

1. **Quét** — đọc RVA hòm đồ của mọi slot đang kết nối (thread riêng, không treo UI).
2. **Xem trước** — bảng: số món, dọn được / bị giữ, lý do giữ, danh sách từng món dọn được, toạ độ, Merchant MỞ/ĐÓNG.
3. **Chọn cách dọn** — `Tự động (vứt → bán)` / `Chỉ vứt` / `Chỉ bán`, bấm **Thực hiện**.

Kết quả từng slot được ghi vào log Moss, kèm `reason` và số món thực sự biến mất (xác minh lại bằng RAM).

Code: `DashboardApp.open_junk_disposal_dialog()` → `_show_junk_disposal_dialog()` → `_run_junk_disposal()`.

### 4.4. Cách dùng nhanh (script / log)
```powershell
# 1) Chạy khi game đang mở — chỉ đọc, không xóa gì
python tools/moss_junk_report.py
python tools/moss_junk_report.py --max-level 9 --ignore-type
```

Hoặc trong app: **Tab Moss → "🔍 Phân Tích Rác"** rồi đọc log:
```
🔍 HÒM ĐỒ: 19 món | dọn được 0 | bị giữ 19 | toạ độ (22,225) | Merchant MỞ
🛡️ Bị giữ → bị lọc theo TÊN/LOẠI: 14 · cấp + vượt ngưỡng: 3 · ngọc/vé/cánh: 2
```
Nếu ra đúng như vậy → bật **"⚠️ Bỏ lọc tên/loại"** (hoặc chạy với `--ignore-type`) rồi bấm "Ném" lại.

> Lưu ý an toàn: khi bật bỏ lọc, đồ Divine/Rồng **+0 không có thuộc tính** vẫn có thể bị dọn. Nên xem danh sách "Chi tiết món bị giữ" trước khi bấm.

---

## 5. Sự cố 17:51 — `send_failed` và suýt xóa sạch ngọc

### 5.1. Diễn biến

Log của bạn: `Dọn 0 món (vứt 0, bán 0) — send_failed` ⇒ **không có packet nào được gửi**, nên chưa mất gì.

Nhưng khi chạy dry-run (`tools/drop_junk_now.py`, không `--yes`) trên chính phiên game đó, danh sách "rác" gồm:

```
slot 13  Devil Square Ticket      slot 29  Jewel of Chaos
slot 14  [Bound] Bless of Light   slot 35  Jewel of Bless
slot 16  Jewel of Darkness        slot 54  Jewel of Harmony
slot 19-27  Mirror of Dimensions  slot 28  Box of Luck
```

⇒ **Toàn là đồ quý.** Nếu lần đó gửi được packet thì đã mất sạch.

### 5.2. Nguyên nhân gốc

`readItemIndex()` đọc `TableItem + 0x68` và chấp nhận cả giá trị **0**:

```js
var fieldIdx = te.add(0x68).readS32();
if (fieldIdx >= 0 && fieldIdx < 65536) return fieldIdx;   // 0 vẫn "hợp lệ"!
```

Theo `dump_current/dump.cs`:
- `class Info { public int Index; // 0x10 }` ← index thật nằm ở **+0x10**
- `class EPBPOHPFKG : Info` ← `itemPtr + 0x58` chính là bảng entry này
- `+0x68` là một field khác (mặc định 0) ⇒ **mọi món trả index = 0**
- index 0 ⇒ `sec = 0`, `type = 0` ⇒ không món nào lọt vào nhóm bảo vệ ngọc (sec 12–15)

### 5.3. Đã sửa

| Sửa | Chi tiết |
|---|---|
| `readItemIndex()` | Đọc `Info.Index @ te+0x10`, **từ chối giá trị 0**; fallback `sec/type @ +0x58/+0x5C` cũng phải > 0; không xác định được ⇒ trả `-1` (bị coi là "không rõ" ⇒ được bảo vệ) |
| Lưới an toàn theo tên | `isDivineOrDragonItem()` bổ sung keyword: `jewel/bless/soul/chaos/harmony/creation/life/guardian/ticket/mirror/box/wing/feather/cloak/seed/fruit/rune/gem/stone/scroll/horn/pentagram/errtel/muun/raven/horse/ngọc/vé/…` — bảo vệ kể cả khi index đọc sai |
| Gửi gói | Thêm **native drop** `UserInventory.KCEAGAMOOOO(slot, Coord*) @ 0x1449740` (hàm drop thật của client, đã verify prologue trên DLL); packet thuần chỉ còn là fallback |
| Chẩn đoán | `disposeJunkItems` trả thêm `sendError` + `nativeDropBound`; log GUI in kèm để biết chính xác tắc ở đâu |

### 5.4. Vì sao `send_failed`

Chuỗi gửi hiện tại: `getGSConnection` → `createManagedByteArray` (il2cpp_array_new + class `System.Byte`) → `gs_send(gs, byte[], 0, 0, 0)`.

Cả 3 export (`mono_domain_get_corlib`, `il2cpp_class_from_name`, `il2cpp_array_new`) đều **có** trong `GameAssembly.dll` (đã kiểm tra export table), nên nhiều khả năng lỗi nằm ở việc `gs_send` cần **packet object** (do `0x14af970` tạo) chứ không phải `byte[]` thô. Vì vậy hướng sửa là gọi hàm drop native của game — nó tự dựng packet đúng chuẩn.

---

## 6. Việc còn lại (đề xuất tiếp)
1. **Map lại 7 offset UI** cho build hiện tại:
   - Tìm trong `Window` (`0x25E9EE0…0x25EDCA0`) hàm nào ghi `byte [this+0x48] = 0` → đó là `Hide`; ghi `= 1` → `Show`.
   - `Button.Press` / `UnityEvent.Invoke` có thể lấy trực tiếp từ `dump_current/dump.cs` (namespace `UnityEngine.UI` / `UnityEngine.Events`).
   - Sau khi map: chạy `python tools/verify_offsets.py --dll` phải về 0 FAIL.
2. **Marshal native UI về main thread** (dùng lại pattern `pendingMossOpenCategory` trong hook `GameUI.Update`) — giảm rủi ro crash khi đóng/mở bảng.
3. **Nối auto-sell vào vòng lặp theo ngưỡng** (hiện chỉ gọi khi dọn thất bại) và thêm tuỳ chọn UI "Khi hòm đầy: Bán / Vứt / Dừng".
4. **Thống nhất chính sách level**: auto-clean dọn tới +6 nhưng `sellMossPlusItems` lại chỉ bán +0..+4 — cần chọn một ngưỡng.
5. Bỏ câu "bảo vệ May Mắn" khỏi log/UI (engine cố ý không bảo vệ `luck`).
