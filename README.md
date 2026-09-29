# MegAccountManager

Ứng dụng Windows Forms quản lý tài khoản đăng nhập MEGAMU và danh sách nhân vật theo từng tài khoản.

## Chạy

```powershell
cd C:\Users\donpv\Desktop\meg\MegAccountManager
dotnet run
```

Hoặc mở:

`C:\Users\donpv\Desktop\meg\MegAccountManager\bin\Release\net8.0-windows\MegAccountManager.exe`

### Kiểm thử IL2CPP chỉ-đọc

Khi MEGAMU đang chạy, dùng lệnh sau để kiểm tra chain
`GameAssembly → Game.Instance → _Player/_World → Coord/SceneIndex`:

```powershell
dotnet build .\MegAccountManager\MegAccountManager.csproj --configuration Release
dotnet .\MegAccountManager\bin\Release\net8.0-windows\MegAccountManager.dll --il2cpp-probe
```

Probe chỉ mở process với quyền đọc; không ghi RAM, gọi method IL2CPP hay gửi packet.
Nếu app đang mở từ cùng thư mục `bin\Release`, hãy đóng app trước bước build để Windows
không khóa file `.exe`.

## Tính năng

- Thêm / sửa / xóa tài khoản và nhân vật
- **Quét map/tọa độ**: đọc cửa sổ `MEGAMU.exe` + quét RAM/IL2CPP để lấy
  - tài khoản (`LastUsername`)
  - map (`World.SceneIndex` / `World###`)
  - tọa độ (`Body.Coord`)
- **Tab Maps**: catalog đầy đủ map (ID/tên/nhóm), tìm kiếm, gắn “theo dõi map”
  - khớp với process live đang đứng map đó
  - chỉ giám sát — **không** gửi lệnh chuyển map vào game
- **Đọc AccountList**: lấy danh sách tài khoản/nhân vật từ registry `HKCU\Software\MEGAMU\MEGAMU`
- **Nhập process vào danh sách**: merge kết quả quét vào dữ liệu quản lý

## Dữ liệu app

`%AppData%\MegAccountManager\accounts.json`

## Nguồn dữ liệu MEGAMU

| Nguồn | Nội dung |
|---|---|
| Tiêu đề cửa sổ process | Nhân vật, level, server (`Diradira (660/51rr) - MEGAMU Sv41`) |
| RAM process | JSON settings có `LastUsername` + `LastCharacter` |
| Registry AccountList | Danh sách username và nhân vật đã login trên máy |

Ví dụ map đã xác minh trên máy bạn:

- `osint` → `osint88`
- `hface` → `1hitdivien`
- `hvideo` → `SaoxoaKuta`
- `cravr` → `Diradira`
- `clario` → `GunApao`
