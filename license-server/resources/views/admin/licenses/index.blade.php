@extends('layouts.admin')

@section('title', 'Quản lý Bản quyền')

@section('content')
<div class="space-y-6">

    <!-- Top Action Bar -->
    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
            <h1 class="text-2xl font-extrabold tracking-tight text-white">Quản lý Bản quyền Sản phẩm</h1>
            <p class="text-sm text-slate-400 mt-1">Cấp phát, quản lý key, liên kết HWID máy tính và theo dõi hạn sử dụng khách hàng.</p>
        </div>
        <button onclick="document.getElementById('createModal').classList.remove('hidden')" class="px-4 py-2.5 rounded-xl bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-dark-950 font-bold text-sm flex items-center space-x-2 shadow-lg shadow-cyan-500/20 transition-all transform hover:-translate-y-0.5">
            <svg class="w-4 h-4 font-bold" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4"></path></svg>
            <span>Tạo Key Mới</span>
        </button>
    </div>

    <!-- Stat Cards Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Card 1 -->
        <div class="p-4 rounded-2xl bg-dark-900 border border-dark-750 flex items-center justify-between">
            <div>
                <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Tổng số Key</p>
                <h3 class="text-2xl font-black text-white mt-1">{{ number_format($totalLicenses) }}</h3>
                <span class="text-[11px] text-slate-500">Đã phát hành</span>
            </div>
            <div class="w-12 h-12 rounded-xl bg-dark-800 border border-dark-700 flex items-center justify-center text-cyan-400">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
            </div>
        </div>

        <!-- Card 2 -->
        <div class="p-4 rounded-2xl bg-dark-900 border border-dark-750 flex items-center justify-between">
            <div>
                <p class="text-xs font-semibold uppercase tracking-wider text-emerald-400">Đang hoạt động</p>
                <h3 class="text-2xl font-black text-emerald-400 mt-1">{{ number_format($activeLicenses) }}</h3>
                <span class="text-[11px] text-slate-500">Còn hạn & hợp lệ</span>
            </div>
            <div class="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            </div>
        </div>

        <!-- Card 3 -->
        <div class="p-4 rounded-2xl bg-dark-900 border border-dark-750 flex items-center justify-between">
            <div>
                <p class="text-xs font-semibold uppercase tracking-wider text-amber-400">Đã hết hạn</p>
                <h3 class="text-2xl font-black text-amber-400 mt-1">{{ number_format($expiredLicenses) }}</h3>
                <span class="text-[11px] text-slate-500">Cần gia hạn</span>
            </div>
            <div class="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            </div>
        </div>

        <!-- Card 4 -->
        <div class="p-4 rounded-2xl bg-dark-900 border border-dark-750 flex items-center justify-between">
            <div>
                <p class="text-xs font-semibold uppercase tracking-wider text-rose-400">Đã khóa / Thu hồi</p>
                <h3 class="text-2xl font-black text-rose-400 mt-1">{{ number_format($revokedLicenses) }}</h3>
                <span class="text-[11px] text-slate-500">Bị chặn kích hoạt</span>
            </div>
            <div class="w-12 h-12 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path></svg>
            </div>
        </div>
    </div>

    <!-- Filters & Search Bar -->
    <div class="p-4 rounded-2xl bg-dark-900 border border-dark-750">
        <form method="GET" action="{{ route('admin.licenses.index') }}" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-3 items-center">
            <!-- Search -->
            <div class="lg:col-span-5 relative">
                <input type="text" name="search" value="{{ request('search') }}" placeholder="Tìm theo Key, Tên khách hàng, Zalo, HWID..." class="w-full pl-10 pr-4 py-2 rounded-xl bg-dark-800 border border-dark-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                </div>
            </div>

            <!-- Status Filter -->
            <div class="lg:col-span-3">
                <select name="status" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 transition-all">
                    <option value="">Tất cả trạng thái</option>
                    <option value="active" {{ request('status') === 'active' ? 'selected' : '' }}>Đang hoạt động</option>
                    <option value="suspended" {{ request('status') === 'suspended' ? 'selected' : '' }}>Tạm dừng</option>
                    <option value="revoked" {{ request('status') === 'revoked' ? 'selected' : '' }}>Bị thu hồi</option>
                </select>
            </div>

            <!-- Product Filter -->
            <div class="lg:col-span-3">
                <select name="product_id" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 transition-all">
                    <option value="">Tất cả sản phẩm</option>
                    @foreach ($products as $prod)
                        <option value="{{ $prod->id }}" {{ request('product_id') == $prod->id ? 'selected' : '' }}>{{ $prod->name }}</option>
                    @endforeach
                </select>
            </div>

            <!-- Action button -->
            <div class="lg:col-span-1 flex items-center space-x-2">
                <button type="submit" class="w-full py-2 bg-dark-750 hover:bg-dark-700 border border-dark-700 text-white rounded-xl text-sm font-semibold transition-colors flex items-center justify-center">
                    Lọc
                </button>
                @if(request()->hasAny(['search', 'status', 'product_id']))
                    <a href="{{ route('admin.licenses.index') }}" class="p-2 text-slate-400 hover:text-white" title="Xóa bộ lọc">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </a>
                @endif
            </div>
        </form>
    </div>

    <!-- License Table -->
    <div class="rounded-2xl bg-dark-900 border border-dark-750 overflow-hidden shadow-xl">
        <div class="overflow-x-auto">
            <table class="w-full text-left text-sm text-slate-300">
                <thead class="bg-dark-850/80 text-[11px] uppercase tracking-wider text-slate-400 border-b border-dark-750">
                    <tr>
                        <th class="px-4 py-3.5 font-bold">Key Bản quyền</th>
                        <th class="px-4 py-3.5 font-bold">Sản phẩm / Gói</th>
                        <th class="px-4 py-3.5 font-bold">Khách hàng</th>
                        <th class="px-4 py-3.5 font-bold">Thiết bị HWID</th>
                        <th class="px-4 py-3.5 font-bold">Thời hạn</th>
                        <th class="px-4 py-3.5 font-bold">Trạng thái</th>
                        <th class="px-4 py-3.5 font-bold text-right">Thao tác</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-dark-800">
                    @forelse ($licenses as $item)
                        <tr class="hover:bg-dark-800/40 transition-colors">
                            <!-- License Key -->
                            <td class="px-4 py-4 whitespace-nowrap">
                                <div class="flex items-center space-x-2">
                                    <span class="font-mono font-bold text-white text-[13px] bg-dark-800 px-2 py-1 rounded-lg border border-dark-700 tracking-wider">
                                        {{ $item->license_key }}
                                    </span>
                                    <button onclick="copyToClipboard('{{ $item->license_key }}')" title="Sao chép Key" class="p-1.5 rounded-lg text-slate-400 hover:text-cyan-400 hover:bg-dark-750 transition-colors">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                                    </button>
                                </div>
                            </td>

                            <!-- Product & Plan -->
                            <td class="px-4 py-4 whitespace-nowrap">
                                <div class="font-semibold text-white">{{ $item->product ? $item->product->name : 'N/A' }}</div>
                                <div class="flex items-center space-x-2 mt-0.5">
                                    <span class="px-2 py-0.5 text-[10px] font-bold rounded-md bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">{{ $item->plan_type }}</span>
                                    <span class="text-xs text-slate-400 font-mono">{{ $item->max_slots }} Slots</span>
                                </div>
                            </td>

                            <!-- Customer -->
                            <td class="px-4 py-4 whitespace-nowrap">
                                <div class="font-medium text-slate-200">{{ $item->customer_name ?: 'Chưa đặt tên' }}</div>
                                <div class="text-xs text-slate-400">{{ $item->customer_contact ?: '--' }}</div>
                            </td>

                            <!-- HWID -->
                            <td class="px-4 py-4 whitespace-nowrap">
                                @if ($item->hwid)
                                    <div class="flex items-center space-x-2">
                                        <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
                                        <span class="font-mono text-xs text-slate-300" title="{{ $item->hwid }}">
                                            {{ substr($item->hwid, 0, 10) }}...{{ substr($item->hwid, -4) }}
                                        </span>
                                        <form method="POST" action="{{ route('admin.licenses.reset-hwid', $item) }}" class="inline" onsubmit="return confirm('Bạn có chắc muốn Reset HWID cho Key này? Thiết bị tiếp theo đăng nhập sẽ được gán tự động.')">
                                            @csrf
                                            <button type="submit" class="px-1.5 py-0.5 rounded text-[10px] bg-dark-750 hover:bg-dark-700 text-slate-300 hover:text-white border border-dark-700" title="Reset HWID để đổi máy">
                                                Reset
                                            </button>
                                        </form>
                                    </div>
                                    @if ($item->machine_name)
                                        <div class="text-[11px] text-slate-500 mt-0.5">Máy: {{ $item->machine_name }}</div>
                                    @endif
                                @else
                                    <span class="inline-flex items-center px-2 py-0.5 text-[10px] font-semibold rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                                        Chưa kích hoạt
                                    </span>
                                @endif
                            </td>

                            <!-- Expiry -->
                            <td class="px-4 py-4 whitespace-nowrap">
                                @if ($item->expires_at === null)
                                    <span class="px-2 py-0.5 text-[10px] font-bold rounded-md bg-purple-500/10 text-purple-400 border border-purple-500/20">Vĩnh viễn (Lifetime)</span>
                                @else
                                    <div class="{{ $item->isExpired() ? 'text-rose-400 font-bold' : 'text-slate-200' }}">
                                        {{ $item->expires_at->format('d/m/Y H:i') }}
                                    </div>
                                    <div class="text-[11px] {{ $item->isExpired() ? 'text-rose-500' : 'text-slate-500' }}">
                                        @if ($item->isExpired())
                                            Đã hết hạn {{ $item->expires_at->diffForHumans() }}
                                        @else
                                            Còn {{ now()->diffInDays($item->expires_at) }} ngày
                                        @endif
                                    </div>
                                @endif
                            </td>

                            <!-- Status -->
                            <td class="px-4 py-4 whitespace-nowrap">
                                @if ($item->status === 'revoked')
                                    <span class="px-2 py-0.5 text-[11px] font-bold rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20">Bị thu hồi</span>
                                @elseif ($item->status === 'suspended')
                                    <span class="px-2 py-0.5 text-[11px] font-bold rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20">Tạm khóa</span>
                                @elseif ($item->isExpired())
                                    <span class="px-2 py-0.5 text-[11px] font-bold rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20">Hết hạn</span>
                                @else
                                    <span class="px-2 py-0.5 text-[11px] font-bold rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Hoạt động</span>
                                @endif
                            </td>

                            <!-- Actions -->
                            <td class="px-4 py-4 whitespace-nowrap text-right text-xs">
                                <div class="flex items-center justify-end space-x-1.5">
                                    <!-- Extend Button -->
                                    <button onclick="openExtendModal('{{ $item->id }}', '{{ $item->license_key }}')" class="p-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-cyan-400 border border-dark-700" title="Gia hạn ngày">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
                                    </button>

                                    <!-- Status Toggle Button -->
                                    @if ($item->status === 'active')
                                        <form method="POST" action="{{ route('admin.licenses.status', $item) }}" class="inline" onsubmit="return confirm('Khóa tạm thời Key này?')">
                                            @csrf
                                            <input type="hidden" name="status" value="suspended">
                                            <button type="submit" class="p-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-amber-400 border border-dark-700" title="Tạm khóa Key">
                                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                            </button>
                                        </form>
                                    @else
                                        <form method="POST" action="{{ route('admin.licenses.status', $item) }}" class="inline">
                                            @csrf
                                            <input type="hidden" name="status" value="active">
                                            <button type="submit" class="p-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-emerald-400 border border-dark-700" title="Kích hoạt lại Key">
                                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                            </button>
                                        </form>
                                    @endif

                                    <!-- Delete Button -->
                                    <form method="POST" action="{{ route('admin.licenses.destroy', $item) }}" class="inline" onsubmit="return confirm('Bạn có chắc muốn XÓA vĩnh viễn Key này?')">
                                        @csrf
                                        @method('DELETE')
                                        <button type="submit" class="p-1.5 rounded-lg bg-dark-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 border border-dark-700" title="Xóa Key">
                                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                                        </button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                    @empty
                        <tr>
                            <td colspan="7" class="px-4 py-8 text-center text-slate-500">
                                Chưa có Key bản quyền nào phù hợp với bộ lọc.
                            </td>
                        </tr>
                    @endforelse
                </tbody>
            </table>
        </div>

        @if ($licenses->hasPages())
            <div class="p-4 border-t border-dark-750 bg-dark-850">
                {{ $licenses->links() }}
            </div>
        @endif
    </div>

</div>

<!-- Modal: Tạo Key Mới -->
<div id="createModal" class="hidden fixed inset-0 z-50 overflow-y-auto bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-dark-900 border border-dark-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5">
        <div class="flex items-center justify-between border-b border-dark-750 pb-3">
            <h3 class="text-lg font-extrabold text-white">Tạo Key Bản quyền Mới</h3>
            <button onclick="document.getElementById('createModal').classList.add('hidden')" class="text-slate-400 hover:text-white text-xl font-bold">&times;</button>
        </div>

        <form method="POST" action="{{ route('admin.licenses.store') }}" class="space-y-4 text-sm">
            @csrf
            <!-- Sản phẩm -->
            <div>
                <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Sản phẩm</label>
                <select name="product_id" required class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white focus:outline-none focus:border-cyan-500">
                    @foreach ($products as $prod)
                        <option value="{{ $prod->id }}">{{ $prod->name }}</option>
                    @endforeach
                </select>
            </div>

            <!-- Tên & Liên hệ Khách hàng -->
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Tên khách hàng</label>
                    <input type="text" name="customer_name" placeholder="Nguyễn Văn A" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Zalo / SĐT / FB</label>
                    <input type="text" name="customer_contact" placeholder="0988xxxxxx" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500">
                </div>
            </div>

            <!-- Gói & Số Slot -->
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Gói dịch vụ</label>
                    <select name="plan_type" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white focus:outline-none focus:border-cyan-500">
                        <option value="Basic">Basic</option>
                        <option value="Pro" selected>Pro</option>
                        <option value="VIP Pro">VIP Pro</option>
                        <option value="Master Enterprise">Master Enterprise</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Số Slot tối đa</label>
                    <input type="number" name="max_slots" value="10" min="1" max="100" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white focus:outline-none focus:border-cyan-500">
                </div>
            </div>

            <!-- Thời hạn sử dụng -->
            <div>
                <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Thời hạn bản quyền</label>
                <select name="duration_type" id="durationTypeSelect" onchange="toggleCustomDays(this.value)" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white focus:outline-none focus:border-cyan-500">
                    <option value="7d">7 Ngày (Dùng thử)</option>
                    <option value="30d" selected>30 Ngày (1 Tháng)</option>
                    <option value="90d">90 Ngày (3 Tháng)</option>
                    <option value="1y">365 Ngày (1 Năm)</option>
                    <option value="lifetime">Vĩnh viễn (Lifetime)</option>
                    <option value="custom">Tùy chỉnh số ngày...</option>
                </select>
            </div>

            <div id="customDaysBox" class="hidden">
                <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Nhập số ngày cụ thể</label>
                <input type="number" name="custom_days" placeholder="60" min="1" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white focus:outline-none focus:border-cyan-500">
            </div>

            <!-- Ghi chú -->
            <div>
                <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Ghi chú (Tùy chọn)</label>
                <textarea name="notes" rows="2" placeholder="Ghi chú đơn hàng, mã giao dịch..." class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 text-xs"></textarea>
            </div>

            <!-- Submit buttons -->
            <div class="flex items-center justify-end space-x-3 pt-3 border-t border-dark-750">
                <button type="button" onclick="document.getElementById('createModal').classList.add('hidden')" class="px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-750 text-slate-400 hover:text-white font-semibold transition-colors">
                    Hủy
                </button>
                <button type="submit" class="px-5 py-2 rounded-xl bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-dark-950 font-bold transition-all">
                    Tạo Key & Lưu
                </button>
            </div>
        </form>
    </div>
</div>

<!-- Modal: Gia hạn ngày -->
<div id="extendModal" class="hidden fixed inset-0 z-50 overflow-y-auto bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-dark-900 border border-dark-700 rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4">
        <div class="flex items-center justify-between border-b border-dark-750 pb-2">
            <h3 class="text-base font-bold text-white">Gia hạn Bản quyền</h3>
            <button onclick="document.getElementById('extendModal').classList.add('hidden')" class="text-slate-400 hover:text-white text-lg font-bold">&times;</button>
        </div>

        <p class="text-xs text-slate-400">Key: <span id="extendKeyName" class="font-mono font-bold text-cyan-400"></span></p>

        <form id="extendForm" method="POST" action="" class="space-y-3">
            @csrf
            <div>
                <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Chọn số ngày cộng thêm</label>
                <select name="days" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white text-sm focus:outline-none focus:border-cyan-500">
                    <option value="30">+30 Ngày (1 Tháng)</option>
                    <option value="60">+60 Ngày (2 Tháng)</option>
                    <option value="90">+90 Ngày (3 Tháng)</option>
                    <option value="180">+180 Ngày (6 Tháng)</option>
                    <option value="365">+365 Ngày (1 Năm)</option>
                </select>
            </div>

            <div class="flex items-center justify-end space-x-2 pt-2">
                <button type="button" onclick="document.getElementById('extendModal').classList.add('hidden')" class="px-3 py-1.5 rounded-lg bg-dark-800 text-slate-400 text-xs font-semibold">
                    Hủy
                </button>
                <button type="submit" class="px-4 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-dark-950 font-bold text-xs">
                    Xác nhận Gia hạn
                </button>
            </div>
        </form>
    </div>
</div>
@endsection

@section('scripts')
<script>
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            alert('Đã sao chép Key: ' + text);
        }).catch(() => {
            prompt('Sao chép Key:', text);
        });
    }

    function toggleCustomDays(val) {
        const box = document.getElementById('customDaysBox');
        if (val === 'custom') {
            box.classList.remove('hidden');
        } else {
            box.classList.add('hidden');
        }
    }

    function openExtendModal(id, key) {
        document.getElementById('extendKeyName').innerText = key;
        document.getElementById('extendForm').action = '/admin/licenses/' + id + '/extend';
        document.getElementById('extendModal').classList.remove('hidden');
    }
</script>
@endsection
