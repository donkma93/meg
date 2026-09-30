<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\License;
use App\Models\LicenseLog;
use App\Models\Product;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

class LicenseController extends Controller
{
    /**
     * Bảng điều khiển quản lý License & thống kê.
     */
    public function index(Request $request): View
    {
        $query = License::with('product')->orderBy('id', 'desc');

        if ($request->filled('search')) {
            $s = trim($request->search);
            $query->where(function ($q) use ($s) {
                $q->where('license_key', 'like', "%{$s}%")
                  ->orWhere('customer_name', 'like', "%{$s}%")
                  ->orWhere('customer_contact', 'like', "%{$s}%")
                  ->orWhere('hwid', 'like', "%{$s}%");
            });
        }

        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }

        if ($request->filled('product_id')) {
            $query->where('product_id', $request->product_id);
        }

        $licenses = $query->paginate(15)->withQueryString();

        // Thống kê tổng quan
        $totalLicenses = License::count();
        $activeLicenses = License::where('status', 'active')
            ->where(function ($q) {
                $q->whereNull('expires_at')->orWhere('expires_at', '>', now());
            })->count();
        $expiredLicenses = License::whereNotNull('expires_at')
            ->where('expires_at', '<=', now())->count();
        $revokedLicenses = License::whereIn('status', ['revoked', 'suspended'])->count();

        $products = Product::all();
        $recentLogs = LicenseLog::with('license')->orderBy('id', 'desc')->take(8)->get();

        return view('admin.licenses.index', compact(
            'licenses',
            'products',
            'totalLicenses',
            'activeLicenses',
            'expiredLicenses',
            'revokedLicenses',
            'recentLogs'
        ));
    }

    /**
     * Tạo mới Key bản quyền.
     */
    public function store(Request $request): RedirectResponse
    {
        $request->validate([
            'product_id' => 'required|exists:products,id',
            'customer_name' => 'nullable|string|max:100',
            'customer_contact' => 'nullable|string|max:100',
            'plan_type' => 'required|string',
            'max_slots' => 'required|integer|min:1|max:500',
            'duration_type' => 'required|string', // 7d, 30d, 90d, 1y, lifetime, custom
            'custom_days' => 'nullable|integer|min:1',
            'notes' => 'nullable|string',
        ]);

        $prefix = 'MEG';
        $product = Product::find($request->product_id);
        if ($product && str_contains($product->code, 'direct')) {
            $prefix = 'DIR';
        }

        $key = License::generateLicenseKey($prefix);

        // Tính ngày hết hạn
        $expiresAt = null;
        switch ($request->duration_type) {
            case '7d':
                $expiresAt = now()->addDays(7);
                break;
            case '30d':
                $expiresAt = now()->addDays(30);
                break;
            case '90d':
                $expiresAt = now()->addDays(90);
                break;
            case '1y':
                $expiresAt = now()->addDays(365);
                break;
            case 'custom':
                $days = (int) ($request->custom_days ?: 30);
                $expiresAt = now()->addDays($days);
                break;
            case 'lifetime':
            default:
                $expiresAt = null;
                break;
        }

        $license = License::create([
            'product_id' => $request->product_id,
            'license_key' => $key,
            'customer_name' => $request->customer_name ?: 'Khách hàng',
            'customer_contact' => $request->customer_contact,
            'plan_type' => $request->plan_type,
            'max_slots' => (int) $request->max_slots,
            'hwid' => null,
            'expires_at' => $expiresAt,
            'status' => 'active',
            'notes' => $request->notes,
        ]);

        LicenseLog::create([
            'license_id' => $license->id,
            'action' => 'create',
            'ip_address' => $request->ip(),
            'status' => 'success',
            'message' => "Tạo mới key {$key} cho {$license->customer_name} ({$request->plan_type})",
            'created_at' => now(),
        ]);

        return redirect()->route('admin.licenses.index')
            ->with('success', "Đã tạo thành công Key: {$key}");
    }

    /**
     * Reset HWID để cho phép người dùng đổi sang máy mới.
     */
    public function resetHwid(License $license, Request $request): RedirectResponse
    {
        $oldHwid = $license->hwid;
        $license->hwid = null;
        $license->machine_name = null;
        $license->save();

        LicenseLog::create([
            'license_id' => $license->id,
            'action' => 'reset_hwid',
            'ip_address' => $request->ip(),
            'status' => 'success',
            'message' => "Admin đã reset HWID (HWID cũ: {$oldHwid})",
            'created_at' => now(),
        ]);

        return back()->with('success', "Đã reset HWID cho key {$license->license_key}. Thiết bị tiếp theo đăng nhập sẽ được gán tự động.");
    }

    /**
     * Thay đổi trạng thái (Khóa / Mở khóa / Thu hồi).
     */
    public function toggleStatus(License $license, Request $request): RedirectResponse
    {
        $request->validate(['status' => 'required|in:active,suspended,revoked']);
        $newStatus = $request->status;

        $license->status = $newStatus;
        $license->save();

        LicenseLog::create([
            'license_id' => $license->id,
            'action' => 'change_status',
            'ip_address' => $request->ip(),
            'status' => 'success',
            'message' => "Admin đổi trạng thái key sang: {$newStatus}",
            'created_at' => now(),
        ]);

        return back()->with('success', "Đã chuyển trạng thái key {$license->license_key} thành: {$newStatus}");
    }

    /**
     * Gia hạn thêm ngày sử dụng.
     */
    public function extend(License $license, Request $request): RedirectResponse
    {
        $request->validate(['days' => 'required|integer|min:1']);
        $days = (int) $request->days;

        if ($license->expires_at === null) {
            return back()->with('info', "Key này là Vĩnh viễn (Lifetime), không cần gia hạn.");
        }

        // Nếu đã hết hạn thì tính từ thời điểm hiện tại, ngược lại cộng dồn
        $base = $license->expires_at->isPast() ? now() : $license->expires_at;
        $license->expires_at = $base->addDays($days);
        $license->status = 'active'; // Tự động active nếu trước đó expired
        $license->save();

        LicenseLog::create([
            'license_id' => $license->id,
            'action' => 'extend',
            'ip_address' => $request->ip(),
            'status' => 'success',
            'message' => "Admin gia hạn thêm {$days} ngày. Hạn mới: {$license->expires_at->format('d/m/Y')}",
            'created_at' => now(),
        ]);

        return back()->with('success', "Đã gia hạn thêm {$days} ngày cho key {$license->license_key}. Hạn mới: {$license->expires_at->format('d/m/Y')}");
    }

    /**
     * Xóa key bản quyền.
     */
    public function destroy(License $license): RedirectResponse
    {
        $key = $license->license_key;
        $license->delete();

        return back()->with('success', "Đã xóa vĩnh viễn Key bản quyền: {$key}");
    }

    /**
     * Xem toàn bộ nhật ký Audit Logs.
     */
    public function logs(Request $request): View
    {
        $query = LicenseLog::with('license.product')->orderBy('id', 'desc');

        if ($request->filled('action')) {
            $query->where('action', $request->action);
        }

        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }

        $logs = $query->paginate(25)->withQueryString();

        return view('admin.licenses.logs', compact('logs'));
    }
}
