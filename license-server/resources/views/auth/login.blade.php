<!DOCTYPE html>
<html lang="vi" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Đăng Nhập Quản Trị | MEGATEAM License Server</title>
    <!-- Fonts: Be Vietnam Pro -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:ital,wght@0,400;0,500;0,600;0,700;0,800&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['"Be Vietnam Pro"', 'Segoe UI', 'sans-serif'],
                    },
                    colors: {
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
            font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
    </style>
</head>
<body class="min-h-screen flex items-center justify-center p-4 antialiased relative overflow-hidden bg-[#090c13]">

    <!-- Decorative background glow circles -->
    <div class="absolute -top-32 -left-32 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl pointer-events-none"></div>
    <div class="absolute -bottom-32 -right-32 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>

    <div class="w-full max-w-md relative z-10">
        
        <!-- Header Brand -->
        <div class="text-center mb-8">
            <div class="inline-flex w-14 h-14 rounded-2xl bg-gradient-to-tr from-teal-500 to-cyan-400 items-center justify-center shadow-xl shadow-teal-500/25 mb-4">
                <svg class="w-8 h-8 text-dark-950 font-bold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
                </svg>
            </div>
            <h1 class="text-2xl font-extrabold text-white tracking-tight">MEGATEAM License Server</h1>
            <p class="text-sm text-slate-400 mt-1">Đăng nhập tài khoản quản trị viên</p>
        </div>

        <!-- Flash messages -->
        @if (session('success'))
            <div class="mb-4 p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm text-center">
                {{ session('success') }}
            </div>
        @endif

        @if ($errors->any())
            <div class="mb-4 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
                @foreach ($errors->all() as $error)
                    <p>{{ $error }}</p>
                @endforeach
            </div>
        @endif

        <!-- Card Form -->
        <div class="bg-dark-900 border border-dark-750/80 rounded-2xl p-7 shadow-2xl backdrop-blur">
            <form action="{{ route('login.post') }}" method="POST" class="space-y-5">
                @csrf

                <div>
                    <label for="email" class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                        Tài khoản / Email
                    </label>
                    <div class="relative">
                        <input type="text" id="email" name="email" value="{{ old('email') }}" required autofocus
                            placeholder="admin@megamu.vn hoặc admin"
                            class="w-full px-4 py-2.5 rounded-xl bg-dark-850 border border-dark-700 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition text-sm">
                    </div>
                </div>

                <div>
                    <div class="flex items-center justify-between mb-2">
                        <label for="password" class="block text-xs font-bold text-slate-300 uppercase tracking-wider">
                            Mật khẩu
                        </label>
                    </div>
                    <div class="relative">
                        <input type="password" id="password" name="password" required
                            placeholder="••••••••••••"
                            class="w-full px-4 py-2.5 rounded-xl bg-dark-850 border border-dark-700 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition text-sm">
                    </div>
                </div>

                <div class="flex items-center justify-between">
                    <label class="flex items-center space-x-2 text-xs text-slate-400 cursor-pointer">
                        <input type="checkbox" name="remember" class="w-4 h-4 rounded bg-dark-800 border-dark-700 text-cyan-500 focus:ring-0">
                        <span>Ghi nhớ đăng nhập</span>
                    </label>
                </div>

                <button type="submit"
                    class="w-full py-3 px-4 rounded-xl font-bold text-sm bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-dark-950 shadow-lg shadow-teal-500/25 transition-all transform active:scale-[0.98]">
                    Đăng Nhập Quản Trị
                </button>
            </form>
        </div>

        <!-- Footer -->
        <p class="text-center text-xs text-slate-600 mt-6">
            &copy; {{ date('Y') }} MEGATEAM License Manager &bull; Hệ thống bảo mật 3 lớp Native Bridge
        </p>

    </div>

</body>
</html>
