<?php

namespace Database\Seeders;

use App\Models\User;
use Illuminate\Database\Console\Seeds\WithoutModelEvents;
use Illuminate\Database\Seeder;

class DatabaseSeeder extends Seeder
{
    use WithoutModelEvents;

    /**
     * Seed the application's database.
     */
    public function run(): void
    {
        $prod1 = \App\Models\Product::firstOrCreate(
            ['code' => 'megamu-navigator'],
            [
                'name' => 'MEGAMU Auto Train Dashboard',
                'description' => 'Hệ thống tự động tìm đường, di chuyển, train quái và điều khiển đa tài khoản MEGAMU.',
            ]
        );

        $prod2 = \App\Models\Product::firstOrCreate(
            ['code' => 'megamu-direct'],
            [
                'name' => 'MEGAMU Zero-Mouse Direct Engine',
                'description' => 'Gói Engine hook native không chiếm chuột và phím.',
            ]
        );

        // Tạo 1 Key bản quyền mẫu để kiểm thử ngay
        \App\Models\License::firstOrCreate(
            ['license_key' => 'MEG-DONPV-2026-VIP1'],
            [
                'product_id' => $prod1->id,
                'customer_name' => 'MEGATEAM',
                'customer_contact' => '036.203.1354',
                'plan_type' => 'VIP Pro',
                'max_slots' => 50,
                'hwid' => null, // Chưa bind HWID, sẵn sàng kích hoạt từ máy đầu tiên
                'activated_at' => null,
                'expires_at' => now()->addDays(365),
                'status' => 'active',
                'notes' => 'Key bản quyền Master khởi tạo bởi MEGATEAM (Hotline / Zalo: 036.203.1354).',
            ]
        );
        // Tạo tài khoản quản trị mặc định (admin / admin123)
        \App\Models\User::firstOrCreate(
            ['email' => 'admin@megamu.vn'],
            [
                'name' => 'admin',
                'password' => bcrypt('admin123'),
            ]
        );
    }
}
