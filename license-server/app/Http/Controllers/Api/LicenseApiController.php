<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\License;
use App\Models\LicenseLog;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class LicenseApiController extends Controller
{
    /**
     * Kích hoạt bản quyền lần đầu hoặc kích hoạt lại trên máy đã đăng ký.
     */
    public function activate(Request $request): JsonResponse
    {
        $request->validate([
            'license_key' => 'required|string',
            'hwid' => 'required|string',
            'machine_name' => 'nullable|string|max:100',
            'client_version' => 'nullable|string|max:50',
            'product_code' => 'nullable|string|max:50',
            'nonce' => 'nullable|string|max:128',
        ]);

        $key = trim($request->input('license_key'));
        $hwid = trim($request->input('hwid'));
        $machineName = $request->input('machine_name');
        $version = $request->input('client_version');
        $ip = $request->ip();

        $license = License::with('product')->where('license_key', $key)->first();

        if (!$license) {
            $this->logAction(null, 'activate', $hwid, $ip, $version, 'failed', 'Key bản quyền không tồn tại: ' . $key);
            return response()->json([
                'success' => false,
                'message' => 'Key bản quyền không tồn tại trong hệ thống. Vui lòng kiểm tra lại.',
            ], 404);
        }

        // Kiểm tra sản phẩm tương ứng nếu có truyền product_code
        $productCode = $request->input('product_code');
        if ($productCode && $license->product) {
            $megamuCodes = ['megamu-navigator', 'megamu-direct'];
            $isSameSuite = in_array($productCode, $megamuCodes) && in_array($license->product->code, $megamuCodes);
            if (!$isSameSuite && $license->product->code !== $productCode) {
                $this->logAction($license, 'activate', $hwid, $ip, $version, 'failed', 'Key không thuộc sản phẩm: ' . $productCode);
                return response()->json([
                    'success' => false,
                    'message' => "Key bản quyền này dành cho {$license->product->name}, không thể dùng cho sản phẩm hiện tại.",
                ], 400);
            }
        }

        // Kiểm tra trạng thái khóa / thu hồi
        if ($license->status === 'revoked') {
            $this->logAction($license, 'activate', $hwid, $ip, $version, 'failed', 'Key đã bị thu hồi / hủy bỏ.');
            return response()->json([
                'success' => false,
                'message' => 'Key bản quyền này đã bị THU HỒI bởi quản trị viên.',
            ], 403);
        }

        if ($license->status === 'suspended') {
            $this->logAction($license, 'activate', $hwid, $ip, $version, 'failed', 'Key đang bị tạm dừng.');
            return response()->json([
                'success' => false,
                'message' => 'Key bản quyền đang bị TẠM KHÓA. Hãy liên hệ bộ phận hỗ trợ.',
            ], 403);
        }

        // Kiểm tra hết hạn
        if ($license->isExpired()) {
            $this->logAction($license, 'activate', $hwid, $ip, $version, 'failed', 'Key đã hết hạn.');
            return response()->json([
                'success' => false,
                'message' => 'Key bản quyền đã HẾT HẠN vào ngày ' . $license->expires_at->format('d/m/Y H:i') . '.',
            ], 403);
        }

        // Kiểm tra HWID (Hardware ID)
        if (empty($license->hwid)) {
            // Lần đầu kích hoạt -> Gán HWID này vào License
            $license->hwid = $hwid;
            $license->machine_name = $machineName;
            $license->activated_at = now();
            $license->save();

            $this->logAction($license, 'activate', $hwid, $ip, $version, 'success', 'Kích hoạt lần đầu thành công trên máy ' . ($machineName ?: $hwid));
        } else {
            // Đã có HWID trước đó -> So khớp HWID
            if (strtoupper($license->hwid) !== strtoupper($hwid)) {
                $this->logAction($license, 'activate', $hwid, $ip, $version, 'failed', 'HWID không khớp (Máy cũ: ' . $license->hwid . ', Máy mới: ' . $hwid . ')');
                return response()->json([
                    'success' => false,
                    'message' => 'Key này đã được kích hoạt trên thiết bị khác! Mỗi key chỉ dùng cho 1 thiết bị. Liên hệ Admin để reset HWID nếu bạn đổi máy tính.',
                    'current_hwid_registered' => substr($license->hwid, 0, 8) . '...',
                ], 403);
            }

            // Cập nhật lại tên máy / thời gian nếu có
            if ($machineName && $license->machine_name !== $machineName) {
                $license->machine_name = $machineName;
                $license->save();
            }

            $this->logAction($license, 'activate', $hwid, $ip, $version, 'success', 'Kích hoạt lại thành công trên máy ' . ($machineName ?: $hwid));
        }

        $daysLeft = $license->expires_at ? max(0, now()->diffInDays($license->expires_at, false)) : null;
        $signature = $this->generateSignature($license->license_key, $hwid, 'active');
        $nonce = trim((string) $request->input('nonce', ''));
        $offsetsPkg = $this->buildEncryptedOffsetsPayload($license, $hwid, $nonce);

        return response()->json(array_merge([
            'success' => true,
            'message' => 'Kích hoạt bản quyền thành công!',
            'signature' => $signature,
            'data' => [
                'license_key' => $license->license_key,
                'product_name' => $license->product ? $license->product->name : 'MEGAMU Auto Train',
                'customer_name' => $license->customer_name ?: 'Khách hàng',
                'plan_type' => $license->plan_type,
                'max_slots' => $license->max_slots,
                'hwid' => $license->hwid,
                'activated_at' => $license->activated_at ? $license->activated_at->toDateTimeString() : null,
                'expires_at' => $license->expires_at ? $license->expires_at->toDateTimeString() : null,
                'is_lifetime' => $license->expires_at === null,
                'days_left' => $daysLeft,
                'modules' => $license->modules,
                'signature' => $signature,
            ]
        ], $offsetsPkg));
    }

    /**
     * Xác thực định kỳ (Heartbeat / Verify) từ Client.
     */
    public function verify(Request $request): JsonResponse
    {
        $request->validate([
            'license_key' => 'required|string',
            'hwid' => 'required|string',
            'client_version' => 'nullable|string',
            'nonce' => 'nullable|string|max:128',
        ]);

        $key = trim($request->input('license_key'));
        $hwid = trim($request->input('hwid'));
        $version = $request->input('client_version');
        $ip = $request->ip();

        $license = License::with('product')->where('license_key', $key)->first();

        if (!$license) {
            return response()->json([
                'valid' => false,
                'status' => 'not_found',
                'message' => 'Key bản quyền không tồn tại.',
            ], 404);
        }

        if ($license->status !== 'active') {
            $this->logAction($license, 'verify', $hwid, $ip, $version, 'failed', 'Key trạng thái: ' . $license->status);
            return response()->json([
                'valid' => false,
                'status' => $license->status,
                'message' => 'Bản quyền không khả dụng (Trạng thái: ' . $license->status . ').',
            ], 403);
        }

        if ($license->isExpired()) {
            $this->logAction($license, 'verify', $hwid, $ip, $version, 'failed', 'Key đã hết hạn.');
            return response()->json([
                'valid' => false,
                'status' => 'expired',
                'message' => 'Bản quyền đã hết hạn.',
            ], 403);
        }

        if (empty($license->hwid) || strtoupper($license->hwid) !== strtoupper($hwid)) {
            $this->logAction($license, 'verify', $hwid, $ip, $version, 'failed', 'HWID không trùng khớp.');
            return response()->json([
                'valid' => false,
                'status' => 'hwid_mismatch',
                'message' => 'Thiết bị không trùng khớp với thông tin đã đăng ký.',
            ], 403);
        }

        // Ghi log heartbeat nhẹ nhàng
        $this->logAction($license, 'verify', $hwid, $ip, $version, 'success', 'Xác thực định kỳ OK');

        $daysLeft = $license->expires_at ? max(0, now()->diffInDays($license->expires_at, false)) : null;
        $nonce = trim((string) $request->input('nonce', ''));
        $offsetsPkg = $this->buildEncryptedOffsetsPayload($license, $hwid, $nonce);

        return response()->json(array_merge([
            'valid' => true,
            'status' => 'active',
            'plan_type' => $license->plan_type,
            'max_slots' => $license->max_slots,
            'expires_at' => $license->expires_at ? $license->expires_at->toDateTimeString() : null,
            'is_lifetime' => $license->expires_at === null,
            'days_left' => $daysLeft,
            'modules' => $license->modules,
            'signature' => $this->generateSignature($license->license_key, $hwid, 'active'),
        ], $offsetsPkg));
    }

    /**
     * Đọc file game_offsets.json nội bộ trên Server (KHÔNG công khai trong public/),
     * lọc theo module bản quyền của key và mã hóa AES-256-CBC + HMAC-SHA256 theo khóa phiên dùng 1 lần.
     * Client giải mã trực tiếp trong RAM của meg_license_bridge.dll (không lưu ra đĩa).
     */
    private function buildEncryptedOffsetsPayload(License $license, string $hwid, string $nonce): array
    {
        if ($nonce === '') {
            return [];
        }

        $offsetsPath = storage_path('app/private/game_offsets.json');
        if (!is_file($offsetsPath)) {
            $altPath = storage_path('app/game_offsets.json');
            if (is_file($altPath)) {
                $offsetsPath = $altPath;
            } else {
                return [];
            }
        }

        $raw = @file_get_contents($offsetsPath);
        if (!$raw) {
            return [];
        }
        $allOffsets = json_decode($raw, true);
        if (!is_array($allOffsets) || empty($allOffsets)) {
            return [];
        }

        $filtered = $this->filterOffsetsByModules($allOffsets, $license->modules);
        $plainJson = json_encode($filtered, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
        if ($plainJson === false) {
            return [];
        }

        $secret = $this->getNativeSecret();
        $ts = (string) time();
        $upperKey = strtoupper(trim($license->license_key));
        $upperHwid = strtoupper(trim($hwid));
        $baseMaterial = $secret . '|' . $upperKey . '|' . $upperHwid . '|' . $nonce . '|' . $ts;

        $encKey = hash('sha256', 'ENC|' . $baseMaterial, true);
        $macKey = hash('sha256', 'MAC|' . $baseMaterial, true);
        $iv = random_bytes(16);

        $cipher = openssl_encrypt($plainJson, 'AES-256-CBC', $encKey, OPENSSL_RAW_DATA, $iv);
        if ($cipher === false) {
            return [];
        }

        $tag = hash_hmac('sha256', $iv . $cipher, $macKey, true);
        $blob = base64_encode($iv . $cipher . $tag);
        $sigPayload = $upperKey . '|' . $upperHwid . '|active|' . $ts . '|' . $nonce . '|' . $blob;
        $offsetsSig = hash_hmac('sha256', $sigPayload, $secret);

        return [
            'offsets_ts' => $ts,
            'offsets_nonce' => $nonce,
            'offsets_blob' => $blob,
            'offsets_sig' => $offsetsSig,
        ];
    }

    /**
     * Chỉ cấp các nhóm offset tương ứng với module đã kích hoạt (train / mirror / moss).
     */
    private function filterOffsetsByModules(array $allOffsets, $modules): array
    {
        if (!is_array($modules) || empty($modules)) {
            return $allOffsets;
        }
        $mods = array_map('strtolower', $modules);
        $hasTrain = in_array('train', $mods, true);
        $hasMirror = in_array('mirror', $mods, true);
        $hasMoss = in_array('moss', $mods, true);

        if ($hasTrain && $hasMirror && $hasMoss) {
            return $allOffsets;
        }

        $out = [];
        foreach ($allOffsets as $k => $v) {
            $lk = strtolower((string) $k);
            $isMossKey = str_starts_with($lk, 'moss_') || $lk === 'ui_moss_window';
            $isMirrorKey = str_starts_with($lk, 'mirror_')
                || str_starts_with($lk, 'doublegoer_')
                || str_starts_with($lk, 'gremory_')
                || str_starts_with($lk, 'pkt_enc_')
                || in_array($lk, ['item_mirror_ticket', 'ui_gremory_window', 'socket_send_err', 'tcp_set_nodelay'], true);
            $isDevilKey = str_starts_with($lk, 'devil_') || str_starts_with($lk, 'item_devil_');

            if ($isMossKey && !$hasMoss) {
                continue;
            }
            if ($isMirrorKey && !$hasMirror) {
                continue;
            }
            if ($isDevilKey && !$hasTrain) {
                continue;
            }
            $out[$k] = $v;
        }
        return $out;
    }

    private function getNativeSecret(): string
    {
        return (string) env('LICENSE_NATIVE_SECRET', 'MEGAMU_DONPV_2026_NATIVE_SECURE_TOKEN_#89a1');
    }

    /**
     * Tạo chữ ký số HMAC-SHA256 để chống giả mạo phản hồi từ Client.
     */
    private function generateSignature(string $licenseKey, string $hwid, string $status): string
    {
        $secret = $this->getNativeSecret();
        $payload = strtoupper($licenseKey) . '|' . strtoupper($hwid) . '|' . strtolower($status);
        return hash_hmac('sha256', $payload, $secret);
    }

    /**
     * Tra cứu nhanh trạng thái License (công khai).
     */
    public function checkStatus(Request $request): JsonResponse
    {
        $key = trim($request->input('license_key', ''));
        if (!$key) {
            return response()->json(['success' => false, 'message' => 'Vui lòng cung cấp license_key.'], 400);
        }

        $license = License::with('product')->where('license_key', $key)->first();
        if (!$license) {
            return response()->json(['success' => false, 'message' => 'Key không tồn tại.'], 404);
        }

        return response()->json([
            'success' => true,
            'license_key' => $license->license_key,
            'product' => $license->product ? $license->product->name : 'N/A',
            'plan' => $license->plan_type,
            'max_slots' => $license->max_slots,
            'status' => $license->isExpired() ? 'expired' : $license->status,
            'has_bound_device' => !empty($license->hwid),
            'expires_at' => $license->expires_at ? $license->expires_at->format('d/m/Y') : 'Vĩnh viễn',
        ]);
    }

    private function logAction(?License $license, string $action, ?string $hwid, ?string $ip, ?string $version, string $status, ?string $message): void
    {
        try {
            LicenseLog::create([
                'license_id' => $license ? $license->id : null,
                'action' => $action,
                'hwid' => $hwid,
                'ip_address' => $ip,
                'client_version' => $version,
                'status' => $status,
                'message' => $message,
                'created_at' => now(),
            ]);
        } catch (\Exception $e) {
            // Không ngắt luồng nếu lỗi ghi log
        }
    }
}
