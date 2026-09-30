// ==============================================================================
// DONPV MEGAMU NATIVE C++ SECURITY BRIDGE DLL (v2.0 - ADVANCED ANTI-CRACK)
// ==============================================================================
// 3 LỚP BẢO VỆ CAO CẤP:
// LỚP 1: Mã hóa XOR URL Server & Secret Token (Không lưu chuỗi dạng Plaintext trong DLL)
// LỚP 2: Chữ ký số HMAC-SHA256 chống Proxy / Fiddler / Giả mạo Server
// LỚP 3: Giấu Offsets Game trong RAM mã hóa & Chống Debugger (Anti-Debugging)
// ==============================================================================

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>
#include <string>
#include <sstream>
#include <iomanip>
#include <vector>
#include <algorithm>
#include <cstring>
#include <cstdint>

#pragma comment(lib, "winhttp.lib")
#pragma comment(lib, "advapi32.lib")

#define BRIDGE_API extern "C" __declspec(dllexport)

// Biến trạng thái xác thực nội bộ trong bộ nhớ C++ (Chống patch GUI Python)
static volatile bool g_isLicenseAuthenticated = false;
static std::string g_customServerUrl = "";

// ==============================================================================
// 1. MÃ HÓA XOR CHUỖI NHẠY CẢM (URL VÀ SECRET TOKEN)
// ==============================================================================

// URL mặc định: "https://megamuoffical.com" (XOR key: 0x5C)
static const unsigned char ENC_DEFAULT_URL[] = {
    0x34, 0x28, 0x28, 0x2C, 0x2F, 0x66, 0x73, 0x73, 0x31, 0x39, 0x3B, 0x3D, 0x31, 0x29, 0x33, 0x3A,
    0x3A, 0x35, 0x3F, 0x3D, 0x30, 0x72, 0x3F, 0x33, 0x31, 0x00
};
static const unsigned char XOR_KEY_URL = 0x5C;

static std::string GetDecryptedDefaultUrl() {
    if (!g_customServerUrl.empty()) {
        return g_customServerUrl;
    }
    std::string s = "";
    int i = 0;
    while (ENC_DEFAULT_URL[i] != 0x00) {
        s += (char)(ENC_DEFAULT_URL[i] ^ XOR_KEY_URL);
        i++;
    }
    return s;
}

// Secret Salt: "MEGAMU_DONPV_2026_NATIVE_SECURE_TOKEN_#89a1" (XOR key: 0x6D)
static const unsigned char ENC_SECRET_SALT[] = {
    0x20, 0x28, 0x2A, 0x2C, 0x20, 0x38, 0x32, 0x29, 0x22, 0x23, 0x3D, 0x3B, 0x32, 0x5F, 0x5D, 0x5F,
    0x5B, 0x32, 0x23, 0x2C, 0x39, 0x24, 0x3B, 0x28, 0x32, 0x3E, 0x28, 0x2E, 0x38, 0x3F, 0x28, 0x32,
    0x39, 0x22, 0x26, 0x28, 0x23, 0x32, 0x4E, 0x55, 0x54, 0x0C, 0x5C, 0x00
};
static const unsigned char XOR_KEY_SALT = 0x6D;

static std::string GetDecryptedSecretSalt() {
    std::string s = "";
    int i = 0;
    while (ENC_SECRET_SALT[i] != 0x00) {
        s += (char)(ENC_SECRET_SALT[i] ^ XOR_KEY_SALT);
        i++;
    }
    return s;
}

// ==============================================================================
// 2. MÃ HÓA NATIVE GAME OFFSETS (CHỈ GIẢI MÃ KHI BẢN QUYỀN HỢP LỆ)
// ==============================================================================
static const unsigned char ENC_GAME_OFFSETS[] = {
    0x2C, 0x75, 0x30, 0x36, 0x3A, 0x32, 0x08, 0x3A, 0x38, 0x33, 0x22, 0x3B, 0x32, 0x75, 0x6D, 0x77,
    0x75, 0x10, 0x36, 0x3A, 0x32, 0x16, 0x24, 0x24, 0x32, 0x3A, 0x35, 0x3B, 0x2E, 0x79, 0x33, 0x3B,
    0x3B, 0x75, 0x7B, 0x77, 0x75, 0x30, 0x32, 0x23, 0x08, 0x27, 0x3B, 0x36, 0x2E, 0x32, 0x25, 0x75,
    0x6D, 0x77, 0x75, 0x67, 0x2F, 0x66, 0x65, 0x64, 0x66, 0x67, 0x13, 0x67, 0x75, 0x7B, 0x77, 0x75,
    0x3A, 0x38, 0x21, 0x32, 0x08, 0x23, 0x38, 0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x13, 0x60, 0x65,
    0x60, 0x62, 0x67, 0x75, 0x7B, 0x77, 0x75, 0x34, 0x3F, 0x36, 0x23, 0x08, 0x24, 0x32, 0x39, 0x33,
    0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x66, 0x63, 0x15, 0x6E, 0x65, 0x62, 0x67, 0x75, 0x7B, 0x77,
    0x75, 0x34, 0x3F, 0x36, 0x23, 0x08, 0x22, 0x27, 0x33, 0x36, 0x23, 0x32, 0x75, 0x6D, 0x77, 0x75,
    0x67, 0x2F, 0x66, 0x63, 0x15, 0x61, 0x16, 0x11, 0x67, 0x75, 0x7B, 0x77, 0x75, 0x3F, 0x32, 0x3B,
    0x27, 0x32, 0x25, 0x08, 0x24, 0x23, 0x36, 0x25, 0x23, 0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x65,
    0x16, 0x64, 0x15, 0x62, 0x6F, 0x67, 0x75, 0x7B, 0x77, 0x75, 0x3F, 0x32, 0x3B, 0x27, 0x32, 0x25,
    0x08, 0x24, 0x23, 0x38, 0x27, 0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x65, 0x16, 0x64, 0x14, 0x61,
    0x61, 0x67, 0x75, 0x7B, 0x77, 0x75, 0x27, 0x3B, 0x36, 0x2E, 0x32, 0x25, 0x08, 0x39, 0x36, 0x3A,
    0x32, 0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x65, 0x6F, 0x75, 0x7B, 0x77, 0x75, 0x27, 0x3B, 0x36,
    0x2E, 0x32, 0x25, 0x08, 0x3B, 0x32, 0x21, 0x32, 0x3B, 0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x64,
    0x67, 0x75, 0x7B, 0x77, 0x75, 0x27, 0x3B, 0x36, 0x2E, 0x32, 0x25, 0x08, 0x34, 0x3B, 0x36, 0x24,
    0x24, 0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x64, 0x63, 0x75, 0x7B, 0x77, 0x75, 0x27, 0x3B, 0x36,
    0x2E, 0x32, 0x25, 0x08, 0x34, 0x38, 0x38, 0x25, 0x33, 0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x61,
    0x6F, 0x75, 0x7B, 0x77, 0x75, 0x27, 0x3B, 0x36, 0x2E, 0x32, 0x25, 0x08, 0x3A, 0x38, 0x21, 0x32,
    0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x11, 0x67, 0x75, 0x7B, 0x77, 0x75, 0x27, 0x3B, 0x36, 0x2E,
    0x32, 0x25, 0x08, 0x3F, 0x32, 0x3B, 0x27, 0x32, 0x25, 0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x66,
    0x12, 0x6F, 0x75, 0x7B, 0x77, 0x75, 0x27, 0x3B, 0x36, 0x2E, 0x32, 0x25, 0x08, 0x3B, 0x36, 0x24,
    0x23, 0x08, 0x34, 0x38, 0x38, 0x25, 0x33, 0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x63, 0x12, 0x67,
    0x75, 0x7B, 0x77, 0x75, 0x3A, 0x38, 0x21, 0x32, 0x08, 0x31, 0x3B, 0x36, 0x30, 0x75, 0x6D, 0x77,
    0x75, 0x67, 0x2F, 0x64, 0x14, 0x75, 0x7B, 0x77, 0x75, 0x3F, 0x32, 0x3B, 0x27, 0x32, 0x25, 0x08,
    0x24, 0x23, 0x36, 0x23, 0x32, 0x75, 0x6D, 0x77, 0x75, 0x67, 0x2F, 0x65, 0x67, 0x75, 0x2A, 0x00
};
static const unsigned char XOR_KEY_OFFSETS = 0x57;


static std::string GetDecryptedOffsetsJson() {
    std::string s = "";
    int i = 0;
    while (ENC_GAME_OFFSETS[i] != 0x00) {
        s += (char)(ENC_GAME_OFFSETS[i] ^ XOR_KEY_OFFSETS);
        i++;
    }
    return s;
}

// ==============================================================================
// 3. ANTI-DEBUGGING (PHÁT HIỆN TOOL HACK / DEBUGGER X64DBG, CHEAT ENGINE)
// ==============================================================================
static bool CheckDebuggerPresent() {
    if (IsDebuggerPresent()) return true;

    BOOL isRemote = FALSE;
    if (CheckRemoteDebuggerPresent(GetCurrentProcess(), &isRemote) && isRemote) {
        return true;
    }
    return false;
}

// ==============================================================================
// 4. MẬT MÃ SHA-256 & RFC 2104 HMAC-SHA256 (100% C++ TỰ CHỨA - ZERO DEPENDENCY)
// ==============================================================================
namespace NativeCrypto {
    static inline uint32_t ror(uint32_t val, uint32_t shift) {
        return (val >> shift) | (val << (32 - shift));
    }
    static inline uint32_t ch(uint32_t x, uint32_t y, uint32_t z) { return (x & y) ^ (~x & z); }
    static inline uint32_t maj(uint32_t x, uint32_t y, uint32_t z) { return (x & y) ^ (x & z) ^ (y & z); }
    static inline uint32_t ep0(uint32_t x) { return ror(x, 2) ^ ror(x, 13) ^ ror(x, 22); }
    static inline uint32_t ep1(uint32_t x) { return ror(x, 6) ^ ror(x, 11) ^ ror(x, 25); }
    static inline uint32_t sig0(uint32_t x) { return ror(x, 7) ^ ror(x, 18) ^ (x >> 3); }
    static inline uint32_t sig1(uint32_t x) { return ror(x, 17) ^ ror(x, 19) ^ (x >> 10); }

    static const uint32_t K[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    };

    struct Sha256Ctx {
        uint32_t state[8];
        uint64_t bitlen;
        uint8_t data[64];
        uint32_t datalen;
    };

    static void Sha256Transform(Sha256Ctx* ctx, const uint8_t data[]) {
        uint32_t m[64], a, b, c, d, e, f, g, h;
        for (int i = 0, j = 0; i < 16; ++i, j += 4)
            m[i] = (data[j] << 24) | (data[j + 1] << 16) | (data[j + 2] << 8) | (data[j + 3]);
        for (int i = 16; i < 64; ++i)
            m[i] = sig1(m[i - 2]) + m[i - 7] + sig0(m[i - 15]) + m[i - 16];

        a = ctx->state[0]; b = ctx->state[1]; c = ctx->state[2]; d = ctx->state[3];
        e = ctx->state[4]; f = ctx->state[5]; g = ctx->state[6]; h = ctx->state[7];

        for (int i = 0; i < 64; ++i) {
            uint32_t t1 = h + ep1(e) + ch(e, f, g) + K[i] + m[i];
            uint32_t t2 = ep0(a) + maj(a, b, c);
            h = g; g = f; f = e; e = d + t1;
            d = c; c = b; b = a; a = t1 + t2;
        }
        ctx->state[0] += a; ctx->state[1] += b; ctx->state[2] += c; ctx->state[3] += d;
        ctx->state[4] += e; ctx->state[5] += f; ctx->state[6] += g; ctx->state[7] += h;
    }

    static void Sha256Init(Sha256Ctx* ctx) {
        ctx->datalen = 0;
        ctx->bitlen = 0;
        ctx->state[0] = 0x6a09e667; ctx->state[1] = 0xbb67ae85;
        ctx->state[2] = 0x3c6ef372; ctx->state[3] = 0xa54ff53a;
        ctx->state[4] = 0x510e527f; ctx->state[5] = 0x9b05688c;
        ctx->state[6] = 0x1f83d9ab; ctx->state[7] = 0x5be0cd19;
    }

    static void Sha256Update(Sha256Ctx* ctx, const uint8_t data[], size_t len) {
        for (size_t i = 0; i < len; ++i) {
            ctx->data[ctx->datalen] = data[i];
            ctx->datalen++;
            if (ctx->datalen == 64) {
                Sha256Transform(ctx, ctx->data);
                ctx->bitlen += 512;
                ctx->datalen = 0;
            }
        }
    }

    static void Sha256Final(Sha256Ctx* ctx, uint8_t hash[32]) {
        size_t i = ctx->datalen;
        ctx->data[i++] = 0x80;
        if (i > 56) {
            while (i < 64) ctx->data[i++] = 0x00;
            Sha256Transform(ctx, ctx->data);
            i = 0;
        }
        while (i < 56) ctx->data[i++] = 0x00;
        ctx->bitlen += ctx->datalen * 8;
        ctx->data[63] = (uint8_t)(ctx->bitlen);
        ctx->data[62] = (uint8_t)(ctx->bitlen >> 8);
        ctx->data[61] = (uint8_t)(ctx->bitlen >> 16);
        ctx->data[60] = (uint8_t)(ctx->bitlen >> 24);
        ctx->data[59] = (uint8_t)(ctx->bitlen >> 32);
        ctx->data[58] = (uint8_t)(ctx->bitlen >> 40);
        ctx->data[57] = (uint8_t)(ctx->bitlen >> 48);
        ctx->data[56] = (uint8_t)(ctx->bitlen >> 56);
        Sha256Transform(ctx, ctx->data);

        for (int j = 0; j < 4; ++j) {
            hash[j]      = (uint8_t)((ctx->state[0] >> (24 - j * 8)) & 0x000000ff);
            hash[j + 4]  = (uint8_t)((ctx->state[1] >> (24 - j * 8)) & 0x000000ff);
            hash[j + 8]  = (uint8_t)((ctx->state[2] >> (24 - j * 8)) & 0x000000ff);
            hash[j + 12] = (uint8_t)((ctx->state[3] >> (24 - j * 8)) & 0x000000ff);
            hash[j + 16] = (uint8_t)((ctx->state[4] >> (24 - j * 8)) & 0x000000ff);
            hash[j + 20] = (uint8_t)((ctx->state[5] >> (24 - j * 8)) & 0x000000ff);
            hash[j + 24] = (uint8_t)((ctx->state[6] >> (24 - j * 8)) & 0x000000ff);
            hash[j + 28] = (uint8_t)((ctx->state[7] >> (24 - j * 8)) & 0x000000ff);
        }
    }

    static std::vector<uint8_t> RawSha256(const uint8_t* data, size_t len) {
        Sha256Ctx ctx;
        Sha256Init(&ctx);
        Sha256Update(&ctx, data, len);
        std::vector<uint8_t> hash(32);
        Sha256Final(&ctx, hash.data());
        return hash;
    }

    static std::string HexSha256Upper(const std::string& input) {
        std::vector<uint8_t> h = RawSha256((const uint8_t*)input.data(), input.length());
        const char hexDigits[] = "0123456789ABCDEF";
        std::string hexStr = "";
        for (size_t i = 0; i < 32; ++i) {
            hexStr += hexDigits[(h[i] >> 4) & 0x0F];
            hexStr += hexDigits[h[i] & 0x0F];
        }
        return hexStr;
    }

    static std::string ComputeHmacSha256(const std::string& data, const std::string& key) {
        const size_t BLOCK_SIZE = 64;
        uint8_t k0[BLOCK_SIZE] = { 0 };

        if (key.length() > BLOCK_SIZE) {
            std::vector<uint8_t> keyHash = RawSha256((const uint8_t*)key.data(), key.length());
            memcpy(k0, keyHash.data(), 32);
        } else {
            memcpy(k0, key.data(), key.length());
        }

        uint8_t ipad[BLOCK_SIZE];
        uint8_t opad[BLOCK_SIZE];
        for (size_t i = 0; i < BLOCK_SIZE; ++i) {
            ipad[i] = k0[i] ^ 0x36;
            opad[i] = k0[i] ^ 0x5C;
        }

        std::vector<uint8_t> innerData(BLOCK_SIZE + data.length());
        memcpy(innerData.data(), ipad, BLOCK_SIZE);
        memcpy(innerData.data() + BLOCK_SIZE, data.data(), data.length());
        std::vector<uint8_t> innerHash = RawSha256(innerData.data(), innerData.size());

        std::vector<uint8_t> outerData(BLOCK_SIZE + 32);
        memcpy(outerData.data(), opad, BLOCK_SIZE);
        memcpy(outerData.data() + BLOCK_SIZE, innerHash.data(), 32);
        std::vector<uint8_t> outerHash = RawSha256(outerData.data(), outerData.size());

        const char hexDigits[] = "0123456789abcdef";
        std::string hexStr = "";
        for (size_t i = 0; i < 32; ++i) {
            hexStr += hexDigits[(outerHash[i] >> 4) & 0x0F];
            hexStr += hexDigits[outerHash[i] & 0x0F];
        }
        return hexStr;
    }
}

// Trích xuất giá trị String an toàn từ JSON
static std::string ExtractJsonField(const std::string& json, const std::string& field) {
    std::string keyPattern = "\"" + field + "\"";
    size_t pos = json.find(keyPattern);
    if (pos == std::string::npos) return "";

    pos = json.find(':', pos + keyPattern.length());
    if (pos == std::string::npos) return "";

    while (pos < json.length() && (json[pos] == ':' || json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\r' || json[pos] == '\n')) {
        pos++;
    }
    if (pos >= json.length()) return "";

    if (json[pos] == '"') {
        size_t endQ = json.find('"', pos + 1);
        if (endQ != std::string::npos) {
            return json.substr(pos + 1, endQ - pos - 1);
        }
        return "";
    }

    size_t endVal = json.find_first_of(",}\r\n ", pos);
    if (endVal == std::string::npos) endVal = json.length();
    return json.substr(pos, endVal - pos);
}

// ==============================================================================
// 5. THU THẬP HWID VÀ WINHTTP NATIVE
// ==============================================================================
static std::string GetRawMachineGuid() {
    HKEY hKey;
    char buffer[256] = { 0 };
    DWORD dwSize = sizeof(buffer);

    LSTATUS status = RegOpenKeyExA(
        HKEY_LOCAL_MACHINE,
        "SOFTWARE\\Microsoft\\Cryptography",
        0,
        KEY_READ | KEY_WOW64_64KEY,
        &hKey
    );

    if (status == ERROR_SUCCESS) {
        status = RegQueryValueExA(hKey, "MachineGuid", NULL, NULL, (LPBYTE)buffer, &dwSize);
        RegCloseKey(hKey);
    }

    if (status != ERROR_SUCCESS || buffer[0] == '\0') {
        char compName[MAX_COMPUTERNAME_LENGTH + 1] = { 0 };
        DWORD compSize = sizeof(compName);
        GetComputerNameA(compName, &compSize);
        return std::string("FALLBACK-") + compName;
    }
    return std::string(buffer);
}

static std::wstring Utf8ToWide(const std::string& str) {
    if (str.empty()) return L"";
    int sizeNeeded = MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.size(), NULL, 0);
    std::wstring wstr(sizeNeeded, 0);
    MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.size(), &wstr[0], sizeNeeded);
    return wstr;
}

struct ParsedUrl {
    std::wstring host;
    INTERNET_PORT port;
    std::wstring path;
    bool isHttps;
};

static bool ParseHttpUrl(const std::string& urlStr, ParsedUrl& out) {
    std::wstring wUrl = Utf8ToWide(urlStr);
    URL_COMPONENTSW urlComp = { 0 };
    urlComp.dwStructSize = sizeof(urlComp);
    
    wchar_t hostBuf[256] = { 0 };
    wchar_t pathBuf[1024] = { 0 };
    
    urlComp.lpszHostName = hostBuf;
    urlComp.dwHostNameLength = sizeof(hostBuf) / sizeof(wchar_t);
    urlComp.lpszUrlPath = pathBuf;
    urlComp.dwUrlPathLength = sizeof(pathBuf) / sizeof(wchar_t);

    if (!WinHttpCrackUrl(wUrl.c_str(), (DWORD)wUrl.length(), 0, &urlComp)) {
        return false;
    }

    out.host = hostBuf;
    out.port = urlComp.nPort;
    out.path = pathBuf;
    out.isHttps = (urlComp.nScheme == INTERNET_SCHEME_HTTPS);
    return true;
}

static bool HttpPostJson(const std::string& fullUrl, const std::string& jsonPayload, std::string& outResponse, int timeoutMs = 8000) {
    ParsedUrl parsed;
    if (!ParseHttpUrl(fullUrl, parsed)) {
        outResponse = "{\"success\":false,\"message\":\"C++ Bridge: Invalid Server URL\"}";
        return false;
    }

    HINTERNET hSession = WinHttpOpen(
        L"MEGAMU-SecureBridge/2.0",
        WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        0
    );
    if (!hSession) {
        outResponse = "{\"success\":false,\"message\":\"C++ Bridge: WinHttpOpen failed\"}";
        return false;
    }

    WinHttpSetTimeouts(hSession, timeoutMs, timeoutMs, timeoutMs, timeoutMs);

    HINTERNET hConnect = WinHttpConnect(hSession, parsed.host.c_str(), parsed.port, 0);
    if (!hConnect) {
        WinHttpCloseHandle(hSession);
        outResponse = "{\"success\":false,\"message\":\"C++ Bridge: WinHttpConnect failed\"}";
        return false;
    }

    DWORD reqFlags = parsed.isHttps ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(
        hConnect,
        L"POST",
        parsed.path.c_str(),
        NULL,
        WINHTTP_NO_REFERER,
        WINHTTP_DEFAULT_ACCEPT_TYPES,
        reqFlags
    );

    if (!hRequest) {
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);
        outResponse = "{\"success\":false,\"message\":\"C++ Bridge: WinHttpOpenRequest failed\"}";
        return false;
    }

    if (parsed.isHttps) {
        DWORD dwSecurityFlags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
                                SECURITY_FLAG_IGNORE_CERT_CN_INVALID |
                                SECURITY_FLAG_IGNORE_CERT_DATE_INVALID |
                                SECURITY_FLAG_IGNORE_CERT_WRONG_USAGE;
        WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &dwSecurityFlags, sizeof(dwSecurityFlags));
    }

    LPCWSTR headers = L"Content-Type: application/json\r\nAccept: application/json\r\n";
    DWORD headersLen = (DWORD)wcslen(headers);

    std::string postData = jsonPayload;
    BOOL bSend = WinHttpSendRequest(
        hRequest,
        headers,
        headersLen,
        (LPVOID)postData.c_str(),
        (DWORD)postData.length(),
        (DWORD)postData.length(),
        0
    );

    if (!bSend) {
        WinHttpCloseHandle(hRequest);
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);
        outResponse = "{\"success\":false,\"message\":\"C++ Bridge: Could not send request to server\"}";
        return false;
    }

    BOOL bRecv = WinHttpReceiveResponse(hRequest, NULL);
    if (!bRecv) {
        WinHttpCloseHandle(hRequest);
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);
        outResponse = "{\"success\":false,\"message\":\"C++ Bridge: No response from server\"}";
        return false;
    }

    std::string responseBody = "";
    DWORD dwSize = 0;
    do {
        DWORD dwDownloaded = 0;
        if (!WinHttpQueryDataAvailable(hRequest, &dwSize)) break;
        if (dwSize == 0) break;

        std::vector<char> buffer(dwSize + 1, 0);
        if (WinHttpReadData(hRequest, &buffer[0], dwSize, &dwDownloaded)) {
            responseBody.append(&buffer[0], dwDownloaded);
        }
    } while (dwSize > 0);

    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    WinHttpCloseHandle(hSession);

    outResponse = responseBody;
    return true;
}

static std::string JsonEscape(const std::string& s) {
    std::ostringstream o;
    for (auto c = s.cbegin(); c != s.cend(); ++c) {
        if (*c == '"' || *c == '\\' || ('\x00' <= *c && *c <= '\x1f')) {
            o << "\\u" << std::hex << std::setw(4) << std::setfill('0') << (int)*c;
        } else {
            o << *c;
        }
    }
    return o.str();
}

static std::string ToUpperStr(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), ::toupper);
    return s;
}

// ==============================================================================
// 6. EXPORTED C API DÀNH CHO APP PYTHON / C++
// ==============================================================================

// Lấy phiên bản Bridge C++
BRIDGE_API int Bridge_GetVersion() {
    return 200; // v2.0.0
}

// Thiết lập URL API máy chủ nếu cần cấu hình động
BRIDGE_API void Bridge_SetApiUrl(const char* url) {
    if (url && url[0]) {
        g_customServerUrl = url;
    }
}

// Lấy HWID máy tính duy nhất
BRIDGE_API int Bridge_GetHwid(char* outBuffer, int maxLen) {
    if (!outBuffer || maxLen <= 0) return 0;
    std::string guid = GetRawMachineGuid();
    std::string hash = NativeCrypto::HexSha256Upper(guid);
    std::string hwid16 = hash.substr(0, 16);
    strncpy_s(outBuffer, maxLen, hwid16.c_str(), _TRUNCATE);
    return 1;
}

// Kiểm tra trạng thái xác thực mật mã hiện tại
BRIDGE_API int Bridge_IsAuthenticated() {
    if (CheckDebuggerPresent()) {
        g_isLicenseAuthenticated = false;
        return 0;
    }
    return g_isLicenseAuthenticated ? 1 : 0;
}

// Kích hoạt License qua Laravel API và xác thực chữ ký HMAC
BRIDGE_API int Bridge_ActivateLicense(
    const char* serverUrl,
    const char* licenseKey,
    const char* productCode,
    const char* clientVersion,
    char* outJson,
    int maxLen
) {
    if (!licenseKey || !outJson || maxLen <= 0) return 0;

    // Kiểm tra debugger
    if (CheckDebuggerPresent()) {
        g_isLicenseAuthenticated = false;
        strncpy_s(outJson, maxLen, "{\"success\":false,\"message\":\"Debugger detected! Access denied.\"}", _TRUNCATE);
        return 0;
    }

    char hwidBuf[64] = { 0 };
    Bridge_GetHwid(hwidBuf, sizeof(hwidBuf));

    char compName[MAX_COMPUTERNAME_LENGTH + 1] = { 0 };
    DWORD compSize = sizeof(compName);
    GetComputerNameA(compName, &compSize);

    std::string srv = (serverUrl && serverUrl[0]) ? serverUrl : GetDecryptedDefaultUrl();
    while (!srv.empty() && srv.back() == '/') srv.pop_back();
    std::string fullUrl = srv + "/api/v1/license/activate";

    std::string pCode = (productCode && productCode[0]) ? productCode : "megamu-navigator";
    std::string cVer = (clientVersion && clientVersion[0]) ? clientVersion : "v1.5.1";

    std::ostringstream jsonStream;
    jsonStream << "{"
               << "\"license_key\":\"" << JsonEscape(licenseKey) << "\","
               << "\"hwid\":\"" << JsonEscape(hwidBuf) << "\","
               << "\"machine_name\":\"" << JsonEscape(compName) << "\","
               << "\"client_version\":\"" << JsonEscape(cVer) << "\","
               << "\"product_code\":\"" << JsonEscape(pCode) << "\""
               << "}";

    std::string response;
    bool success = HttpPostJson(fullUrl, jsonStream.str(), response, 10000);

    if (success) {
        std::string isSuccess = ExtractJsonField(response, "success");
        if (isSuccess == "true") {
            // Xác minh chữ ký số trả về từ Laravel
            std::string serverSig = ExtractJsonField(response, "signature");
            std::string secretSalt = GetDecryptedSecretSalt();
            std::string expectedPayload = ToUpperStr(licenseKey) + "|" + ToUpperStr(hwidBuf) + "|active";
            std::string expectedSig = NativeCrypto::ComputeHmacSha256(expectedPayload, secretSalt);

            if (!serverSig.empty() && _stricmp(serverSig.c_str(), expectedSig.c_str()) == 0) {
                g_isLicenseAuthenticated = true;
            } else {
                g_isLicenseAuthenticated = false;
                response = "{\"success\":false,\"message\":\"Chữ ký bảo mật không khớp! Phát hiện giả mạo máy chủ.\"}";
            }
        } else {
            // Giữ nguyên thông báo lỗi chính xác từ Laravel Server (sai key, hết hạn, đổi máy...)
            g_isLicenseAuthenticated = false;
        }
    } else {
        g_isLicenseAuthenticated = false;
        response = "{\"success\":false,\"message\":\"Không thể kết nối đến máy chủ bản quyền! Vui lòng kiểm tra mạng.\"}";
    }

    strncpy_s(outJson, maxLen, response.c_str(), _TRUNCATE);
    return g_isLicenseAuthenticated ? 1 : 0;
}

// Xác thực định kỳ License qua Laravel API và kiểm tra chữ ký HMAC
BRIDGE_API int Bridge_VerifyLicense(
    const char* serverUrl,
    const char* licenseKey,
    const char* clientVersion,
    char* outJson,
    int maxLen
) {
    if (!licenseKey || !outJson || maxLen <= 0) return 0;

    // Kiểm tra debugger
    if (CheckDebuggerPresent()) {
        g_isLicenseAuthenticated = false;
        strncpy_s(outJson, maxLen, "{\"valid\":false,\"status\":\"debugger_detected\",\"message\":\"Debugger detected!\"}", _TRUNCATE);
        return 0;
    }

    char hwidBuf[64] = { 0 };
    Bridge_GetHwid(hwidBuf, sizeof(hwidBuf));

    std::string srv = (serverUrl && serverUrl[0]) ? serverUrl : GetDecryptedDefaultUrl();
    while (!srv.empty() && srv.back() == '/') srv.pop_back();
    std::string fullUrl = srv + "/api/v1/license/verify";

    std::string cVer = (clientVersion && clientVersion[0]) ? clientVersion : "v1.5.1";

    std::ostringstream jsonStream;
    jsonStream << "{"
               << "\"license_key\":\"" << JsonEscape(licenseKey) << "\","
               << "\"hwid\":\"" << JsonEscape(hwidBuf) << "\","
               << "\"client_version\":\"" << JsonEscape(cVer) << "\""
               << "}";

    std::string response;
    bool success = HttpPostJson(fullUrl, jsonStream.str(), response, 8000);

    if (success) {
        std::string isValid = ExtractJsonField(response, "valid");
        std::string status = ExtractJsonField(response, "status");
        std::string serverSig = ExtractJsonField(response, "signature");

        if (isValid == "true" && status == "active") {
            // Xác thực chữ ký HMAC chống Proxy Fiddler
            std::string secretSalt = GetDecryptedSecretSalt();
            std::string expectedPayload = ToUpperStr(licenseKey) + "|" + ToUpperStr(hwidBuf) + "|active";
            std::string expectedSig = NativeCrypto::ComputeHmacSha256(expectedPayload, secretSalt);

            if (!serverSig.empty() && _stricmp(serverSig.c_str(), expectedSig.c_str()) == 0) {
                g_isLicenseAuthenticated = true;
            } else {
                g_isLicenseAuthenticated = false;
                response = "{\"valid\":false,\"status\":\"tampered\",\"message\":\"Chữ ký bảo mật không khớp! Phát hiện giả mạo máy chủ.\"}";
            }
        } else {
            g_isLicenseAuthenticated = false;
        }
    } else {
        g_isLicenseAuthenticated = false;
    }

    strncpy_s(outJson, maxLen, response.c_str(), _TRUNCATE);
    return g_isLicenseAuthenticated ? 1 : 0;
}

// Xác thực chữ ký số Offline trực tiếp từ file license local (HMAC-SHA256 theo HWID)
BRIDGE_API int Bridge_VerifyOfflineSignature(const char* licenseKey, const char* signature) {
    if (!licenseKey || !signature || !licenseKey[0] || !signature[0]) return 0;
    if (CheckDebuggerPresent()) {
        g_isLicenseAuthenticated = false;
        return 0;
    }
    char hwidBuf[64] = { 0 };
    Bridge_GetHwid(hwidBuf, sizeof(hwidBuf));
    std::string secretSalt = GetDecryptedSecretSalt();
    std::string expectedPayload = ToUpperStr(licenseKey) + "|" + ToUpperStr(hwidBuf) + "|active";
    std::string expectedSig = NativeCrypto::ComputeHmacSha256(expectedPayload, secretSalt);

    if (!expectedSig.empty() && _stricmp(signature, expectedSig.c_str()) == 0) {
        g_isLicenseAuthenticated = true;
        return 1;
    }
    return 0;
}

// Giải mã Game Offsets - CHỈ CẤP KHI BẢN QUYỀN ĐÃ XÁC THỰC MẬT MÃ THÀNH CÔNG
// Nếu cracker patch Python để bỏ qua màn hình khóa, hàm này vẫn trả về rỗng và Engine không thể chạy!
BRIDGE_API int Bridge_GetGameOffsets(char* outJson, int maxLen) {
    if (!outJson || maxLen <= 0) return 0;

    // Kiểm tra debugger và tính hợp lệ bản quyền
    if (CheckDebuggerPresent() || !g_isLicenseAuthenticated) {
        strncpy_s(outJson, maxLen, "{}", _TRUNCATE);
        return 0;
    }

    std::string offsets = GetDecryptedOffsetsJson();
    strncpy_s(outJson, maxLen, offsets.c_str(), _TRUNCATE);
    return 1;
}
