// ==============================================================================
// DONPV MEGAMU NATIVE C++ BRIDGE CLI TOOL
// ==============================================================================
// Chuong trinh C++ doc lap de kiem tra cau noi Native giua App va Web Laravel
// ==============================================================================

#include <iostream>
#include <string>
#include <windows.h>

typedef int (*FnGetVersion)();
typedef int (*FnGetHwid)(char*, int);
typedef int (*FnActivate)(const char*, const char*, const char*, const char*, char*, int);
typedef int (*FnVerify)(const char*, const char*, const char*, char*, int);

int main(int argc, char* argv[]) {
    // Thiet lap console UTF-8 tren Windows
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);

    std::cout << "==========================================================" << std::endl;
    std::cout << " DONPV MEGAMU C++ NATIVE BRIDGE TESTER v1.0.0            " << std::endl;
    std::cout << " Cầu Nối Native C++ Giữa Client & Web Server Laravel     " << std::endl;
    std::cout << "==========================================================" << std::endl;

    HMODULE hDll = LoadLibraryA("meg_license_bridge.dll");
    if (!hDll) {
        std::cerr << "[LỖI] Không thể nạp thư viện meg_license_bridge.dll!" << std::endl;
        std::cerr << "Hãy chắc chắn rằng meg_license_bridge.dll nằm cùng thư mục." << std::endl;
        return 1;
    }

    FnGetVersion pGetVer = (FnGetVersion)GetProcAddress(hDll, "Bridge_GetVersion");
    FnGetHwid pGetHwid = (FnGetHwid)GetProcAddress(hDll, "Bridge_GetHwid");
    FnActivate pActivate = (FnActivate)GetProcAddress(hDll, "Bridge_ActivateLicense");
    FnVerify pVerify = (FnVerify)GetProcAddress(hDll, "Bridge_VerifyLicense");

    if (!pGetVer || !pGetHwid || !pActivate || !pVerify) {
        std::cerr << "[LỖI] Không tìm thấy các hàm Export trong DLL!" << std::endl;
        FreeLibrary(hDll);
        return 1;
    }

    std::cout << "[✓] Đã nạp thành công meg_license_bridge.dll (Phiên bản: " << pGetVer() << ")" << std::endl;

    char hwid[64] = { 0 };
    if (pGetHwid(hwid, sizeof(hwid))) {
        std::cout << "[✓] Mã định danh máy tính (HWID): " << hwid << std::endl;
    }

    std::string serverUrl = "https://megamuoffical.com";

    if (argc >= 2) {
        std::string cmd = argv[1];
        if (cmd == "hwid") {
            std::cout << "HWID: " << hwid << std::endl;
            FreeLibrary(hDll);
            return 0;
        } else if (cmd == "activate" && argc >= 3) {
            std::string key = argv[2];
            std::cout << "\n[*] Đang gửi yêu cầu kích hoạt key '" << key << "' tới Laravel API..." << std::endl;
            char outJson[4096] = { 0 };
            int res = pActivate(serverUrl.c_str(), key.c_str(), "megamu-navigator", "v1.5.1", outJson, sizeof(outJson));
            std::cout << "[*] Kết quả phản hồi từ C++ Native Bridge (Code: " << res << "):" << std::endl;
            std::cout << outJson << std::endl;
            FreeLibrary(hDll);
            return 0;
        } else if (cmd == "verify" && argc >= 3) {
            std::string key = argv[2];
            std::cout << "\n[*] Đang gửi yêu cầu xác thực key '" << key << "' tới Laravel API..." << std::endl;
            char outJson[4096] = { 0 };
            int res = pVerify(serverUrl.c_str(), key.c_str(), "v1.5.1", outJson, sizeof(outJson));
            std::cout << "[*] Kết quả phản hồi từ C++ Native Bridge (Code: " << res << "):" << std::endl;
            std::cout << outJson << std::endl;
            FreeLibrary(hDll);
            return 0;
        }
    }

    // Mặc định: Tự động chạy xác thực key mẫu MEG-DONPV-2026-VIP1
    std::cout << "\n[*] Đang kiểm tra xác thực Native C++ với Laravel Server (" << serverUrl << ")..." << std::endl;
    char outJson[4096] = { 0 };
    int res = pVerify(serverUrl.c_str(), "MEG-DONPV-2026-VIP1", "v1.5.1", outJson, sizeof(outJson));
    std::cout << "[*] Trạng thái gọi hàm: " << (res ? "THÀNH CÔNG (1)" : "THẤT BÀI (0)") << std::endl;
    std::cout << "[*] Dữ liệu JSON nhận từ Laravel:" << std::endl;
    std::cout << outJson << std::endl;

    std::cout << "\n----------------------------------------------------------" << std::endl;
    std::cout << "Cách sử dụng CLI:" << std::endl;
    std::cout << "  meg_bridge_cli.exe hwid" << std::endl;
    std::cout << "  meg_bridge_cli.exe verify <KEY>" << std::endl;
    std::cout << "  meg_bridge_cli.exe activate <KEY>" << std::endl;
    std::cout << "==========================================================" << std::endl;

    FreeLibrary(hDll);
    return 0;
}
