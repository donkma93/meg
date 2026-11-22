// ==============================================================================
// MEGATEAM MEGAMU NATIVE C++ SECURITY BRIDGE DLL (v3.0 - ZERO-OFFSET-ON-DISK)
// ==============================================================================
// 4 LỚP BẢO VỆ CAO CẤP:
// LỚP 1: Mã hóa XOR URL Server & Secret Token (Không lưu chuỗi Plaintext trong DLL)
// LỚP 2: Chữ ký số HMAC-SHA256 + Nonce ngẫu nhiên chống Proxy / Fiddler / Replay
// LỚP 3: ZERO Hardcoded Offsets — Offsets chỉ được Server mã hóa AES-256-CBC + HMAC
//        theo khóa phiên dùng 1 lần, giải mã vào vùng RAM ẩn (che phủ bởi khóa ngẫu nhiên
//        theo từng tiến trình) và xóa sạch bằng SecureZeroMemory khi đóng/hết hạn!
// LỚP 4: Anti-Debugging + Xác thực chứng chỉ HTTPS thật cho máy chủ từ xa
// ==============================================================================

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>
#include <bcrypt.h>
#include <string>
#include <sstream>
#include <iomanip>
#include <vector>
#include <algorithm>
#include <cstring>
#include <cstdint>
#include <mutex>

#pragma comment(lib, "winhttp.lib")
#pragma comment(lib, "bcrypt.lib")
#pragma comment(lib, "advapi32.lib")

#define BRIDGE_API extern "C" __declspec(dllexport)

// ==============================================================================
// TRẠNG THÁI XÁC THỰC & KHO LƯU TRỮ OFFSET CHỈ NẰM TRÊN RAM (KHÔNG LƯU ĐĨA)
// ==============================================================================
static std::mutex g_vaultMutex;
static volatile bool g_isLicenseAuthenticated = false;
static std::string g_customServerUrl = "";
static std::vector<uint8_t> g_ramMaskedOffsets;   // JSON offsets đã che phủ XOR bởi khóa runtime
static uint8_t g_ramMaskKey[32] = { 0 };
static bool g_ramMaskKeyReady = false;

static void SecureWipeString(std::string& s) {
    if (!s.empty()) {
        SecureZeroMemory(&s[0], s.size());
        s.clear();
    }
}

static void SecureWipeVec(std::vector<uint8_t>& v) {
    if (!v.empty()) {
        SecureZeroMemory(v.data(), v.size());
        v.clear();
    }
}

static void EnsureRamMaskKey() {
    if (!g_ramMaskKeyReady) {
        if (BCryptGenRandom(NULL, g_ramMaskKey, sizeof(g_ramMaskKey), BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0) {
            // Fallback PRNG phòng hờ
            uint64_t seed = GetTickCount64() ^ (uint64_t)GetCurrentProcessId() ^ (uintptr_t)&g_ramMaskKey;
            for (size_t i = 0; i < sizeof(g_ramMaskKey); ++i) {
                seed = seed * 6364136223846793005ULL + 1442695040888963407ULL;
                g_ramMaskKey[i] = (uint8_t)(seed >> 56);
            }
        }
        g_ramMaskKeyReady = true;
    }
}

static void ClearRamOffsetsLocked() {
    SecureWipeVec(g_ramMaskedOffsets);
}

static void StoreRamOffsetsLocked(const std::string& plainJson) {
    ClearRamOffsetsLocked();
    if (plainJson.empty()) return;
    EnsureRamMaskKey();
    g_ramMaskedOffsets.resize(plainJson.size());
    for (size_t i = 0; i < plainJson.size(); ++i) {
        g_ramMaskedOffsets[i] = ((uint8_t)plainJson[i]) ^ g_ramMaskKey[i & 31];
    }
}

static std::string LoadRamOffsetsLocked() {
    if (g_ramMaskedOffsets.empty() || !g_ramMaskKeyReady) return "";
    std::string out(g_ramMaskedOffsets.size(), '\0');
    for (size_t i = 0; i < g_ramMaskedOffsets.size(); ++i) {
        out[i] = (char)(g_ramMaskedOffsets[i] ^ g_ramMaskKey[i & 31]);
    }
    return out;
}

// ==============================================================================
// 1. MÃ HÓA XOR CHUỖI NHẠY CẢM (URL VÀ SECRET TOKEN) — ZERO OFFSET TRONG DLL
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

// Secret Salt (XOR key: 0x6D)
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
// 2. ANTI-DEBUGGING
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
// 3. MẬT MÃ SHA-256, HMAC-SHA256, BASE64 & WINDOWS CNG AES-256-CBC
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

    static std::vector<uint8_t> RawHmacSha256(const uint8_t* data, size_t dataLen, const uint8_t* key, size_t keyLen) {
        const size_t BLOCK_SIZE = 64;
        uint8_t k0[BLOCK_SIZE] = { 0 };

        if (keyLen > BLOCK_SIZE) {
            std::vector<uint8_t> keyHash = RawSha256(key, keyLen);
            memcpy(k0, keyHash.data(), 32);
        } else {
            memcpy(k0, key, keyLen);
        }

        uint8_t ipad[BLOCK_SIZE];
        uint8_t opad[BLOCK_SIZE];
        for (size_t i = 0; i < BLOCK_SIZE; ++i) {
            ipad[i] = k0[i] ^ 0x36;
            opad[i] = k0[i] ^ 0x5C;
        }

        std::vector<uint8_t> innerData(BLOCK_SIZE + dataLen);
        memcpy(innerData.data(), ipad, BLOCK_SIZE);
        if (dataLen > 0) memcpy(innerData.data() + BLOCK_SIZE, data, dataLen);
        std::vector<uint8_t> innerHash = RawSha256(innerData.data(), innerData.size());

        std::vector<uint8_t> outerData(BLOCK_SIZE + 32);
        memcpy(outerData.data(), opad, BLOCK_SIZE);
        memcpy(outerData.data() + BLOCK_SIZE, innerHash.data(), 32);
        std::vector<uint8_t> outerHash = RawSha256(outerData.data(), outerData.size());

        SecureZeroMemory(k0, sizeof(k0));
        SecureZeroMemory(ipad, sizeof(ipad));
        SecureZeroMemory(opad, sizeof(opad));
        return outerHash;
    }

    static std::string ComputeHmacSha256(const std::string& data, const std::string& key) {
        std::vector<uint8_t> outerHash = RawHmacSha256(
            (const uint8_t*)data.data(), data.length(),
            (const uint8_t*)key.data(), key.length()
        );
        const char hexDigits[] = "0123456789abcdef";
        std::string hexStr = "";
        for (size_t i = 0; i < 32; ++i) {
            hexStr += hexDigits[(outerHash[i] >> 4) & 0x0F];
            hexStr += hexDigits[outerHash[i] & 0x0F];
        }
        return hexStr;
    }

    static bool ConstantTimeEquals(const uint8_t* a, const uint8_t* b, size_t len) {
        uint8_t diff = 0;
        for (size_t i = 0; i < len; ++i) {
            diff |= (uint8_t)(a[i] ^ b[i]);
        }
        return diff == 0;
    }

    static std::string GenerateRandomHexNonce(size_t numBytes = 16) {
        std::vector<uint8_t> buf(numBytes, 0);
        if (BCryptGenRandom(NULL, buf.data(), (ULONG)buf.size(), BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0) {
            uint64_t seed = GetTickCount64() ^ ((uint64_t)GetCurrentProcessId() << 16) ^ (uintptr_t)buf.data();
            for (size_t i = 0; i < numBytes; ++i) {
                seed = seed * 6364136223846793005ULL + 1442695040888963407ULL;
                buf[i] = (uint8_t)(seed >> 56);
            }
        }
        const char hexDigits[] = "0123456789abcdef";
        std::string out;
        out.reserve(numBytes * 2);
        for (uint8_t b : buf) {
            out += hexDigits[(b >> 4) & 0x0F];
            out += hexDigits[b & 0x0F];
        }
        return out;
    }

    static bool Base64Decode(const std::string& in, std::vector<uint8_t>& out) {
        static const int T[256] = {
            -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
            -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,62,-1,-1,-1,63,52,53,54,55,56,57,58,59,60,61,-1,-1,-1,-2,-1,-1,
            -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,-1,-1,-1,-1,-1,
            -1,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,-1,-1,-1,-1,-1,
            -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
            -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
            -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
            -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1
        };
        out.clear();
        int val = 0, valb = -8;
        for (unsigned char c : in) {
            if (c == '\\') continue; // JSON-escaped "\/" tolerance
            int d = T[c];
            if (d == -1) {
                if (c == ' ' || c == '\r' || c == '\n' || c == '\t') continue;
                return false;
            }
            if (d == -2) break;
            val = (val << 6) + d;
            valb += 6;
            if (valb >= 0) {
                out.push_back((uint8_t)((val >> valb) & 0xFF));
                valb -= 8;
            }
        }
        return !out.empty();
    }

    static bool Aes256CbcDecrypt(
        const uint8_t key[32],
        const uint8_t iv[16],
        const uint8_t* cipher,
        size_t cipherLen,
        std::string& outPlain
    ) {
        if (!cipher || cipherLen == 0 || (cipherLen % 16) != 0) return false;

        BCRYPT_ALG_HANDLE hAlg = NULL;
        BCRYPT_KEY_HANDLE hKey = NULL;
        bool ok = false;

        if (BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_AES_ALGORITHM, NULL, 0) != 0) {
            return false;
        }
        if (BCryptSetProperty(hAlg, BCRYPT_CHAINING_MODE, (PUCHAR)BCRYPT_CHAIN_MODE_CBC, sizeof(BCRYPT_CHAIN_MODE_CBC), 0) == 0) {
            DWORD keyObjSize = 0, cbData = 0;
            if (BCryptGetProperty(hAlg, BCRYPT_OBJECT_LENGTH, (PUCHAR)&keyObjSize, sizeof(DWORD), &cbData, 0) == 0 && keyObjSize > 0) {
                std::vector<uint8_t> keyObj(keyObjSize, 0);
                if (BCryptGenerateSymmetricKey(hAlg, &hKey, keyObj.data(), keyObjSize, (PUCHAR)key, 32, 0) == 0) {
                    uint8_t ivCopy[16];
                    memcpy(ivCopy, iv, 16);
                    ULONG plainLen = 0;
                    if (BCryptDecrypt(hKey, (PUCHAR)cipher, (ULONG)cipherLen, NULL, ivCopy, 16, NULL, 0, &plainLen, BCRYPT_BLOCK_PADDING) == 0 && plainLen > 0) {
                        std::vector<uint8_t> plainBuf(plainLen, 0);
                        memcpy(ivCopy, iv, 16);
                        ULONG written = 0;
                        if (BCryptDecrypt(hKey, (PUCHAR)cipher, (ULONG)cipherLen, NULL, ivCopy, 16, plainBuf.data(), plainLen, &written, BCRYPT_BLOCK_PADDING) == 0 && written > 0) {
                            outPlain.assign((const char*)plainBuf.data(), written);
                            ok = true;
                        }
                        SecureWipeVec(plainBuf);
                    }
                    SecureZeroMemory(ivCopy, sizeof(ivCopy));
                    BCryptDestroyKey(hKey);
                }
                SecureWipeVec(keyObj);
            }
        }
        BCryptCloseAlgorithmProvider(hAlg, 0);
        return ok;
    }
}

// Trích xuất giá trị String/Number an toàn từ JSON (xử lý cả chuỗi escape \/)
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
        std::string res;
        size_t i = pos + 1;
        while (i < json.length()) {
            if (json[i] == '\\' && i + 1 < json.length()) {
                char nxt = json[i + 1];
                if (nxt == '/' || nxt == '"' || nxt == '\\') {
                    res += nxt;
                    i += 2;
                    continue;
                }
            }
            if (json[i] == '"') {
                return res;
            }
            res += json[i];
            i++;
        }
        return "";
    }

    size_t endVal = json.find_first_of(",}\r\n ", pos);
    if (endVal == std::string::npos) endVal = json.length();
    return json.substr(pos, endVal - pos);
}

// Xóa các trường nhạy cảm (offsets_blob, offsets_sig, offsets_nonce, offsets_ts) khỏi JSON trước khi trả về Python
static std::string StripFieldFromJson(const std::string& json, const std::string& field) {
    std::string keyPattern = "\"" + field + "\"";
    size_t pos = json.find(keyPattern);
    if (pos == std::string::npos) return json;

    size_t colon = json.find(':', pos + keyPattern.length());
    if (colon == std::string::npos) return json;

    size_t valStart = colon + 1;
    while (valStart < json.length() && (json[valStart] == ' ' || json[valStart] == '\t' || json[valStart] == '\r' || json[valStart] == '\n')) {
        valStart++;
    }
    if (valStart >= json.length()) return json;

    size_t valEnd = valStart;
    if (json[valStart] == '"') {
        valEnd++;
        while (valEnd < json.length()) {
            if (json[valEnd] == '\\' && valEnd + 1 < json.length()) {
                valEnd += 2;
                continue;
            }
            if (json[valEnd] == '"') {
                valEnd++;
                break;
            }
            valEnd++;
        }
    } else {
        valEnd = json.find_first_of(",}\r\n", valStart);
        if (valEnd == std::string::npos) valEnd = json.length();
    }

    // Xóa luôn dấu phẩy trước hoặc sau field
    size_t eraseStart = pos;
    size_t eraseEnd = valEnd;
    size_t prevNonSpace = pos;
    while (prevNonSpace > 0 && (json[prevNonSpace - 1] == ' ' || json[prevNonSpace - 1] == '\t' || json[prevNonSpace - 1] == '\r' || json[prevNonSpace - 1] == '\n')) {
        prevNonSpace--;
    }
    size_t nextNonSpace = valEnd;
    while (nextNonSpace < json.length() && (json[nextNonSpace] == ' ' || json[nextNonSpace] == '\t' || json[nextNonSpace] == '\r' || json[nextNonSpace] == '\n')) {
        nextNonSpace++;
    }

    if (prevNonSpace > 0 && json[prevNonSpace - 1] == ',') {
        eraseStart = prevNonSpace - 1;
    } else if (nextNonSpace < json.length() && json[nextNonSpace] == ',') {
        eraseEnd = nextNonSpace + 1;
    }

    return json.substr(0, eraseStart) + json.substr(eraseEnd);
}

static std::string StripOffsetsFieldsFromJson(std::string json) {
    json = StripFieldFromJson(json, "offsets_blob");
    json = StripFieldFromJson(json, "offsets_sig");
    json = StripFieldFromJson(json, "offsets_nonce");
    json = StripFieldFromJson(json, "offsets_ts");
    return json;
}

static std::string ToUpperStr(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), ::toupper);
    return s;
}

// Giải mã offsets_blob từ Server và nạp thẳng vào RAM ẩn (trả true nếu giải mã & xác thực thành công)
static bool VerifyAndStoreEncryptedOffsets(
    const std::string& response,
    const std::string& licenseKey,
    const std::string& hwid,
    const std::string& sentNonce,
    const std::string& secretSalt
) {
    std::string blob = ExtractJsonField(response, "offsets_blob");
    std::string sig = ExtractJsonField(response, "offsets_sig");
    std::string respNonce = ExtractJsonField(response, "offsets_nonce");
    std::string respTs = ExtractJsonField(response, "offsets_ts");

    if (blob.empty() || sig.empty() || respNonce.empty() || respTs.empty()) {
        return false;
    }
    if (respNonce != sentNonce) {
        return false;
    }

    std::string upperKey = ToUpperStr(licenseKey);
    std::string upperHwid = ToUpperStr(hwid);

    // 1. Xác thực chữ ký toàn gói offsets_sig
    std::string sigPayload = upperKey + "|" + upperHwid + "|active|" + respTs + "|" + respNonce + "|" + blob;
    std::string expectedOffsetsSig = NativeCrypto::ComputeHmacSha256(sigPayload, secretSalt);
    if (_stricmp(sig.c_str(), expectedOffsetsSig.c_str()) != 0) {
        return false;
    }

    // 2. Base64 decode -> [16-byte IV][Ciphertext][32-byte HMAC-SHA256 Tag]
    std::vector<uint8_t> raw;
    if (!NativeCrypto::Base64Decode(blob, raw) || raw.size() < 64) {
        return false;
    }
    size_t cipherLen = raw.size() - 16 - 32;
    if (cipherLen == 0 || (cipherLen % 16) != 0) {
        SecureWipeVec(raw);
        return false;
    }

    const uint8_t* iv = raw.data();
    const uint8_t* cipher = raw.data() + 16;
    const uint8_t* tag = raw.data() + 16 + cipherLen;

    // 3. Dẫn xuất khóa phiên 1 lần: encKey & macKey
    std::string baseMaterial = secretSalt + "|" + upperKey + "|" + upperHwid + "|" + respNonce + "|" + respTs;
    std::string encMat = "ENC|" + baseMaterial;
    std::string macMat = "MAC|" + baseMaterial;
    std::vector<uint8_t> encKey = NativeCrypto::RawSha256((const uint8_t*)encMat.data(), encMat.size());
    std::vector<uint8_t> macKey = NativeCrypto::RawSha256((const uint8_t*)macMat.data(), macMat.size());
    SecureWipeString(baseMaterial);
    SecureWipeString(encMat);
    SecureWipeString(macMat);

    // 4. Kiểm tra Encrypt-then-MAC Tag (Constant-time)
    std::vector<uint8_t> calcTag = NativeCrypto::RawHmacSha256(raw.data(), 16 + cipherLen, macKey.data(), macKey.size());
    bool macOk = NativeCrypto::ConstantTimeEquals(calcTag.data(), tag, 32);
    SecureWipeVec(macKey);
    SecureWipeVec(calcTag);
    if (!macOk) {
        SecureWipeVec(encKey);
        SecureWipeVec(raw);
        return false;
    }

    // 5. Giải mã AES-256-CBC trong bộ nhớ C++
    std::string plainJson;
    bool decOk = NativeCrypto::Aes256CbcDecrypt(encKey.data(), iv, cipher, cipherLen, plainJson);
    SecureWipeVec(encKey);
    SecureWipeVec(raw);
    if (!decOk || plainJson.empty() || plainJson[0] != '{') {
        SecureWipeString(plainJson);
        return false;
    }

    // 6. Lưu vào kho RAM đã che phủ XOR theo khóa tiến trình
    {
        std::lock_guard<std::mutex> lock(g_vaultMutex);
        StoreRamOffsetsLocked(plainJson);
    }
    SecureWipeString(plainJson);
    return true;
}

// ==============================================================================
// 4. THU THẬP HWID VÀ WINHTTP NATIVE (XÁC THỰC CHỨNG CHỈ HTTPS THẬT)
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

static bool HttpPostJson(const std::string& fullUrl, const std::string& jsonPayload, std::string& outResponse, int timeoutMs = 10000) {
    ParsedUrl parsed;
    if (!ParseHttpUrl(fullUrl, parsed)) {
        outResponse = "{\"success\":false,\"message\":\"C++ Bridge: Invalid Server URL\"}";
        return false;
    }

    HINTERNET hSession = WinHttpOpen(
        L"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        0
    );
    if (!hSession) {
        outResponse = "{\"success\":false,\"message\":\"C++ Bridge: WinHttpOpen failed\"}";
        return false;
    }

    DWORD secProtocols = WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_2 | 0x00002000;
    WinHttpSetOption(hSession, WINHTTP_OPTION_SECURE_PROTOCOLS, &secProtocols, sizeof(secProtocols));
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

    // Chỉ bỏ kiểm tra chứng chỉ tự ký nếu là localhost dev; máy chủ từ xa BẮT BUỘC chứng chỉ TLS hợp lệ (chống MITM Fiddler)
    if (parsed.isHttps && (parsed.host == L"127.0.0.1" || parsed.host == L"localhost")) {
        DWORD dwSecurityFlags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
                                SECURITY_FLAG_IGNORE_CERT_CN_INVALID |
                                SECURITY_FLAG_IGNORE_CERT_DATE_INVALID;
        WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &dwSecurityFlags, sizeof(dwSecurityFlags));
    }

    LPCWSTR headers = L"Content-Type: application/json\r\nAccept: application/json, text/plain, */*\r\nAccept-Language: vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7\r\n";
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

// ==============================================================================
// 5. EXPORTED C API
// ==============================================================================

BRIDGE_API int Bridge_GetVersion() {
    return 300; // v3.0.0 — Zero-Offset-On-Disk + RAM-Only AES-256-CBC Vault
}

BRIDGE_API void Bridge_SetApiUrl(const char* url) {
    if (url && url[0]) {
        g_customServerUrl = url;
    }
}

BRIDGE_API int Bridge_GetHwid(char* outBuffer, int maxLen) {
    if (!outBuffer || maxLen <= 0) return 0;
    std::string guid = GetRawMachineGuid();
    std::string hash = NativeCrypto::HexSha256Upper(guid);
    std::string hwid16 = hash.substr(0, 16);
    strncpy_s(outBuffer, maxLen, hwid16.c_str(), _TRUNCATE);
    return 1;
}

BRIDGE_API int Bridge_IsAuthenticated() {
    if (CheckDebuggerPresent()) {
        std::lock_guard<std::mutex> lock(g_vaultMutex);
        g_isLicenseAuthenticated = false;
        ClearRamOffsetsLocked();
        return 0;
    }
    return g_isLicenseAuthenticated ? 1 : 0;
}

BRIDGE_API int Bridge_HasGameOffsets() {
    if (CheckDebuggerPresent() || !g_isLicenseAuthenticated) {
        return 0;
    }
    std::lock_guard<std::mutex> lock(g_vaultMutex);
    return g_ramMaskedOffsets.empty() ? 0 : 1;
}

BRIDGE_API void Bridge_ClearOffsets() {
    std::lock_guard<std::mutex> lock(g_vaultMutex);
    g_isLicenseAuthenticated = false;
    ClearRamOffsetsLocked();
}

BRIDGE_API int Bridge_ActivateLicense(
    const char* serverUrl,
    const char* licenseKey,
    const char* productCode,
    const char* clientVersion,
    char* outJson,
    int maxLen
) {
    if (!licenseKey || !outJson || maxLen <= 0) return 0;

    if (CheckDebuggerPresent()) {
        Bridge_ClearOffsets();
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
    std::string cVer = (clientVersion && clientVersion[0]) ? clientVersion : "v3.0.0";
    std::string nonce = NativeCrypto::GenerateRandomHexNonce(16);

    std::ostringstream jsonStream;
    jsonStream << "{"
               << "\"license_key\":\"" << JsonEscape(licenseKey) << "\","
               << "\"hwid\":\"" << JsonEscape(hwidBuf) << "\","
               << "\"machine_name\":\"" << JsonEscape(compName) << "\","
               << "\"client_version\":\"" << JsonEscape(cVer) << "\","
               << "\"product_code\":\"" << JsonEscape(pCode) << "\","
               << "\"nonce\":\"" << nonce << "\""
               << "}";

    std::string response;
    bool success = HttpPostJson(fullUrl, jsonStream.str(), response, 10000);

    if (success) {
        std::string isSuccess = ExtractJsonField(response, "success");
        if (isSuccess == "true") {
            std::string serverSig = ExtractJsonField(response, "signature");
            std::string secretSalt = GetDecryptedSecretSalt();
            std::string expectedPayload = ToUpperStr(licenseKey) + "|" + ToUpperStr(hwidBuf) + "|active";
            std::string expectedSig = NativeCrypto::ComputeHmacSha256(expectedPayload, secretSalt);

            if (!serverSig.empty() && _stricmp(serverSig.c_str(), expectedSig.c_str()) == 0) {
                g_isLicenseAuthenticated = true;
                VerifyAndStoreEncryptedOffsets(response, licenseKey, hwidBuf, nonce, secretSalt);
                // Xóa bỏ toàn bộ offsets_blob trước khi trả JSON cho Python (không bao giờ lưu ra license.json)
                response = StripOffsetsFieldsFromJson(response);
            } else {
                Bridge_ClearOffsets();
                response = "{\"success\":false,\"message\":\"Chữ ký bảo mật không khớp! Phát hiện giả mạo máy chủ.\"}";
            }
            SecureWipeString(secretSalt);
        } else {
            Bridge_ClearOffsets();
        }
    } else {
        Bridge_ClearOffsets();
        response = "{\"success\":false,\"message\":\"Không thể kết nối đến máy chủ bản quyền! Vui lòng kiểm tra mạng.\"}";
    }

    strncpy_s(outJson, maxLen, response.c_str(), _TRUNCATE);
    return g_isLicenseAuthenticated ? 1 : 0;
}

BRIDGE_API int Bridge_VerifyLicense(
    const char* serverUrl,
    const char* licenseKey,
    const char* clientVersion,
    char* outJson,
    int maxLen
) {
    if (!licenseKey || !outJson || maxLen <= 0) return 0;

    if (CheckDebuggerPresent()) {
        Bridge_ClearOffsets();
        strncpy_s(outJson, maxLen, "{\"valid\":false,\"status\":\"debugger_detected\",\"message\":\"Debugger detected!\"}", _TRUNCATE);
        return 0;
    }

    char hwidBuf[64] = { 0 };
    Bridge_GetHwid(hwidBuf, sizeof(hwidBuf));

    std::string srv = (serverUrl && serverUrl[0]) ? serverUrl : GetDecryptedDefaultUrl();
    while (!srv.empty() && srv.back() == '/') srv.pop_back();
    std::string fullUrl = srv + "/api/v1/license/verify";

    std::string cVer = (clientVersion && clientVersion[0]) ? clientVersion : "v3.0.0";
    std::string nonce = NativeCrypto::GenerateRandomHexNonce(16);

    std::ostringstream jsonStream;
    jsonStream << "{"
               << "\"license_key\":\"" << JsonEscape(licenseKey) << "\","
               << "\"hwid\":\"" << JsonEscape(hwidBuf) << "\","
               << "\"client_version\":\"" << JsonEscape(cVer) << "\","
               << "\"nonce\":\"" << nonce << "\""
               << "}";

    std::string response;
    bool success = HttpPostJson(fullUrl, jsonStream.str(), response, 8000);

    if (success) {
        std::string isValid = ExtractJsonField(response, "valid");
        std::string status = ExtractJsonField(response, "status");
        std::string serverSig = ExtractJsonField(response, "signature");

        if (isValid == "true" && status == "active") {
            std::string secretSalt = GetDecryptedSecretSalt();
            std::string expectedPayload = ToUpperStr(licenseKey) + "|" + ToUpperStr(hwidBuf) + "|active";
            std::string expectedSig = NativeCrypto::ComputeHmacSha256(expectedPayload, secretSalt);

            if (!serverSig.empty() && _stricmp(serverSig.c_str(), expectedSig.c_str()) == 0) {
                g_isLicenseAuthenticated = true;
                VerifyAndStoreEncryptedOffsets(response, licenseKey, hwidBuf, nonce, secretSalt);
                response = StripOffsetsFieldsFromJson(response);
            } else {
                Bridge_ClearOffsets();
                response = "{\"valid\":false,\"status\":\"tampered\",\"message\":\"Chữ ký bảo mật không khớp! Phát hiện giả mạo máy chủ.\"}";
            }
            SecureWipeString(secretSalt);
        } else {
            Bridge_ClearOffsets();
        }
    } else {
        Bridge_ClearOffsets();
    }

    strncpy_s(outJson, maxLen, response.c_str(), _TRUNCATE);
    return g_isLicenseAuthenticated ? 1 : 0;
}

// Xác thực chữ ký số Offline (CHỈ xác nhận metadata license; KHÔNG cấp offset vì Strict Online Zero-Offset-On-Disk)
BRIDGE_API int Bridge_VerifyOfflineSignature(const char* licenseKey, const char* signature) {
    if (!licenseKey || !signature || !licenseKey[0] || !signature[0]) return 0;
    if (CheckDebuggerPresent()) {
        Bridge_ClearOffsets();
        return 0;
    }
    char hwidBuf[64] = { 0 };
    Bridge_GetHwid(hwidBuf, sizeof(hwidBuf));
    std::string secretSalt = GetDecryptedSecretSalt();
    std::string expectedPayload = ToUpperStr(licenseKey) + "|" + ToUpperStr(hwidBuf) + "|active";
    std::string expectedSig = NativeCrypto::ComputeHmacSha256(expectedPayload, secretSalt);
    SecureWipeString(secretSalt);

    if (!expectedSig.empty() && _stricmp(signature, expectedSig.c_str()) == 0) {
        g_isLicenseAuthenticated = true;
        return 1;
    }
    return 0;
}

// Đọc Game Offsets từ RAM ẩn — CHỈ TRẢ VỀ KHI ĐÃ NHẬN & GIẢI MÃ TỪ SERVER ONLINE TRONG PHIÊN HIỆN TẠI
BRIDGE_API int Bridge_GetGameOffsets(char* outJson, int maxLen) {
    if (!outJson || maxLen <= 0) return 0;

    if (CheckDebuggerPresent() || !g_isLicenseAuthenticated) {
        strncpy_s(outJson, maxLen, "{}", _TRUNCATE);
        return 0;
    }

    std::string offsets;
    {
        std::lock_guard<std::mutex> lock(g_vaultMutex);
        offsets = LoadRamOffsetsLocked();
    }

    if (offsets.empty() || (int)offsets.size() >= maxLen) {
        SecureWipeString(offsets);
        strncpy_s(outJson, maxLen, "{}", _TRUNCATE);
        return 0;
    }

    strncpy_s(outJson, maxLen, offsets.c_str(), _TRUNCATE);
    SecureWipeString(offsets);
    return 1;
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    if (fdwReason == DLL_PROCESS_DETACH) {
        Bridge_ClearOffsets();
        SecureZeroMemory(g_ramMaskKey, sizeof(g_ramMaskKey));
    }
    return TRUE;
}
