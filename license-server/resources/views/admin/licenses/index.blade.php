@extends('layouts.admin')

@section('title', 'Quản lý Bản quyền')

@section('content')
<div class="space-y-6">

    <!-- Top Action Bar -->
    <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 py-2">
        <div class="flex items-center space-x-3.5">
            <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-teal-500/20 to-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-lg shadow-cyan-500/10">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
            </div>
            <div>
                <h1 class="text-2xl sm:text-3xl font-black tracking-tight text-white">Quản lý Bản quyền Sản phẩm</h1>
                <p class="text-sm text-slate-400 mt-0.5">Cấp phát, quản lý key, phân quyền Module (Train / Moss / Mirror) và liên kết HWID máy khách.</p>
            </div>
        </div>
        <button onclick="document.getElementById('createModal').classList.remove('hidden')" class="px-5 py-3 rounded-xl bg-gradient-to-r from-teal-400 via-cyan-400 to-blue-500 hover:from-teal-300 hover:to-blue-400 text-dark-950 font-black text-sm flex items-center space-x-2.5 shadow-xl shadow-cyan-500/25 transition-all transform hover:-translate-y-0.5 active:translate-y-0">
            <svg class="w-5 h-5 font-black" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4"></path></svg>
            <span>Tạo Key Mới</span>
        </button>
    </div>

    <!-- Stat Cards Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        <!-- Card 1: Tổng số Key -->
        <div class="p-5 sm:p-6 rounded-2xl bg-dark-900/90 border border-dark-750/90 hover:border-cyan-500/40 backdrop-blur-md shadow-xl flex items-center justify-between transition-all hover:shadow-cyan-500/5 group">
            <div>
                <p class="text-xs font-bold uppercase tracking-wider text-slate-400">Tổng số Key</p>
                <h3 class="text-3xl font-black text-white mt-1.5">{{ number_format($totalLicenses) }}</h3>
                <span class="inline-block text-xs text-slate-500 mt-1 font-medium">Đã phát hành trong hệ thống</span>
            </div>
            <div class="w-14 h-14 rounded-2xl bg-dark-800/90 border border-dark-700 flex items-center justify-center text-cyan-400 group-hover:scale-105 group-hover:border-cyan-500/40 group-hover:bg-cyan-500/10 transition-all shadow-md">
                <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
            </div>
        </div>

        <!-- Card 2: Đang hoạt động -->
        <div class="p-5 sm:p-6 rounded-2xl bg-dark-900/90 border border-dark-750/90 hover:border-emerald-500/40 backdrop-blur-md shadow-xl flex items-center justify-between transition-all hover:shadow-emerald-500/5 group">
            <div>
                <p class="text-xs font-bold uppercase tracking-wider text-emerald-400">Đang hoạt động</p>
                <h3 class="text-3xl font-black text-emerald-400 mt-1.5">{{ number_format($activeLicenses) }}</h3>
                <span class="inline-block text-xs text-slate-500 mt-1 font-medium">Còn thời hạn & hợp lệ</span>
            </div>
            <div class="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 group-hover:scale-105 group-hover:border-emerald-500/40 group-hover:bg-emerald-500/20 transition-all shadow-md">
                <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            </div>
        </div>

        <!-- Card 3: Đã hết hạn -->
        <div class="p-5 sm:p-6 rounded-2xl bg-dark-900/90 border border-dark-750/90 hover:border-amber-500/40 backdrop-blur-md shadow-xl flex items-center justify-between transition-all hover:shadow-amber-500/5 group">
            <div>
                <p class="text-xs font-bold uppercase tracking-wider text-amber-400">Đã hết hạn</p>
                <h3 class="text-3xl font-black text-amber-400 mt-1.5">{{ number_format($expiredLicenses) }}</h3>
                <span class="inline-block text-xs text-slate-500 mt-1 font-medium">Cần liên hệ gia hạn</span>
            </div>
            <div class="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 group-hover:scale-105 group-hover:border-amber-500/40 group-hover:bg-amber-500/20 transition-all shadow-md">
                <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            </div>
        </div>

        <!-- Card 4: Đã khóa / Thu hồi -->
        <div class="p-5 sm:p-6 rounded-2xl bg-dark-900/90 border border-dark-750/90 hover:border-rose-500/40 backdrop-blur-md shadow-xl flex items-center justify-between transition-all hover:shadow-rose-500/5 group">
            <div>
                <p class="text-xs font-bold uppercase tracking-wider text-rose-400">Đã khóa / Thu hồi</p>
                <h3 class="text-3xl font-black text-rose-400 mt-1.5">{{ number_format($revokedLicenses) }}</h3>
                <span class="inline-block text-xs text-slate-500 mt-1 font-medium">Chặn kích hoạt trên máy</span>
            </div>
            <div class="w-14 h-14 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 group-hover:scale-105 group-hover:border-rose-500/40 group-hover:bg-rose-500/20 transition-all shadow-md">
                <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path></svg>
            </div>
        </div>
    </div>

    <!-- Filters & Search Bar -->
    <div class="p-5 rounded-2xl bg-dark-900/90 border border-dark-750/90 backdrop-blur-md shadow-xl">
        <form method="GET" action="{{ route('admin.licenses.index') }}" class="grid grid-cols-1 sm:grid-cols-12 gap-3.5 items-center">
            <!-- Search -->
            <div class="sm:col-span-12 lg:col-span-5 relative">
                <input type="text" name="search" value="{{ request('search') }}" placeholder="Tìm nhanh theo Mã Key, Tên khách hàng, Zalo / SĐT, HWID..." class="w-full pl-11 pr-4 py-2.5 rounded-xl bg-dark-800/90 border border-dark-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all">
                <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                </div>
            </div>

            <!-- Status Filter -->
            <div class="sm:col-span-6 lg:col-span-3">
                <select name="status" class="w-full px-3.5 py-2.5 rounded-xl bg-dark-800/90 border border-dark-700 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 transition-all cursor-pointer">
                    <option value="">-- Tất cả trạng thái --</option>
                    <option value="active" {{ request('status') === 'active' ? 'selected' : '' }}>Đang hoạt động</option>
                    <option value="suspended" {{ request('status') === 'suspended' ? 'selected' : '' }}>Tạm dừng</option>
                    <option value="revoked" {{ request('status') === 'revoked' ? 'selected' : '' }}>Bị thu hồi</option>
                </select>
            </div>

            <!-- Product Filter -->
            <div class="sm:col-span-6 lg:col-span-3">
                <select name="product_id" class="w-full px-3.5 py-2.5 rounded-xl bg-dark-800/90 border border-dark-700 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 transition-all cursor-pointer">
                    <option value="">-- Tất cả sản phẩm --</option>
                    @foreach ($products as $prod)
                        <option value="{{ $prod->id }}" {{ request('product_id') == $prod->id ? 'selected' : '' }}>{{ $prod->name }}</option>
                    @endforeach
                </select>
            </div>

            <!-- Action button -->
            <div class="sm:col-span-12 lg:col-span-1 flex items-center space-x-2">
                <button type="submit" class="w-full py-2.5 bg-dark-800 hover:bg-cyan-500/10 hover:border-cyan-500/40 hover:text-cyan-400 border border-dark-700 text-white rounded-xl text-sm font-bold transition-all flex items-center justify-center shadow-sm">
                    Lọc
                </button>
                @if(request()->hasAny(['search', 'status', 'product_id']))
                    <a href="{{ route('admin.licenses.index') }}" class="p-2.5 rounded-xl bg-dark-800 border border-dark-700 text-slate-400 hover:text-rose-400 hover:border-rose-500/30 transition-colors" title="Xóa bộ lọc">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </a>
                @endif
            </div>
        </form>
    </div>

    <!-- License Table (Widescreen Spacious Layout) -->
    <div class="rounded-2xl bg-dark-900/90 border border-dark-750/90 shadow-2xl backdrop-blur-md overflow-hidden">
        <div class="overflow-x-auto">
            <table class="w-full text-left text-sm text-slate-300">
                <thead class="bg-dark-850/90 text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-dark-750/90">
                    <tr>
                        <th class="px-6 py-4.5 font-bold">Key Bản quyền</th>
                        <th class="px-6 py-4.5 font-bold">Sản phẩm / Gói</th>
                        <th class="px-6 py-4.5 font-bold">Modules Cấp phép</th>
                        <th class="px-6 py-4.5 font-bold">Khách hàng</th>
                        <th class="px-6 py-4.5 font-bold">Thiết bị HWID</th>
                        <th class="px-6 py-4.5 font-bold">Thời hạn</th>
                        <th class="px-6 py-4.5 font-bold">Trạng thái</th>
                        <th class="px-6 py-4.5 font-bold text-right">Thao tác</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-dark-800/80">
                    @forelse ($licenses as $item)
                        <tr class="hover:bg-dark-800/50 transition-colors">
                            <!-- License Key -->
                            <td class="px-6 py-5 whitespace-nowrap">
                                <div class="flex items-center space-x-2.5">
                                    <span class="font-mono font-bold text-white text-sm bg-dark-950/80 px-3 py-1.5 rounded-xl border border-dark-700/80 tracking-wider shadow-inner select-all">
                                        {{ $item->license_key }}
                                    </span>
                                    <button onclick="copyToClipboard('{{ $item->license_key }}')" title="Sao chép Key" class="p-2 rounded-xl text-slate-400 hover:text-cyan-400 hover:bg-dark-800 border border-transparent hover:border-cyan-500/30 transition-all">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                                    </button>
                                </div>
                            </td>

                            <!-- Product & Plan -->
                            <td class="px-6 py-5 whitespace-nowrap">
                                <div class="font-bold text-white text-sm">{{ $item->product ? $item->product->name : 'MEGAMU Auto Train' }}</div>
                                <div class="flex items-center space-x-2 mt-1">
                                    <span class="px-2.5 py-0.5 text-xs font-bold rounded-lg bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">{{ $item->plan_type }}</span>
                                    <span class="px-2 py-0.5 text-xs text-slate-300 font-mono font-medium rounded-lg bg-dark-800 border border-dark-700">{{ $item->max_slots }} Slots</span>
                                </div>
                            </td>

                            <!-- Modules (Spacious Pills) -->
                            <td class="px-6 py-5 whitespace-nowrap">
                                <div class="inline-flex items-center gap-2 flex-wrap">
                                    @php
                                        $mods = $item->modules ?? ['train', 'moss', 'mirror'];
                                    @endphp
                                    @if(in_array('train', $mods))
                                        <span class="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-xl bg-blue-500/15 text-blue-300 border border-blue-500/30 shadow-sm" title="Train Auto / MuHelper">
                                            <span>⚔️</span> <span>Train</span>
                                        </span>
                                    @endif
                                    @if(in_array('moss', $mods))
                                        <span class="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-xl bg-amber-500/15 text-amber-300 border border-amber-500/30 shadow-sm" title="Moss Merchant Auto">
                                            <span>🎰</span> <span>Moss</span>
                                        </span>
                                    @endif
                                    @if(in_array('mirror', $mods))
                                        <span class="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-xl bg-purple-500/15 text-purple-300 border border-purple-500/30 shadow-sm" title="Double Goer / Mirror of Dimensions">
                                            <span>🪞</span> <span>Mirror</span>
                                        </span>
                                    @endif
                                    @if(empty($mods))
                                        <span class="px-2.5 py-1 text-xs font-medium rounded-xl bg-slate-800 text-slate-500 border border-slate-700">Chưa cấp</span>
                                    @endif
                                </div>
                            </td>

                            <!-- Customer -->
                            <td class="px-6 py-5 whitespace-nowrap">
                                <div class="font-bold text-slate-100 text-sm">{{ $item->customer_name ?: 'Chưa đặt tên' }}</div>
                                <div class="text-xs text-slate-400 mt-0.5 flex items-center space-x-1">
                                    <span>📞</span>
                                    <span>{{ $item->customer_contact ?: '--' }}</span>
                                </div>
                            </td>

                            <!-- HWID -->
                            <td class="px-6 py-5 whitespace-nowrap">
                                @if ($item->hwid)
                                    <div class="flex items-center space-x-2.5">
                                        <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-500/50"></span>
                                        <span class="font-mono text-xs text-slate-200 bg-dark-950/70 px-2.5 py-1 rounded-lg border border-dark-700/80" title="{{ $item->hwid }}">
                                            {{ substr($item->hwid, 0, 10) }}...{{ substr($item->hwid, -4) }}
                                        </span>
                                        <form method="POST" action="{{ route('admin.licenses.reset-hwid', $item) }}" class="inline" onsubmit="return confirm('Bạn có chắc muốn Reset HWID cho Key này? Thiết bị tiếp theo đăng nhập sẽ được gán tự động.')">
                                            @csrf
                                            <button type="submit" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-rose-500/20 text-slate-300 hover:text-rose-300 border border-dark-700 hover:border-rose-500/30 transition-colors" title="Reset HWID để đổi máy tính mới">
                                                Reset
                                            </button>
                                        </form>
                                    </div>
                                    @if ($item->machine_name)
                                        <div class="text-xs text-slate-400 mt-1 flex items-center space-x-1">
                                            <span>💻</span>
                                            <span>Máy: {{ $item->machine_name }}</span>
                                        </div>
                                    @endif
                                @else
                                    <span class="inline-flex items-center px-3 py-1 text-xs font-semibold rounded-xl bg-slate-800/80 text-slate-400 border border-slate-700">
                                        Chưa kích hoạt
                                    </span>
                                @endif
                            </td>

                            <!-- Expiry (Clean rounded numbers) -->
                            <td class="px-6 py-5 whitespace-nowrap">
                                @if ($item->expires_at === null)
                                    <span class="px-3 py-1 text-xs font-bold rounded-xl bg-purple-500/15 text-purple-300 border border-purple-500/30 shadow-sm">
                                        ✨ Vĩnh viễn (Lifetime)
                                    </span>
                                @else
                                    <div class="font-bold text-sm {{ $item->isExpired() ? 'text-rose-400' : 'text-slate-100' }}">
                                        {{ $item->expires_at->format('d/m/Y H:i') }}
                                    </div>
                                    @php
                                        $diffHours = (int) now()->diffInHours($item->expires_at, false);
                                        $diffDays = (int) ceil($diffHours / 24);
                                    @endphp
                                    @if ($item->isExpired())
                                        <div class="text-xs font-semibold text-rose-500 mt-0.5">
                                            Đã hết hạn {{ $item->expires_at->diffForHumans() }}
                                        </div>
                                    @elseif ($diffHours < 24)
                                        <div class="text-xs font-semibold text-amber-400 mt-0.5">
                                            Còn {{ max(1, $diffHours) }} giờ
                                        </div>
                                    @else
                                        <div class="text-xs font-medium text-slate-400 mt-0.5">
                                            Còn {{ $diffDays }} ngày
                                        </div>
                                    @endif
                                @endif
                            </td>

                            <!-- Status -->
                            <td class="px-6 py-5 whitespace-nowrap">
                                <button type="button" onclick="openStatusModal('{{ $item->id }}', '{{ $item->license_key }}', '{{ $item->status }}')" title="Bấm để đổi trạng thái Key" class="cursor-pointer transition-transform hover:scale-105">
                                    @if ($item->status === 'revoked')
                                        <span class="px-3 py-1 text-xs font-bold rounded-xl bg-rose-500/15 text-rose-300 border border-rose-500/30 shadow-sm">Bị thu hồi</span>
                                    @elseif ($item->status === 'suspended')
                                        <span class="px-3 py-1 text-xs font-bold rounded-xl bg-amber-500/15 text-amber-300 border border-amber-500/30 shadow-sm">Tạm dừng</span>
                                    @elseif ($item->isExpired())
                                        <span class="px-3 py-1 text-xs font-bold rounded-xl bg-rose-500/15 text-rose-300 border border-rose-500/30 shadow-sm">Hết hạn</span>
                                    @else
                                        <span class="px-3 py-1 text-xs font-bold rounded-xl bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shadow-sm flex items-center gap-1.5">
                                            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                                            <span>Hoạt động</span>
                                        </span>
                                    @endif
                                </button>
                            </td>

                            <!-- Actions -->
                            <td class="px-6 py-5 whitespace-nowrap text-right text-xs">
                                <div class="flex items-center justify-end space-x-2">
                                    <!-- Modules Config Button -->
                                    <button onclick="openModulesModal('{{ $item->id }}', '{{ $item->license_key }}', {{ json_encode($item->modules ?? ['train', 'moss', 'mirror']) }})" class="p-2 rounded-xl bg-dark-800 hover:bg-indigo-500/20 text-indigo-400 hover:text-indigo-300 border border-dark-700 hover:border-indigo-500/40 transition-all shadow-sm" title="Phân quyền Modules (Train/Moss/Mirror)">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
                                    </button>

                                    <!-- Extend Button -->
                                    <button onclick="openExtendModal('{{ $item->id }}', '{{ $item->license_key }}')" class="p-2 rounded-xl bg-dark-800 hover:bg-cyan-500/20 text-cyan-400 hover:text-cyan-300 border border-dark-700 hover:border-cyan-500/40 transition-all shadow-sm" title="Gia hạn ngày sử dụng">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
                                    </button>

                                    <!-- Status Toggle Button -->
                                    @if ($item->status === 'active')
                                        <form method="POST" action="{{ route('admin.licenses.status', $item) }}" class="inline">
                                            @csrf
                                            <input type="hidden" name="status" value="suspended">
                                            <button type="submit" class="p-2 rounded-xl bg-dark-800 hover:bg-amber-500/20 text-amber-400 hover:text-amber-300 border border-dark-700 hover:border-amber-500/40 transition-all shadow-sm" title="Tạm dừng hoạt động Key này">
                                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                            </button>
                                        </form>
                                    @elseif ($item->status === 'suspended')
                                        <form method="POST" action="{{ route('admin.licenses.status', $item) }}" class="inline">
                                            @csrf
                                            <input type="hidden" name="status" value="active">
                                            <button type="submit" class="p-2 rounded-xl bg-dark-800 hover:bg-emerald-500/20 text-emerald-400 hover:text-emerald-300 border border-dark-700 hover:border-emerald-500/40 transition-all shadow-sm" title="Kích hoạt lại Key (Bỏ tạm dừng)">
                                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                            </button>
                                        </form>
                                    @else
                                        <form method="POST" action="{{ route('admin.licenses.status', $item) }}" class="inline">
                                            @csrf
                                            <input type="hidden" name="status" value="active">
                                            <button type="submit" class="p-2 rounded-xl bg-dark-800 hover:bg-emerald-500/20 text-emerald-400 hover:text-emerald-300 border border-dark-700 hover:border-emerald-500/40 transition-all shadow-sm" title="Khôi phục Key hoạt động">
                                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                            </button>
                                        </form>
                                    @endif

                                    <!-- Delete Button -->
                                    <form method="POST" action="{{ route('admin.licenses.destroy', $item) }}" class="inline" onsubmit="return confirm('Bạn có chắc muốn XÓA vĩnh viễn Key này?')">
                                        @csrf
                                        @method('DELETE')
                                        <button type="submit" class="p-2 rounded-xl bg-dark-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 border border-dark-700 hover:border-rose-500/40 transition-all shadow-sm" title="Xóa Key">
                                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                                        </button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                    @empty
                        <tr>
                            <td colspan="8" class="px-6 py-12 text-center text-slate-500">
                                <div class="flex flex-col items-center justify-center space-y-2">
                                    <svg class="w-10 h-10 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                    <span class="text-sm font-medium">Chưa có Key bản quyền nào phù hợp với bộ lọc.</span>
                                </div>
                            </td>
                        </tr>
                    @endforelse
                </tbody>
            </table>
        </div>

        @if ($licenses->hasPages())
            <div class="px-6 py-4 border-t border-dark-750/90 bg-dark-850/80">
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
                    <input type="text" name="customer_contact" placeholder="036.203.1354 (Zalo / Hotline)" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500">
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
                <!-- Nút chọn nhanh số ngày -->
                <div class="flex flex-wrap gap-1.5 mb-2">
                    <button type="button" onclick="selectDuration('1d')" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 hover:border-cyan-500/50 transition-colors">⚡ 1 Ngày (Test)</button>
                    <button type="button" onclick="selectDuration('2d')" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 hover:border-cyan-500/50 transition-colors">2 Ngày</button>
                    <button type="button" onclick="selectDuration('3d')" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 hover:border-cyan-500/50 transition-colors">3 Ngày</button>
                    <button type="button" onclick="selectDuration('7d')" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 hover:border-cyan-500/50 transition-colors">7 Ngày</button>
                    <button type="button" onclick="selectDuration('30d')" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 hover:border-cyan-500/50 transition-colors">30 Ngày</button>
                    <button type="button" onclick="selectDuration('custom')" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-cyan-400 hover:text-cyan-300 border border-cyan-500/40 transition-colors">⚙️ Tùy chọn ngày</button>
                </div>
                <select name="duration_type" id="durationTypeSelect" onchange="toggleCustomDays(this.value)" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white focus:outline-none focus:border-cyan-500 text-sm">
                    <option value="1d">1 Ngày (Dùng thử test bot)</option>
                    <option value="2d">2 Ngày</option>
                    <option value="3d">3 Ngày (Dùng thử)</option>
                    <option value="7d">7 Ngày (1 Tuần)</option>
                    <option value="30d" selected>30 Ngày (1 Tháng)</option>
                    <option value="90d">90 Ngày (3 Tháng)</option>
                    <option value="1y">365 Ngày (1 Năm)</option>
                    <option value="lifetime">Vĩnh viễn (Lifetime)</option>
                    <option value="custom">Tùy chỉnh số ngày...</option>
                </select>
            </div>

            <div id="customDaysBox" class="hidden">
                <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Nhập số ngày cụ thể</label>
                <div class="relative">
                    <input type="number" id="customDaysInput" name="custom_days" placeholder="Ví dụ: 1, 2, 3, 5, 14, 45, 180..." min="1" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-cyan-500/50 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 text-sm">
                    <span class="absolute right-3 top-2 text-xs text-cyan-400 font-semibold">ngày</span>
                </div>
            </div>

            <!-- Cấp phép Modules tính năng -->
            <div>
                <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Cấp phép Modules tính năng (Bán theo gói)</label>
                <div class="grid grid-cols-3 gap-2 p-2.5 rounded-xl bg-dark-800 border border-dark-700">
                    <label class="flex items-center space-x-2 cursor-pointer p-1.5 rounded-lg hover:bg-dark-750 transition-colors">
                        <input type="checkbox" name="modules[]" value="train" checked class="w-4 h-4 rounded text-cyan-500 bg-dark-900 border-dark-600 focus:ring-0">
                        <span class="text-xs font-semibold text-white">⚔️ Train Auto</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer p-1.5 rounded-lg hover:bg-dark-750 transition-colors">
                        <input type="checkbox" name="modules[]" value="moss" checked class="w-4 h-4 rounded text-cyan-500 bg-dark-900 border-dark-600 focus:ring-0">
                        <span class="text-xs font-semibold text-white">🎰 Moss Merchant</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer p-1.5 rounded-lg hover:bg-dark-750 transition-colors">
                        <input type="checkbox" name="modules[]" value="mirror" checked class="w-4 h-4 rounded text-cyan-500 bg-dark-900 border-dark-600 focus:ring-0">
                        <span class="text-xs font-semibold text-white">🪞 Mirror of Dim</span>
                    </label>
                </div>
                <p class="text-[11px] text-slate-400 mt-1">Khách hàng chỉ sử dụng được các module được tích chọn. Các module không được cấp phép sẽ tự động bị ẩn trên Tool.</p>
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
                <div class="flex flex-wrap gap-1 mb-2">
                    <button type="button" onclick="selectExtendDays(1)" class="px-2 py-0.5 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 transition-colors">+1d</button>
                    <button type="button" onclick="selectExtendDays(2)" class="px-2 py-0.5 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 transition-colors">+2d</button>
                    <button type="button" onclick="selectExtendDays(3)" class="px-2 py-0.5 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 transition-colors">+3d</button>
                    <button type="button" onclick="selectExtendDays(7)" class="px-2 py-0.5 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 transition-colors">+7d</button>
                    <button type="button" onclick="selectExtendDays(30)" class="px-2 py-0.5 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 transition-colors">+30d</button>
                    <button type="button" onclick="selectExtendDays('custom')" class="px-2 py-0.5 rounded-lg text-xs font-semibold bg-dark-800 hover:bg-dark-750 text-cyan-400 border border-cyan-500/40 transition-colors">Tùy chọn</button>
                </div>
                <select name="days" id="extendDaysSelect" onchange="toggleExtendCustom(this.value)" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-dark-700 text-white text-sm focus:outline-none focus:border-cyan-500">
                    <option value="1">+1 Ngày (Dùng thử)</option>
                    <option value="2">+2 Ngày</option>
                    <option value="3">+3 Ngày</option>
                    <option value="7">+7 Ngày (1 Tuần)</option>
                    <option value="30" selected>+30 Ngày (1 Tháng)</option>
                    <option value="60">+60 Ngày (2 Tháng)</option>
                    <option value="90">+90 Ngày (3 Tháng)</option>
                    <option value="180">+180 Ngày (6 Tháng)</option>
                    <option value="365">+365 Ngày (1 Năm)</option>
                    <option value="custom">Tùy chỉnh số ngày...</option>
                </select>
            </div>

            <div id="extendCustomDaysBox" class="hidden">
                <label class="block text-xs font-bold text-slate-300 uppercase mb-1">Nhập số ngày muốn cộng thêm</label>
                <div class="relative">
                    <input type="number" id="extendCustomDaysInput" name="custom_days" placeholder="Ví dụ: 1, 2, 5, 10, 45..." min="1" class="w-full px-3 py-2 rounded-xl bg-dark-800 border border-cyan-500/50 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 text-sm">
                    <span class="absolute right-3 top-2 text-xs text-cyan-400 font-semibold">ngày</span>
                </div>
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
<!-- Modal: Đổi trạng thái Key -->
<div id="statusModal" class="hidden fixed inset-0 z-50 overflow-y-auto bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-dark-900 border border-dark-700 rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4">
        <div class="flex items-center justify-between border-b border-dark-750 pb-2">
            <h3 class="text-base font-bold text-white">Đổi Trạng Thái Bản Quyền</h3>
            <button onclick="document.getElementById('statusModal').classList.add('hidden')" class="text-slate-400 hover:text-white text-lg font-bold">&times;</button>
        </div>

        <p class="text-xs text-slate-400">Key: <span id="statusKeyName" class="font-mono font-bold text-cyan-400"></span></p>

        <form id="statusForm" method="POST" action="" class="space-y-4">
            @csrf
            <div>
                <label class="block text-xs font-bold text-slate-300 uppercase mb-2">Chọn trạng thái hoạt động</label>
                <div class="space-y-2">
                    <label class="flex items-center space-x-3 p-2.5 rounded-xl bg-dark-800 border border-dark-700 hover:border-emerald-500/40 cursor-pointer transition-colors">
                        <input type="radio" name="status" value="active" id="statusRadioActive" class="text-emerald-500 focus:ring-emerald-500">
                        <div>
                            <span class="text-xs font-bold text-emerald-400 block">🟢 Đang hoạt động</span>
                            <span class="text-[11px] text-slate-400">Cho phép bot kết nối và auto bình thường</span>
                        </div>
                    </label>

                    <label class="flex items-center space-x-3 p-2.5 rounded-xl bg-dark-800 border border-dark-700 hover:border-amber-500/40 cursor-pointer transition-colors">
                        <input type="radio" name="status" value="suspended" id="statusRadioSuspended" class="text-amber-500 focus:ring-amber-500">
                        <div>
                            <span class="text-xs font-bold text-amber-400 block">🟡 Tạm dừng hoạt động</span>
                            <span class="text-[11px] text-slate-400">Tạm khóa key, bot sẽ dừng không chạy được</span>
                        </div>
                    </label>

                    <label class="flex items-center space-x-3 p-2.5 rounded-xl bg-dark-800 border border-dark-700 hover:border-rose-500/40 cursor-pointer transition-colors">
                        <input type="radio" name="status" value="revoked" id="statusRadioRevoked" class="text-rose-500 focus:ring-rose-500">
                        <div>
                            <span class="text-xs font-bold text-rose-400 block">🔴 Thu hồi vĩnh viễn</span>
                            <span class="text-[11px] text-slate-400">Hủy hoàn toàn bản quyền của khách</span>
                        </div>
                    </label>
                </div>
            </div>

            <div class="flex items-center justify-end space-x-2 pt-2">
                <button type="button" onclick="document.getElementById('statusModal').classList.add('hidden')" class="px-3.5 py-1.5 rounded-lg bg-dark-800 text-slate-400 text-xs font-semibold hover:text-white">
                    Hủy
                </button>
                <button type="submit" class="px-4 py-1.5 rounded-lg bg-gradient-to-r from-teal-500 to-cyan-500 text-dark-950 font-bold text-xs shadow hover:from-teal-400 hover:to-cyan-400 transition-all">
                    Lưu Thay Đổi
                </button>
            </div>
        </form>
    </div>
</div>
<!-- Modal: Phân quyền Modules -->
<div id="modulesModal" class="hidden fixed inset-0 z-50 overflow-y-auto bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
    <div class="bg-dark-900 border border-dark-700 rounded-2xl max-w-md w-full p-5 shadow-2xl space-y-4">
        <div class="flex items-center justify-between border-b border-dark-750 pb-2">
            <h3 class="text-base font-bold text-white flex items-center space-x-2">
                <span>🧩</span>
                <span>Cấp Quyền Modules Tính Năng</span>
            </h3>
            <button onclick="document.getElementById('modulesModal').classList.add('hidden')" class="text-slate-400 hover:text-white text-lg font-bold">&times;</button>
        </div>

        <p class="text-xs text-slate-400">Key: <span id="modulesKeyName" class="font-mono font-bold text-indigo-400"></span></p>

        <form id="modulesForm" method="POST" action="" class="space-y-4">
            @csrf
            <div>
                <label class="block text-xs font-bold text-slate-300 uppercase mb-2">Chọn các Module được kích hoạt</label>
                <div class="space-y-2.5">
                    <label class="flex items-center space-x-3 p-3 rounded-xl bg-dark-800 border border-dark-700 hover:border-blue-500/40 cursor-pointer transition-colors">
                        <input type="checkbox" name="modules[]" value="train" id="modTrainCheck" class="w-4 h-4 rounded text-blue-500 bg-dark-900 border-dark-600 focus:ring-0">
                        <div>
                            <span class="text-xs font-bold text-blue-400 block">⚔️ Train Auto (Auto Train / MuHelper)</span>
                            <span class="text-[11px] text-slate-400">Quản lý tài khoản, auto train bãi, dùng kỹ năng và hồi máu</span>
                        </div>
                    </label>

                    <label class="flex items-center space-x-3 p-3 rounded-xl bg-dark-800 border border-dark-700 hover:border-amber-500/40 cursor-pointer transition-colors">
                        <input type="checkbox" name="modules[]" value="moss" id="modMossCheck" class="w-4 h-4 rounded text-amber-500 bg-dark-900 border-dark-600 focus:ring-0">
                        <div>
                            <span class="text-xs font-bold text-amber-400 block">🎰 Moss Merchant (Quay Đồ Moss)</span>
                            <span class="text-[11px] text-slate-400">Tự động tìm NPC Moss Elbeland, quay vũ khí, dọn rác và bán shop</span>
                        </div>
                    </label>

                    <label class="flex items-center space-x-3 p-3 rounded-xl bg-dark-800 border border-dark-700 hover:border-purple-500/40 cursor-pointer transition-colors">
                        <input type="checkbox" name="modules[]" value="mirror" id="modMirrorCheck" class="w-4 h-4 rounded text-purple-500 bg-dark-900 border-dark-600 focus:ring-0">
                        <div>
                            <span class="text-xs font-bold text-purple-400 block">🪞 Mirror of Dimensions (Double Goer)</span>
                            <span class="text-[11px] text-slate-400">Quét vé Mirror trong ba lô, cướp cổng đúng tích tắc và hỗ trợ săn boss</span>
                        </div>
                    </label>
                </div>
            </div>

            <div class="flex items-center justify-end space-x-2 pt-2">
                <button type="button" onclick="document.getElementById('modulesModal').classList.add('hidden')" class="px-3.5 py-1.5 rounded-lg bg-dark-800 text-slate-400 text-xs font-semibold hover:text-white">
                    Hủy
                </button>
                <button type="submit" class="px-4 py-1.5 rounded-lg bg-gradient-to-r from-indigo-500 to-cyan-500 text-white font-bold text-xs shadow hover:from-indigo-400 hover:to-cyan-400 transition-all">
                    Lưu Modules
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

    function selectDuration(val) {
        const select = document.getElementById('durationTypeSelect');
        if (select) {
            select.value = val;
            toggleCustomDays(val);
        }
    }

    function toggleCustomDays(val) {
        const box = document.getElementById('customDaysBox');
        const input = document.getElementById('customDaysInput');
        if (val === 'custom') {
            box.classList.remove('hidden');
            if (input) input.focus();
        } else {
            box.classList.add('hidden');
        }
    }

    function selectExtendDays(val) {
        const select = document.getElementById('extendDaysSelect');
        if (select) {
            select.value = val;
            toggleExtendCustom(val);
        }
    }

    function toggleExtendCustom(val) {
        const box = document.getElementById('extendCustomDaysBox');
        const input = document.getElementById('extendCustomDaysInput');
        if (val === 'custom') {
            box.classList.remove('hidden');
            if (input) input.focus();
        } else {
            box.classList.add('hidden');
        }
    }

    function openExtendModal(id, key) {
        document.getElementById('extendKeyName').innerText = key;
        document.getElementById('extendForm').action = '/admin/licenses/' + id + '/extend';
        // Reset selections
        const select = document.getElementById('extendDaysSelect');
        if (select) select.value = '30';
        const box = document.getElementById('extendCustomDaysBox');
        if (box) box.classList.add('hidden');
        document.getElementById('extendModal').classList.remove('hidden');
    }

    function openStatusModal(id, key, status) {
        document.getElementById('statusKeyName').innerText = key;
        document.getElementById('statusForm').action = '/admin/licenses/' + id + '/status';
        
        if (status === 'suspended') {
            document.getElementById('statusRadioSuspended').checked = true;
        } else if (status === 'revoked') {
            document.getElementById('statusRadioRevoked').checked = true;
        } else {
            document.getElementById('statusRadioActive').checked = true;
        }
        document.getElementById('statusModal').classList.remove('hidden');
    }

    function openModulesModal(id, key, modules) {
        document.getElementById('modulesKeyName').innerText = key;
        document.getElementById('modulesForm').action = '/admin/licenses/' + id + '/modules';

        const modList = Array.isArray(modules) ? modules : ['train', 'moss', 'mirror'];
        document.getElementById('modTrainCheck').checked = modList.includes('train');
        document.getElementById('modMossCheck').checked = modList.includes('moss');
        document.getElementById('modMirrorCheck').checked = modList.includes('mirror');

        document.getElementById('modulesModal').classList.remove('hidden');
    }
</script>
@endsection
