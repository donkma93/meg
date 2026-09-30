<!DOCTYPE html>
<html lang="vi" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', 'Quản lý Bản quyền') | donpv License Manager</title>
    <!-- Google Fonts: Inter / Segoe UI -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- Tailwind CSS CDN for swift, responsive dark styling -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['"Plus Jakarta Sans"', 'Segoe UI', 'sans-serif'],
                    },
                    colors: {
                        brand: {
                            50: '#f0fdfa',
                            100: '#ccfbf1',
                            400: '#2dd4bf',
                            500: '#14b8a6',
                            600: '#0d9488',
                        },
                        cyan: {
                            400: '#38bdf8',
                            500: '#0ea5e9',
                        },
                        dark: {
                            950: '#090c13',
                            900: '#0e111a',
                            850: '#131722',
                            800: '#181d2c',
                            750: '#1f2538',
                            700: '#283046',
                        }
                    }
                }
            }
        }
    </script>
    <style>
        body {
            background-color: #090c13;
            color: #f1f5f9;
            font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #0e111a;
        }
        ::-webkit-scrollbar-thumb {
            background: #283046;
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #38bdf8;
        }
    </style>
</head>
<body class="min-h-screen flex flex-col bg-[#090c13] text-slate-100 antialiased">

    <!-- Top Header -->
    <header class="border-b border-dark-750 bg-dark-900/90 backdrop-blur sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <!-- Brand Logo -->
            <div class="flex items-center space-x-4">
                <a href="{{ route('admin.licenses.index') }}" class="flex items-center space-x-3 group">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-teal-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-teal-500/20 group-hover:scale-105 transition-transform">
                        <svg class="w-6 h-6 text-dark-950 font-bold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
                        </svg>
                    </div>
                    <div>
                        <div class="flex items-center space-x-2">
                            <span class="text-base font-extrabold tracking-tight text-white group-hover:text-cyan-400 transition-colors">donpv License Server</span>
                            <span class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/20">v1.0</span>
                        </div>
                        <p class="text-xs text-slate-400">Hệ thống cấp phép & xác thực bản quyền trực tuyến</p>
                    </div>
                </a>

                <!-- Navigation Tabs -->
                <nav class="hidden md:flex items-center space-x-1 ml-8">
                    <a href="{{ route('admin.licenses.index') }}" class="px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-all {{ request()->routeIs('admin.licenses.index') ? 'bg-dark-800 text-cyan-400 border border-cyan-500/30 shadow-sm' : 'text-slate-400 hover:text-white hover:bg-dark-800/50' }}">
                        Bản quyền (Licenses)
                    </a>
                    <a href="{{ route('admin.licenses.logs') }}" class="px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-all {{ request()->routeIs('admin.licenses.logs') ? 'bg-dark-800 text-cyan-400 border border-cyan-500/30 shadow-sm' : 'text-slate-400 hover:text-white hover:bg-dark-800/50' }}">
                        Nhật ký Audit (Logs)
                    </a>
                </nav>
            </div>

            <!-- Right Profile / Status -->
            <div class="flex items-center space-x-3">
                <div class="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-dark-850 border border-dark-750">
                    <div class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></div>
                    <span class="text-xs font-semibold text-slate-300">API Server: Online</span>
                </div>
                <div class="h-6 w-px bg-dark-750"></div>
                <div class="flex items-center space-x-3 pl-1">
                    <div class="flex items-center space-x-2">
                        <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-teal-500/20 to-cyan-500/20 border border-teal-500/40 flex items-center justify-center text-teal-300 font-bold text-xs">
                            {{ strtoupper(substr(Auth::user()->name ?? 'AD', 0, 2)) }}
                        </div>
                        <span class="text-xs font-bold text-slate-200 hidden sm:inline">{{ Auth::user()->name ?? 'Admin' }}</span>
                    </div>

                    <form method="POST" action="{{ route('logout') }}" class="inline">
                        @csrf
                        <button type="submit" title="Đăng xuất" class="p-2 rounded-lg bg-dark-850 hover:bg-rose-500/20 border border-dark-750 hover:border-rose-500/30 text-slate-400 hover:text-rose-400 transition-colors">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
                            </svg>
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </header>

    <!-- Flash Notifications -->
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4 w-full">
        @if (session('success'))
            <div class="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm flex items-center justify-between shadow-lg">
                <div class="flex items-center space-x-2.5">
                    <svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>
                    <span>{{ session('success') }}</span>
                </div>
                <button onclick="this.parentElement.remove()" class="text-emerald-400 hover:text-white">&times;</button>
            </div>
        @endif

        @if (session('info'))
            <div class="p-3.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-sm flex items-center justify-between shadow-lg">
                <div class="flex items-center space-x-2.5">
                    <svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>
                    <span>{{ session('info') }}</span>
                </div>
                <button onclick="this.parentElement.remove()" class="text-cyan-400 hover:text-white">&times;</button>
            </div>
        @endif

        @if ($errors->any())
            <div class="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
                <div class="font-bold mb-1">Có lỗi xảy ra:</div>
                <ul class="list-disc pl-5 space-x-1">
                    @foreach ($errors->all() as $err)
                        <li>{{ $err }}</li>
                    @endforeach
                </ul>
            </div>
        @endif
    </div>

    <!-- Main Content -->
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        @yield('content')
    </main>

    <!-- Footer -->
    <footer class="border-t border-dark-750 bg-dark-900 py-4 mt-auto">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
            <div>
                © {{ date('Y') }} <span class="text-slate-300 font-semibold">donpv</span> • MEGAMU Auto Train Dashboard License System.
            </div>
            <div class="flex items-center space-x-4">
                <span>API Endpoint: <code class="text-cyan-400 bg-dark-800 px-1.5 py-0.5 rounded">/api/v1/license/activate</code></span>
                <span>SQLite DB: <span class="text-emerald-400">Online</span></span>
            </div>
        </div>
    </footer>

    @yield('scripts')
</body>
</html>
