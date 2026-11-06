# Phân tích sâu: Moss Merchant (Moss The Gambler) trong app MEGAMU Auto

> Đối chiếu 3 nguồn: `dump_current/dump.cs` (bản mới nhất, 812.814 dòng, 02/11/2026), `dump/dump.cs` (bản cũ, 16/10/2026), và mã nguồn app (`meg_gui.py` 12.606 dòng, `meg_direct_engine.py` 7.418 dòng).
> Mọi kết luận đều kèm số dòng để kiểm chứng lại.

---

## 0. TL;DR — 6 phát hiện quan trọng nhất

| # | Phát hiện | Mức độ |
|---|---|---|
| 1 | **8/17 offset liên quan Moss đang lệch build.** Toàn bộ lớp điều khiển UI (`window_show`, `window_hide`, `window_set_state`, `window_toggle`, `button_press`, `unity_event_invoke`, `component_get_game_object`, `moss_window_close`) chỉ tồn tại trong `dump/dump.cs` cũ, **không còn** trong `dump_current/dump.cs`. Riêng `moss_*` (packet) lại khớp bản mới ⇒ file offset là hỗn hợp 2 build. | 🔴 P0 |
| 2 | **`component_get_game_object` có 3 giá trị khác nhau** trong repo: `config/megamu_offsets.json` = `0x45C8770`, `megamu_offsets.json` (root) = `0x456AE90`, `DEFAULT_OFFSETS` = `0x45C8770`. Không có nguồn duy nhất. | 🔴 P0 |
| 3 | **`save_moss_config()` ghi đè cả file**, xoá `schedule` + `selected_slots`. Bằng chứng: `config/moss_slots_config.json` hiện chỉ còn `{"slots": {...}}`. | 🔴 P0 |
| 4 | **Mọi lệnh native UI chạy trên thread Frida, không phải main thread Unity.** `ensureThreadAttached()` chỉ gọi `il2cpp_thread_attach`, không dispatch. Chỉ thao tác *mở* bảng là được đẩy vào hook `GameUI.Update`. | 🟠 P1 |
| 5 | **3 native binding là dead code** (`nativeMossOpen`, `nativeMossInit`, `nativeMossRollHandler`) — vẫn khai báo, không dùng. `moss_open` (`0x25EA7C0`) thực chất là `Window.KFEFPHKPDGE(bool)`, không phải hàm mở Moss. | 🟠 P1 |
| 6 | **Chính sách "giữ đồ" mâu thuẫn giữa 3 đường đi**: auto-clean dọn tới +6, `sellMossPlusItems` chỉ bán +0..+4, docstring nói bán +5..+7. GUI lại quảng cáo "bảo vệ May Mắn" trong khi engine cố ý bỏ qua `luck`. | 🟠 P1 |

---

## 1. Người dùng thấy gì (chức năng hiện có)

Tab **"5: AUTO QUAY MOSS THE GAMBLER"** — grid đa tài khoản (`meg_gui.py:7303-8390`):

- **Header**: đếm ngược giờ Moss, trạng thái scheduler, 2 checkbox `auto_schedule` / `auto_move_before`.
- **Toolbar**: chọn/bỏ chọn tất cả, badge `Quay Moss: x/y`, BẮT ĐẦU / DỪNG, áp dụng category + delay hàng loạt, checkbox "Tự dọn rác" toàn cục, các nút `🗑️ Ném Tại Chỗ`, `💰 Bán Silvia`, `🔓 Về NPC`, `Mở NPC`, `Đóng NPC`.
- **Bảng 8 cột**: mỗi controller (slot tài khoản) một dòng — checkbox bật, combo 12 category, entry delay, số lượt, trạng thái, 4 nút tác vụ, context menu 6 lệnh.
- **Log console** riêng (giữ 1.000 dòng).
- **Scheduler**: 4 khung/ngày `(0,15) (6,15) (12,15) (18,15)`, mỗi phiên `MOSS_DURATION = 300s`, tự bật/tắt và tự `/move Elbeland` trước 10–15s (`meg_gui.py:8275-8380`).
- **License gate**: module `moss` (`meg_gui.py:2217`, `license_client.py:731`).

Cấu hình lưu tại `config/moss_slots_config.json`:

```json
{"slots": {"1": {"category": 6, "delay_ms": 1000, "max_rolls": 0, "auto_clean": true}, ...}}
```

12 category (`meg_gui.py:7215-7231`): 0–5 quay bằng Zen (kiếm/chùy/cung/gậy/khiên/trang sức), 6–11 quay bằng ngọc (2/10 Soul, 2/10 Bless, 2/10 Chaos).

---

## 2. Kiến trúc 3 tầng

```
[Tkinter UI]  meg_gui.py  build_moss_view + _periodic_moss_scheduler
      │  (Tk.after, main thread)
      ▼
[SlotController worker]  threading.Thread/slot — start_moss() (meg_gui.py:2212)
      │  gọi hàm Python đồng bộ
      ▼
[MegDirectEngine]  _call() → Frida exports_sync (meg_direct_engine.py:5858)
      │  chạy trên thread Frida, giữ _rpc_lock
      ▼
[JS agent]  meg_direct_engine.py (template Frida) — đọc/ghi bộ nhớ IL2CPP + gửi packet GS
      │
      ├─ đọc RAM: GameUI → MMossMerchantWindow (+0x1C8) → MWindow (+0x20)
      └─ packet: C1:04:31 (đóng talk), C1:23 (drop), C1:04:33 (sell), roll qua native send
```

Điểm quan trọng: đây **không phải PyQt/QThread** mà là `customtkinter` + `threading.Thread` + `Tk.after`. Vì vậy mọi ràng buộc "chỉ main thread được chạm widget Tk" đều áp dụng, và code đang vi phạm ở nhiều chỗ (xem §7).

---

## 3. Mô hình game-side đọc từ `dump.cs`

### 3.1. Cây class

| Thành phần | Dòng trong `dump_current/dump.cs` | Vai trò |
|---|---|---|
| `MossMerchantWindow : GameBehaviour` (TypeDefIndex 107) | 12214 | Lớp **protocol**: 14 hàm `internal static void X(byte[] OCHGNNANFNP)` (packet handler từ server), 2 hàm `static void X(int)` (gửi request), 11 slot virtual (callback UI) |
| `MMossMerchantWindow : MossMerchantWindow` (590) | 84114 | Lớp **UI**: 12 field `[SerializeField]`, `Update()`, coroutine, xử lý click/close |
| `MMossMerchantWindow.GIKFMMJFGGK` (589) | 84098 | Closure `[CompilerGenerated]`, giữ `_category` + `<>4__this`, callback `MBJIJAHOMOH(bool r)` — dùng cho luồng xác nhận async khi đổi category |
| `TableMossMerchantCategory : Table<DEKGLEGIGDM>` (1646) | 176326 | Bảng dữ liệu category |
| `TableMossMerchantReward : Table<DKCEBKDCHJJ>` (1647) | 176497 | Bảng tỉ lệ/phần thưởng theo category |
| `DEKGLEGIGDM : Info` (1502) | 167283 | Row category: `0x18 string name`, `0x20 bool`, `0x24 int`, `0x28 int` |
| `DKCEBKDCHJJ : Info` (1503) | 167298 | Row reward: `0x18 int`, `0x1C int` |
| `Data` registry | 163911 / 163912 | `TableMossMerchantCategory` @ `0x118`, `TableMossMerchantReward` @ `0x120` |
| `GameUI` | 224098 | Field `MossMerchantWindow` @ **`0x1C8`** — đúng bằng `ui_moss_window` của app |
| `Window : GameBehaviour` (144) | 15742 | Base window: `CloseButton` @ `0x40`, `IsOpen` @ `0x48`, `OnShow/OnHide` @ `0x70/0x78` |

### 3.2. Layout `MMossMerchantWindow` — app đọc đúng 100%

| Offset | Field trong dump | App dùng ở đâu |
|---|---|---|
| `0x20` | `MWindow Window` | `mossWin.add(0x20)` — mọi nơi |
| `0x28` | `GameObject CategoryItemPrefab` | (không dùng) |
| `0x38/0x40` | `ItemStorage Possibility/Requirement` | (không dùng) |
| `0x58` | `Button RollButton` | `ensureMossRollButtonActive` (1598) |
| `0x60` | `GameObject LoadingImage` | bật/tắt spinner (1602, 2949) |
| `0x68/0x70` | `RewardContainer / RewardStorage` | **không dùng** — app không đọc kết quả quay từ đây |
| `0x78` | `int` (category hiện tại) | ghi category trước khi quay (2910) |
| `0x80` | `List<DEKGLEGIGDM>` | đọc danh sách category (2876, 3103) |
| `0x88` | `float` | (không dùng) |
| `0x8C` | `int` | (không dùng) |
| `0x90` | `List<int>` | (không dùng) |
| `0x98` | `float` (timer quay) | reset về 0 (1627) |

So sánh `dump/dump.cs` (16/10) và `dump_current/dump.cs` (02/11): **layout field y nguyên**, chỉ đổi tên obfuscate ⇒ offset struct của app vẫn đúng trên build mới.

### 3.3. Nhưng RVA hàm thì đã trôi

`Window` cũ nằm ở `0x258A730…0x25986B0`; `Window` mới nằm ở `0x25E9EE0…0x25EDCA0` — dịch ~`0x5C` trang. Trong khi đó `MMossMerchantWindow` mới ở `0x27A56F0…0x27AA890`.

**Bảng đối chiếu offset của app với 2 dump:**

| Key | RVA trong config | Có trong `dump_current`? | Có trong `dump` (cũ)? | Ánh xạ thực tế |
|---|---|---|---|---|
| `moss_send_roll` | `0x23F8BE0` | ✅ | ❌ | `MossMerchantWindow.FOILGIOOHJL(int)` — gửi packet roll (**đúng**) |
| `moss_roll_click` | `0x27A8F90` | ✅ | ✅ | `MMossMerchantWindow.BPHDCANLIID()` — OnClick roll (**đúng**) |
| `moss_select_cat` | `0x27A8510` | ✅ | ❌ | `IGGEKEFMNIJ(DEKGLEGIGDM)` — chọn category (**đúng**) |
| `moss_roll` | `0x27A9760` | ✅ | ❌ | `LJGCFLIJDPL()` private void — **không được dùng** |
| `moss_roll_handler` | `0x27A6230` | ✅ | ❌ | `JOFCEJDGNHI(DEKGLEGIGDM)` — thực ra là handler chọn category, **không dùng** |
| `moss_init` | `0x27A77C0` | ✅ | ❌ | `Awake()` — **không dùng** |
| `moss_open` | `0x25EA7C0` | ✅ | ❌ | `Window.KFEFPHKPDGE(bool state)` — **hàm show/hide generic**, không phải mở Moss |
| `moss_window_close` | `0x25986B0` | ❌ | ✅ | build cũ: `MInventoryWindow` private void (thân dùng chung, nhiều class) |
| `window_show` | `0x258FBC0` | ❌ | ✅ | build cũ: `Window` slot 27 |
| `window_hide` | `0x25986B0` | ❌ | ✅ | build cũ: `Window` slot 51 |
| `window_set_state` | `0x258A730` | ❌ | ✅ | build cũ: `Window` |
| `window_toggle` | `0x2589E10` | ❌ | ✅ | build cũ: `Window` |
| `button_press` | `0x464E520` | ❌ | ✅ | build cũ |
| `unity_event_invoke` | `0x4588220` | ❌ | ✅ | build cũ |
| `component_get_game_object` | `0x45C8770` (config) / `0x456AE90` (root) | ✅ config / ❌ root | ✅ root / ❌ config | — |
| `game_object_set_active` | `0x456F2B0` | ✅ | ✅ | ổn định |

Thống kê toàn bộ 70 offset dạng `0x…` trong `megamu_offsets.json` (root):

- **53** chỉ có trong build mới, **5** có ở cả hai, **8** chỉ có ở build cũ, **4** là TypeInfo (không nằm trong dump).
- Nhóm "chỉ có ở build cũ" đúng bằng nhóm hàm điều khiển UI mà Moss dùng để mở/đóng bảng.

Hệ quả thực tế: trên client build mới, **đường gửi packet quay vẫn chạy**, nhưng `closeMoss()` đang gọi vào địa chỉ không còn là `Window.Hide` ⇒ hoặc không đóng được, hoặc thực thi code lạ với `this` là `Window` (rủi ro access violation). Đây khớp với lịch sử bug "close không được" và các bản patch liên tục ở `3cfce2d`.

Ghi chú: `moss_open → 0x25EA7C0` trỏ vào `Window.KFEFPHKPDGE(bool)` nên nếu ai bật lại `nativeMossOpen` sẽ "show/hide window" chứ không mở bảng Moss — binding này đang **sai về ngữ nghĩa** ngay cả khi RVA còn đúng.

---

## 4. Luồng chạy end-to-end

`SlotController.start_moss()` (`meg_gui.py:2212-2548`), 1 thread/slot:

**Pha 0 — Chuẩn bị (2214-2250)**
1. Check `moss_running`, license `moss`, PID còn sống, engine ready.
2. Nếu Auto Train đang chạy → `stop_auto()` + `sleep 0.3`; nếu MuHelper bật → `stop_helper()` + `sleep 0.2`.

**Pha 1 — Chờ NPC (2262-2305)**
3. Vòng lặp `while moss_running` poll `find_moss_npc()` mỗi `0.5s`, **không timeout**.
4. Khi thấy NPC: `interact_moss_npc(category)` → engine set `pendingMossInteractPtr` → hook `GameUI.Update` mới thực sự `invokeNpcTalk` (đúng main thread, `meg_direct_engine.py:2162-2171`).
5. Chờ `is_moss_ready()` tối đa `20 × 0.1s` = 2s (điều kiện: `IsOpen == 1` và `List<Category>.Count > 0`).

**Pha 2 — Snapshot bảo vệ (2307-2322)**
6. `get_inventory_summary(category=moss_category)` → chỉ lấy `keptSlots` → `moss_initial_slots`.

**Pha 3 — Vòng quay (2324-2527)**
7. Tính `min_slots_needed` theo category: `8` cho 0–4, `6` cho 6/8, `2` cho còn lại.
8. Pre-clean: nếu `free < min+4` và `junk > 0` → `clean_inventory_junk("trash", protected_slots=snapshot, category=..., max_junk_level=6)` rồi đọc lại summary.
9. Nếu `free < min` và `junk == 0` → **dừng an toàn**.
10. Nếu `!is_moss_open()` → `sleep 0.4`, `interact_moss_npc`, chờ `12 × 0.1s`.
11. `inv_before = get_inventory_summary(...)` → `roll_moss(category)`.
12. `sleep 0.35` (cố định) → `inv_after` → **diff theo slot number** giữa `keptSlots`/`junkSlots` để biết "trúng gì".
13. Không thấy item mới ⇒ `fail++`; `reset_moss_ui()`; thử clean rồi `continue`; `fail >= 2` ⇒ dừng.
14. `roll_moss` trả `False` ⇒ `fail++`; NPC mất ⇒ dừng; còn NPC ⇒ interact lại; `fail >= 3` ⇒ `sleep 1.0`.
15. `max_rolls` đạt ⇒ dừng. Delay chia nhỏ `0.05s`, `target = max(0.4, delay_ms/1000)`.

**Pha 4 — Kết thúc (2529-2544)**
16. `reset_moss_ui()` + `close_moss()`; `Tk.after(0)` cập nhật UI; nếu trước đó đã pause Train thì `Tk.after(1000)` gọi `start_auto()`.

**Nhận xét kiến trúc quan trọng:** app **không đọc kết quả quay từ `RewardStorage`/`RewardContainer` (0x68/0x70)** mà suy ra bằng *diff hòm đồ*. Đây là điểm yếu cốt lõi:
- Nếu server trả item vào đúng slot vừa trống nhưng trùng slot number với item cũ ⇒ diff sai.
- Nếu auto-clean chạy xen giữa ⇒ diff nhiễu.
- Trúng ngọc/vé rơi vào `sec 12..15` bị coi là "kept" nên vẫn diff được, nhưng item bị dọn ngay sau đó thì không.
- Không phân biệt được "hòm đầy" vs "hết Zen" vs "mất phiên NPC" — cả 3 đều dẫn tới cùng nhánh `fail`.

---

## 5. Bốn lớp "chống mất đồ" và lỗ hổng của từng lớp

**Lớp 1 — Guard slot cứng** (`meg_direct_engine.py:966, 980, 5051`): mọi hàm drop/sell/clean đều `if (s < 12) return false`. Từng có bug `s - 12` biến slot 12 → 0 (vứt nhầm đồ đang mặc); đã fix và có test bảo vệ.

**Lớp 2 — `isItemProtected()`** (`1320-1375`): bảo vệ Divine/Rồng, `exc>0`, `anc>0`, `sock>0`, `harmony>0`, `sec 12..15`, và level.
- `max_junk_level` mặc định 4; auto-clean truyền **6** ⇒ **+5 và +6 bị dọn**.
- **`luck` được truyền vào nhưng không hề dùng** (dòng 1320 khai báo, 1374 trả về) — trong khi log GUI nói "bảo vệ May Mắn" (2356, 2762, 8039).
- Nhánh `mossCat` (1359-1372) map category → `sec`, nhưng bước 7 (`sec 12..15 → return true`) chạy **trước** ⇒ **category 5 (Pendant/Ring) không bao giờ dọn được gì**.

**Lớp 3 — Snapshot trước khi quay**: chỉ chứa `keptSlots`, tức các món đã được coi là "giữ"; **đồ rác +0..+4 có sẵn trước khi quay không nằm trong snapshot**. Thêm nữa, `clean_moss_inventory()` mặc định `force_clean=True` ⇒ truyền `protected_slots=[]` (2750) ⇒ **tắt luôn lớp này** ở đường dọn thủ công.

**Lớp 4 — 2-pass verify của engine** (`5083-5155`): pass 1 gửi packet từng slot (giãn 60ms), `sleep 0.2`; pass 2 đọc lại RAM, slot nào còn thì retry bằng toạ độ khác; trả `{cleaned, totalJunk, failed}`. Đây là phần chắc chắn nhất. Tuy nhiên GUI **không verify lại** sau khi gọi (chỉ log), còn vòng auto thì có đọc lại summary.

---

## 6. Bảng bug / rủi ro (đã kiểm chứng)

### P0 — có thể mất dữ liệu hoặc hỏng chức năng ngay

| Bug | Vị trí | Chi tiết |
|---|---|---|
| Lệch build 8 offset UI | `config/megamu_offsets.json:53-66` | Xem §3.3. `close_moss` gọi RVA không tồn tại trong build mới |
| 3 nguồn offset không đồng bộ | root JSON vs `config/` vs `DEFAULT_OFFSETS` | `component_get_game_object` = `0x45C8770` / `0x456AE90` / `0x45C8770` |
| `save_moss_config` xoá cấu hình khác | `meg_gui.py:1403` | Ghi `{"slots": ...}` duy nhất; gọi ở 7996/8007/8017/8172/8191. File thật đã mất `schedule` + `selected_slots` |
| Nút "Ném" tắt bảo vệ | `meg_gui.py:2725, 2750`; caller 7876/7884, 8031 | `force_clean=True` ⇒ `protected_slots=[]`, `category=-1` ⇒ quét mọi danh mục |
| `close_moss` luôn báo thành công | `meg_direct_engine.py:3049` | JS `return true` vô điều kiện; Python trả `True` nếu RPC không ném lỗi |

### P1 — sai hành vi nghiệp vụ

| Bug | Vị trí | Chi tiết |
|---|---|---|
| Thread Unity không an toàn | `2901, 2950, 2985, 3007, 3018, 3032` | `nativeWindowShow/Hide`, `GameObject.SetActive`, `Button.Press`, `UnityEvent.Invoke` gọi từ thread Frida. `ensureThreadAttached` (2428) chỉ `il2cpp_thread_attach` |
| Chính sách level mâu thuẫn | `meg_direct_engine.py:1340-1350, 3488` | auto-clean dọn tới +6; `sellMossPlusItems` gọi `isItemProtected` **không truyền** `maxJunkLvl` ⇒ chỉ bán +0..+4, trái docstring "bán +5..+7" |
| Luck bị bỏ qua nhưng UI hứa bảo vệ | `1320-1375` + `meg_gui.py:2356, 2762, 8039` | Người dùng tin là an toàn |
| Category 5 bị vô hiệu | `1352-1354` trước `1359-1371` | Pendant/Ring (`sec 12/13`) luôn `return true` |
| Auto-sell không nối vào loop | `meg_gui.py:2792` vs loop `2324-2527` | Hòm đầy ⇒ dừng, không bán; chỉ gọi thủ công (2966, 7885, 8054) |
| `max_rolls` là config chết | `2212-2250`, `2517` | Không widget nào set; `moss_rolls_count` không reset khi start ⇒ nếu set qua file sẽ dừng ngay |
| `refresh_moss_categories_from_game` dead | `7254-7298` | Không caller ⇒ luôn dùng 12 category hard-code, dù engine có `getMossCategories` đọc từ RAM |
| Checkbox "Tự dọn rác" luôn bật | `7550, 3916, 8017` | `select()` vô điều kiện, ghi đè `auto_clean=false` |
| Bỏ tick slot không dừng slot đang chạy | `7915-7928` | Loop chỉ xem `moss_running` |
| `_worker` không `try/finally` | `2252-2547` | Exception ⇒ thread chết nhưng `moss_running = True` ⇒ slot kẹt vĩnh viễn, `start_moss` trả `True` ngay |
| `stop_moss` không join | `2550` | Bấm start lại ngay ⇒ 2 worker cùng slot |
| `append_moss_log` gọi Tk từ worker | `2218, 2575, 2613, 2788...` | Vi phạm thread-safety của Tkinter |

### P2 — vận hành / bảo trì

| Vấn đề | Vị trí |
|---|---|
| Hard-code toạ độ `(22,225)`, `(44,229)`, `/move Elbeland` | `2257, 2921, 3002, 2815, 2998` |
| `min_slots_needed` map sai (cat 4 = 8 ô; cat 7/9/10/11 = 2 ô) | `2331` |
| Nhánh `continue` sau clean bỏ qua cả delay + max_rolls ⇒ spam packet | `2473` |
| `roll_moss_once` / `open_moss_npc` / `stop_all_moss_auto` block GUI (RPC lock, timeout khai báo nhưng không dùng) | `2593, 2639, 8213`; engine `5858` |
| `except: pass` rải khắp (≥ 20 chỗ) — clean fail vẫn roll tiếp | `2321, 2370, 2433, 2474...` |
| `getInventorySummary` luôn trả `mossPlusCount = 0` (`mossPlusSlots` không bao giờ được push) | `4899, 4956` |
| `remove_last_slot` không xoá config; `add_new_slot` không load config | `5080-5139, 5058` |

---

## 7. Chất lượng bộ test Moss

6 file: `test_moss_cleaner_protection.py`, `test_moss_close_fix.py`, `test_moss_comprehensive_cross_audit.py`, `test_moss_deep_audit.py`, `test_moss_fix.py`, `test_trash_in_place.py`.

| File | Kiểu | Trạng thái thực tế |
|---|---|---|
| `test_trash_in_place.py` | Mock engine + chạy `isItemProtected` qua Node (17 case) | ✅ file có giá trị nhất |
| `test_moss_comprehensive_cross_audit.py` | py_compile + string + `node --check` | ⚠️ false-pass nếu `find()` trả `-1` (slice rỗng vẫn pass) |
| `test_moss_cleaner_protection.py` | regex cấm chuỗi | ⚠️ chỉ cấm đúng literal `"s - 12"` |
| `test_moss_fix.py` | key tồn tại + `startswith("0x")` | ⚠️ `0x0` cũng pass |
| `test_moss_close_fix.py` | assert offset hard-code cũ | ❌ **đang FAIL 2/4** (đã chạy thử: `0x45C8770 != 0x456AE90`) |
| `test_moss_deep_audit.py` | chỉ `print`, **không assert** | ❌ in FAIL 5/7 offset nhưng exit 0 |

Không có test nào: chạy Frida thật, kiểm tra packet bytes, kiểm tra thứ tự `Hide` trước `IsOpen=0`, kiểm tra thread safety, hay tranh chấp roll/close/clean.

> Kết luận: các dòng "PASS 100%", "an toàn tuyệt đối", "đã xếp hàng main thread" trong test **không phải bằng chứng runtime**.

---

## 8. Khuyến nghị (theo thứ tự ưu tiên)

1. **Một nguồn offset duy nhất + kiểm tra tự động.** Viết script đọc `dump_current/dump.cs`, đối chiếu từng RVA trong `config/megamu_offsets.json`, fail nếu RVA không tồn tại. Bỏ `DEFAULT_OFFSETS` trùng lặp hoặc sinh nó từ JSON.
2. **Cập nhật lại nhóm `window_*` cho build mới.** `Window` mới nằm ở `0x25E9EE0…0x25EDCA0`; cần disassemble để xác định hàm nào ghi `IsOpen` (`+0x48`) và fade `CanvasGroup` (`+0x60`) — đó là `Hide`/`Show` thật. Cho tới lúc đó, `close_moss` nên đi đường an toàn: `Button.Press(CloseButton @ win+0x40)` + gửi `C1:04:31`, tránh gọi RVA nghi vấn.
3. **`closeMoss` phải trả về trạng thái thật**: sau khi đóng, đọc lại `IsOpen` và `return win.add(0x48).readU8() === 0`.
4. **Sửa `save_moss_config`**: đọc–gộp–ghi như `save_all_moss_configs` (1415-1421) để không mất `schedule` / `selected_slots`.
5. **Thống nhất chính sách level**: chọn một trong hai — "dọn tới +6, bán +7+" hoặc "chỉ dọn +0..+4". Hiện tại 3 đường (auto-clean / nút Ném / Bán Silvia) đang dùng 3 ngưỡng khác nhau.
6. **Quyết định dứt điểm chuyện Luck**: hoặc bảo vệ `luck > 0`, hoặc bỏ câu "bảo vệ May Mắn" khỏi mọi log/UI.
7. **Xử lý category 5**: đảo thứ tự — kiểm tra `mossCat` trước khi áp `sec 12..15`.
8. **Marshal native UI về main thread**: dùng lại đúng pattern `pendingMossOpenCategory` (2184-2191) cho `close`/`reset`/`SetActive`, thay vì gọi trực tiếp từ `_call`.
9. **Bọc `_worker` bằng `try/finally`** + `Event` thay cho bool + join trong `stop_moss`; đưa mọi `append_moss_log` qua `Tk.after(0, ...)`.
10. **Nối auto-sell vào loop** khi `free < min` và không còn rác — hoặc xoá docstring hứa hẹn.
11. **Dùng `RewardStorage` (0x70) để đọc kết quả quay** thay vì diff hòm đồ — đây là thay đổi kiến trúc đáng giá nhất về độ chính xác.
12. **Sửa/thay bộ test**: bỏ test stale, thêm harness bắt packet thật (`sendGSPacket` hook) và test tranh chấp.

---

## 9. Phụ lục — lệnh kiểm chứng nhanh

```powershell
# 1. Offset nào lệch build?
$cur = Select-String -Path dump_current\dump.cs -Pattern 'RVA: (0x[0-9A-Fa-f]+)' -AllMatches
# so RVA trong config\megamu_offsets.json với $cur

# 2. Test hiện đang đỏ?
python test_moss_close_fix.py      # FAIL 2/4
python test_moss_deep_audit.py     # in FAIL nhưng exit 0

# 3. Cấu hình Moss còn schedule không?
Get-Content config\moss_slots_config.json   # chỉ còn "slots"
```
