@extends('layouts.admin')

@section('title', 'Nhật ký Audit Logs')

@section('content')
<div class="space-y-6">

    <!-- Top Action Bar -->
    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
            <h1 class="text-2xl font-extrabold tracking-tight text-white">Nhật ký Hoạt động (Audit Logs)</h1>
            <p class="text-sm text-slate-400 mt-1">Lịch sử kích hoạt, xác thực định kỳ (heartbeat), reset HWID và các thao tác quản trị.</p>
        </div>
        <a href="{{ route('admin.licenses.index') }}" class="px-3.5 py-2 rounded-xl bg-dark-800 hover:bg-dark-750 border border-dark-700 text-sm font-semibold text-slate-300 hover:text-white transition-colors flex items-center space-x-2">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
            <span>Quay lại Quản lý Key</span>
        </a>
    </div>

    <!-- Filters -->
    <div class="p-4 rounded-2xl bg-dark-900 border border-dark-750">
        <form method="GET" action="{{ route('admin.licenses.logs') }}" class="flex flex-wrap gap-3 items-center">
            <div>
                <select name="action" class="px-3 py-1.5 rounded-xl bg-dark-800 border border-dark-700 text-sm text-slate-200 focus:outline-none focus:border-cyan-500">
                    <option value="">Tất cả hành động</option>
                    <option value="activate" {{ request('action') === 'activate' ? 'selected' : '' }}>Kích hoạt (Activate)</option>
                    <option value="verify" {{ request('action') === 'verify' ? 'selected' : '' }}>Xác thực (Verify)</option>
                    <option value="reset_hwid" {{ request('action') === 'reset_hwid' ? 'selected' : '' }}>Reset HWID</option>
                    <option value="extend" {{ request('action') === 'extend' ? 'selected' : '' }}>Gia hạn (Extend)</option>
                    <option value="create" {{ request('action') === 'create' ? 'selected' : '' }}>Tạo key (Create)</option>
                </select>
            </div>

            <div>
                <select name="status" class="px-3 py-1.5 rounded-xl bg-dark-800 border border-dark-700 text-sm text-slate-200 focus:outline-none focus:border-cyan-500">
                    <option value="">Tất cả kết quả</option>
                    <option value="success" {{ request('status') === 'success' ? 'selected' : '' }}>Thành công (Success)</option>
                    <option value="failed" {{ request('status') === 'failed' ? 'selected' : '' }}>Thất bại (Failed)</option>
                </select>
            </div>

            <button type="submit" class="px-4 py-1.5 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-sm font-semibold transition-colors">
                Lọc
            </button>
            @if(request()->hasAny(['action', 'status']))
                <a href="{{ route('admin.licenses.logs') }}" class="text-xs text-slate-400 hover:text-white">Xóa lọc</a>
            @endif
        </form>
    </div>

    <!-- Logs Table -->
    <div class="rounded-2xl bg-dark-900 border border-dark-750 overflow-hidden shadow-xl">
        <div class="overflow-x-auto">
            <table class="w-full text-left text-sm text-slate-300">
                <thead class="bg-dark-850/80 text-[11px] uppercase tracking-wider text-slate-400 border-b border-dark-750">
                    <tr>
                        <th class="px-4 py-3.5 font-bold">Thời gian</th>
                        <th class="px-4 py-3.5 font-bold">Hành động</th>
                        <th class="px-4 py-3.5 font-bold">Key Bản quyền</th>
                        <th class="px-4 py-3.5 font-bold">HWID / IP</th>
                        <th class="px-4 py-3.5 font-bold">Kết quả</th>
                        <th class="px-4 py-3.5 font-bold">Thông điệp chi tiết</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-dark-800">
                    @forelse ($logs as $log)
                        <tr class="hover:bg-dark-800/40 transition-colors">
                            <td class="px-4 py-3 whitespace-nowrap text-xs text-slate-400">
                                {{ $log->created_at->format('d/m/Y H:i:s') }}
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap">
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider
                                    {{ $log->action === 'activate' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : '' }}
                                    {{ $log->action === 'verify' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : '' }}
                                    {{ $log->action === 'reset_hwid' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : '' }}
                                    {{ $log->action === 'create' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' : '' }}
                                    {{ $log->action === 'extend' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : '' }}
                                ">
                                    {{ $log->action }}
                                </span>
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap font-mono text-xs">
                                {{ $log->license ? $log->license->license_key : '--' }}
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap font-mono text-xs text-slate-400">
                                <div>{{ $log->hwid ? substr($log->hwid, 0, 12) . '...' : '--' }}</div>
                                <div class="text-[10px] text-slate-500">{{ $log->ip_address ?: '127.0.0.1' }}</div>
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap">
                                @if ($log->status === 'success')
                                    <span class="inline-flex items-center text-xs text-emerald-400 font-semibold">
                                        <svg class="w-3.5 h-3.5 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path></svg>
                                        Thành công
                                    </span>
                                @else
                                    <span class="inline-flex items-center text-xs text-rose-400 font-semibold">
                                        <svg class="w-3.5 h-3.5 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path></svg>
                                        Thất bại
                                    </span>
                                @endif
                            </td>
                            <td class="px-4 py-3 text-xs text-slate-300">
                                {{ $log->message ?: '--' }}
                            </td>
                        </tr>
                    @empty
                        <tr>
                            <td colspan="6" class="px-4 py-8 text-center text-slate-500">
                                Chưa có nhật ký nào được ghi nhận.
                            </td>
                        </tr>
                    @endforelse
                </tbody>
            </table>
        </div>

        @if ($logs->hasPages())
            <div class="p-4 border-t border-dark-750 bg-dark-850">
                {{ $logs->links() }}
            </div>
        @endif
    </div>

</div>
@endsection
