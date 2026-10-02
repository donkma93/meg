<!DOCTYPE html>
<html lang="vi" class="dark scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DAuto MEGAMU - Hệ Thống Auto Train Dashboard Đỉnh Cao</title>
    <meta name="description" content="Phần mềm DAuto MEGAMU Auto Train Dashboard - Tự động tìm đường, di chuyển bãi quái theo tọa độ X, Y, gom quái, đánh skill, nhặt ngọc, hồi sinh về bãi train và hỗ trợ Multi-Client siêu mượt.">
    <meta name="keywords" content="DAuto, MEGAMU Auto Train, auto mu, megamu bot, auto train megamu, zero mouse engine, navigator megamu">
    <link rel="icon" type="image/x-icon" href="/assets/images/megamu_dashboard_icon.ico">

    <!-- Google Fonts: Be Vietnam Pro & Inter (Chuẩn 100% tiếng Việt, hiển thị sắc nét) -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400;1,600;1,700&family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">

    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['"Be Vietnam Pro"', '"Inter"', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
                        heading: ['"Be Vietnam Pro"', '"Inter"', 'sans-serif'],
                    },
                    colors: {
                        cyber: {
                            cyan: '#00f2fe',
                            blue: '#4facfe',
                            purple: '#7928ca',
                            emerald: '#10b981',
                        },
                        dark: {
                            950: '#07090e',
                            900: '#0c1017',
                            850: '#111722',
                            800: '#171f2e',
                            750: '#1f2a3e',
                            700: '#2a3750',
                        }
                    },
                    boxShadow: {
                        'neon-cyan': '0 0 25px rgba(0, 242, 254, 0.25)',
                        'neon-purple': '0 0 25px rgba(121, 40, 202, 0.25)',
                        'neon-emerald': '0 0 25px rgba(16, 185, 129, 0.25)',
                    }
                }
            }
        }
    </script>

    <!-- Multi-Language (i18n) Engine -->
    <script src="/assets/js/i18n.js"></script>

    <style>
        body {
            background-color: #07090e;
            color: #e2e8f0;
            font-family: "Be Vietnam Pro", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            overflow-x: hidden;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        h1, h2, h3, h4, .font-heading {
            font-family: "Be Vietnam Pro", "Inter", sans-serif;
            letter-spacing: -0.015em;
        }
        .glass-panel {
            background: rgba(17, 23, 34, 0.75);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .glass-card-hover {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .glass-card-hover:hover {
            transform: translateY(-6px);
            border-color: rgba(0, 242, 254, 0.4);
            box-shadow: 0 12px 30px rgba(0, 242, 254, 0.15);
        }
        .text-gradient-cyan {
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .text-gradient-gold {
            background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .bg-gradient-glow {
            background: radial-gradient(circle at 50% 0%, rgba(0, 242, 254, 0.15) 0%, rgba(121, 40, 202, 0.05) 50%, transparent 80%);
        }
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #07090e;
        }
        ::-webkit-scrollbar-thumb {
            background: #1f2a3e;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #00f2fe;
        }
    </style>
</head>
<body class="antialiased min-h-screen relative selection:bg-cyan-500 selection:text-black">

    <!-- Ambient background glows -->
    <div class="fixed top-0 left-1/4 w-[600px] h-[600px] bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none -z-10"></div>
    <div class="fixed bottom-1/4 right-10 w-[500px] h-[500px] bg-purple-600/10 rounded-full blur-[140px] pointer-events-none -z-10"></div>

    <!-- Navigation Bar -->
    <header class="sticky top-0 z-50 glass-panel border-b border-white/5 backdrop-blur-xl">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between gap-4">
            
            <!-- Brand Logo -->
            <a href="#hero" class="flex items-center space-x-3 group shrink-0">
                <img src="/assets/images/megamu_dashboard_logo.png" alt="MEGAMU Auto Train Dashboard Logo" class="h-11 w-auto object-contain group-hover:scale-105 transition-transform">
                <div>
                    <div class="flex items-center space-x-2">
                        <span class="text-xl font-black font-heading tracking-wider text-white">D<span class="text-cyan-400">AUTO</span></span>
                        <span class="text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">MEGAMU</span>
                    </div>
                    <p data-i18n="nav_subtitle" class="text-[11px] text-slate-400 font-medium tracking-tight">Auto Train Dashboard &bull; v1.5.2</p>
                </div>
            </a>

            <!-- Desktop Nav Items -->
            <nav class="hidden lg:flex items-center space-x-5 xl:space-x-7 text-xs xl:text-sm font-semibold text-slate-300">
                <a href="#showcase" data-i18n="nav_showcase" class="hover:text-cyan-400 transition-colors whitespace-nowrap">Hình Ảnh Thực Tế</a>
                <a href="#features" data-i18n="nav_features" class="hover:text-cyan-400 transition-colors whitespace-nowrap">Tính Năng</a>
                <a href="#guide" data-i18n="nav_guide" class="hover:text-cyan-400 transition-colors whitespace-nowrap">Hướng Dẫn Chạy</a>
                <a href="#pricing" data-i18n="nav_pricing" class="hover:text-cyan-400 transition-colors whitespace-nowrap">Báo Giá</a>
                <a href="#faq" data-i18n="nav_faq" class="hover:text-cyan-400 transition-colors whitespace-nowrap">Hỏi Đáp</a>
                <a href="#contact" data-i18n="nav_contact" class="hover:text-cyan-400 transition-colors whitespace-nowrap">Liên Hệ</a>
            </nav>

            <!-- Actions -->
            <div class="flex items-center space-x-2 sm:space-x-3">

                <!-- Language Selector Dropdown -->
                <div class="relative" id="langSelectorWrapper">
                    <button type="button" onclick="toggleLangDropdown()" id="langDropdownBtn" class="flex items-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-dark-850 hover:bg-dark-800 text-slate-200 border border-white/10 hover:border-cyan-400/40 transition">
                        <span id="currentLangFlag" class="text-sm">🇻🇳</span>
                        <span id="currentLangLabel" class="font-mono text-xs font-bold text-cyan-400">VI</span>
                        <svg class="w-3.5 h-3.5 text-slate-400 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                    </button>
                    <div id="langMenu" class="hidden absolute right-0 mt-2 w-48 rounded-2xl glass-panel border border-white/10 shadow-2xl py-1.5 z-50 bg-dark-900/95 backdrop-blur-xl">
                        <button type="button" onclick="setLanguage('vi')" id="lang-opt-vi" class="w-full px-3.5 py-2 text-left flex items-center space-x-2.5 text-xs font-medium hover:bg-cyan-500/10 hover:text-cyan-400 transition">
                            <span class="text-base">🇻🇳</span>
                            <span class="flex-1 font-medium">Tiếng Việt</span>
                            <span class="text-[10px] text-slate-400 font-mono">VI</span>
                        </button>
                        <button type="button" onclick="setLanguage('en')" id="lang-opt-en" class="w-full px-3.5 py-2 text-left flex items-center space-x-2.5 text-xs font-medium hover:bg-cyan-500/10 hover:text-cyan-400 transition">
                            <span class="text-base">🇬🇧</span>
                            <span class="flex-1 font-medium">English</span>
                            <span class="text-[10px] text-slate-400 font-mono">EN</span>
                        </button>
                        <button type="button" onclick="setLanguage('es')" id="lang-opt-es" class="w-full px-3.5 py-2 text-left flex items-center space-x-2.5 text-xs font-medium hover:bg-cyan-500/10 hover:text-cyan-400 transition">
                            <span class="text-base">🇪🇸</span>
                            <span class="flex-1 font-medium">Español</span>
                            <span class="text-[10px] text-slate-400 font-mono">ES</span>
                        </button>
                        <button type="button" onclick="setLanguage('pt')" id="lang-opt-pt" class="w-full px-3.5 py-2 text-left flex items-center space-x-2.5 text-xs font-medium hover:bg-cyan-500/10 hover:text-cyan-400 transition">
                            <span class="text-base">🇧🇷</span>
                            <span class="flex-1 font-medium">Português</span>
                            <span class="text-[10px] text-slate-400 font-mono">PT</span>
                        </button>
                    </div>
                </div>

                <a href="https://zalo.me/0362031354" target="_blank" class="hidden sm:inline-flex items-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-blue-600/15 hover:bg-blue-600/25 text-blue-400 border border-blue-500/30 transition">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12c0 2.21.72 4.25 1.94 5.91L3.06 21.2a1 1 0 001.24 1.24l3.29-.88C9.25 21.78 10.59 22 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2z"></path></svg>
                    <span>Zalo: 036.203.1354</span>
                </a>
                <a href="tel:0362031354" class="hidden lg:inline-flex items-center space-x-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 transition font-mono">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                    <span>036.203.1354</span>
                </a>
                <a href="#pricing" data-i18n="nav_trial_btn" class="px-4 sm:px-5 py-2.5 rounded-xl text-xs font-extrabold uppercase tracking-wider bg-gradient-to-r from-cyan-400 to-blue-500 hover:from-cyan-300 hover:to-blue-400 text-dark-950 shadow-lg shadow-cyan-500/25 transition-all transform hover:scale-[1.02] active:scale-[0.98]">
                    Liên Hệ Dùng Thử
                </a>
            </div>
        </div>
    </header>

    <!-- HERO SECTION -->
    <section id="hero" class="relative pt-12 pb-20 lg:pt-20 lg:pb-32 overflow-hidden bg-gradient-glow">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
            
            <!-- Release Badge -->
            <div class="inline-flex items-center space-x-2 px-4 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-bold tracking-wide mb-8">
                <span class="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
                <span data-i18n="hero_badge">PHẦN MỀM THỰC TẾ &bull; MEGAMU AUTO TRAIN DASHBOARD V1.5.2 CHÍNH THỨC</span>
            </div>

            <!-- Headline -->
            <h1 class="text-4xl sm:text-6xl lg:text-7xl font-black font-heading tracking-tight text-white max-w-5xl mx-auto leading-tight sm:leading-none">
                <span data-i18n="hero_title_1">Hệ Thống Auto Train Đỉnh Cao Cho </span><span class="text-gradient-cyan">MEGAMU</span>
            </h1>

            <!-- Subtitle -->
            <p class="mt-6 text-base sm:text-xl text-slate-400 max-w-3xl mx-auto leading-relaxed font-normal">
                <span data-i18n="hero_desc_1">Giao diện điều khiển chuyên nghiệp quản lý từ 10 đến 50 tài khoản đồng thời. Tự động kết nối, tự dò đường bãi train, auto nhặt đồ và hồi sinh về spot chuẩn xác. </span>
                <span data-i18n="hero_desc_2" class="text-slate-200 font-semibold">Công nghệ Zero-Mouse Hook không chiếm chuột và phím!</span>
            </p>

            <!-- Call to Actions -->
            <div class="mt-10 flex flex-wrap items-center justify-center gap-4">
                <a href="#pricing" data-i18n="hero_btn_pricing" class="px-8 py-4 rounded-2xl text-sm font-extrabold uppercase tracking-wider bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-500 hover:from-cyan-300 hover:to-blue-400 text-dark-950 shadow-xl shadow-cyan-500/25 transition-all transform hover:-translate-y-1">
                    Báo Giá Tham Khảo & Dùng Thử
                </a>
                <a href="https://zalo.me/0362031354" target="_blank" class="px-7 py-4 rounded-2xl text-sm font-extrabold tracking-wider bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/25 transition-all transform hover:-translate-y-1 flex items-center space-x-2">
                    <svg class="w-5 h-5 shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12c0 2.21.72 4.25 1.94 5.91L3.06 21.2a1 1 0 001.24 1.24l3.29-.88C9.25 21.78 10.59 22 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2z"></path></svg>
                    <span data-i18n="hero_btn_installer">Nhắn Nhận File Cài Đặt</span>
                </a>
                <a href="#showcase" class="px-7 py-4 rounded-2xl text-sm font-extrabold tracking-wider bg-dark-850 hover:bg-dark-800 text-white border border-white/10 hover:border-cyan-400/40 shadow-lg transition-all transform hover:-translate-y-1 flex items-center space-x-2">
                    <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                    </svg>
                    <span data-i18n="hero_btn_showcase">Xem Ảnh Thực Tế</span>
                </a>
            </div>
            
            <!-- Quick Contact Line -->
            <div class="mt-6 flex flex-wrap items-center justify-center gap-4 sm:gap-6 text-xs sm:text-sm text-slate-400">
                <div class="flex items-center space-x-2">
                    <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
                    <span>Hotline / Zalo: <a href="https://zalo.me/0362031354" target="_blank" class="text-cyan-400 hover:underline font-bold font-mono">036.203.1354</a></span>
                </div>
                <span data-i18n="hero_support_note" class="text-slate-500 hidden sm:inline">&bull; Hỗ trợ cài đặt Ultraview 24/7</span>
            </div>

            <!-- Stats Bar -->
            <div class="mt-14 max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-4 p-6 glass-panel rounded-3xl border border-white/10 shadow-2xl">
                <div>
                    <div class="text-3xl font-black font-heading text-cyan-400">10 - 50</div>
                    <div data-i18n="hero_stat_slots" class="text-xs text-slate-400 font-semibold uppercase tracking-wider mt-1">Slot Quản Lý Đa Acc</div>
                </div>
                <div>
                    <div class="text-3xl font-black font-heading text-emerald-400">0%</div>
                    <div data-i18n="hero_stat_mouse" class="text-xs text-slate-400 font-semibold uppercase tracking-wider mt-1">Chiếm Chuột & Phím</div>
                </div>
                <div>
                    <div class="text-3xl font-black font-heading text-indigo-400">100%</div>
                    <div data-i18n="hero_stat_bridge" class="text-xs text-slate-400 font-semibold uppercase tracking-wider mt-1">Native C++ Bridge</div>
                </div>
                <div>
                    <div class="text-3xl font-black font-heading text-amber-400">24/7</div>
                    <div data-i18n="hero_stat_auto" class="text-xs text-slate-400 font-semibold uppercase tracking-wider mt-1">Tự Động Hóa Toàn Diện</div>
                </div>
            </div>

            <!-- Hero Actual Software Image Showcase -->
            <div class="mt-16 max-w-5xl mx-auto relative group">
                <!-- Outer glow aura -->
                <div class="absolute -inset-1.5 bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-600 rounded-3xl blur-xl opacity-30 group-hover:opacity-60 transition duration-700"></div>
                
                <!-- Mockup Container -->
                <div class="relative rounded-2xl glass-panel border border-cyan-500/40 overflow-hidden shadow-2xl shadow-cyan-950/60 p-2 sm:p-3 bg-dark-900/90">
                    
                    <!-- Real Header Banner -->
                    <div class="flex items-center justify-between px-4 py-2 border-b border-white/5 mb-2 bg-dark-950/60 rounded-xl">
                        <div class="flex items-center space-x-2">
                            <span class="w-3 h-3 rounded-full bg-rose-500/80 inline-block"></span>
                            <span class="w-3 h-3 rounded-full bg-amber-500/80 inline-block"></span>
                            <span class="w-3 h-3 rounded-full bg-emerald-500/80 inline-block"></span>
                            <span data-i18n="hero_mockup_title" class="text-xs font-mono text-slate-300 ml-2 font-bold">MEGAMU Auto Train Dashboard - Màn Hình Quản Lý 10 Slot Tài Khoản</span>
                        </div>
                        <div class="flex items-center space-x-2">
                            <span data-i18n="hero_mockup_badge" class="text-[11px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/30">Ảnh chụp trực tiếp từ ứng dụng</span>
                        </div>
                    </div>

                    <!-- Actual Software Screenshot -->
                    <div class="rounded-xl overflow-hidden relative border border-white/5">
                        <img src="/assets/images/real_screenshots/real_tab_accounts.png" alt="Ảnh chụp thực tế phần mềm MEGAMU Auto Train Dashboard" class="w-full h-auto object-cover transform hover:scale-[1.01] transition-transform duration-500 shadow-inner">
                    </div>
                </div>
            </div>

        </div>
    </section>

    <!-- ACTUAL APPLICATION SHOWCASE (TABS) -->
    <section id="showcase" class="py-20 lg:py-28 relative bg-dark-900/50 border-y border-white/5">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            
            <div class="text-center max-w-3xl mx-auto mb-14">
                <span data-i18n="showcase_badge" class="text-xs font-extrabold uppercase tracking-widest text-cyan-400">TRẢI NGHIỆM THỰC TẾ</span>
                <h2 data-i18n="showcase_title" class="text-3xl sm:text-5xl font-black font-heading text-white mt-2">Giao Diện Thực Tế Của Phần Mềm</h2>
                <p data-i18n="showcase_desc" class="mt-4 text-slate-400 text-base">Xem trực tiếp các màn hình làm việc trong ứng dụng: Quản lý 10 Tài khoản, Cấu hình bãi train theo tọa độ và Nhật ký hoạt động.</p>
            </div>

            <!-- Tab Switcher Buttons -->
            <div class="flex justify-center mb-10">
                <div class="inline-flex p-1.5 rounded-2xl glass-panel border border-white/10 gap-2">
                    <button onclick="switchTab('accounts')" id="btn-tab-accounts" data-i18n="tab_accounts_btn" class="px-5 py-2.5 rounded-xl font-bold text-xs uppercase tracking-wider bg-cyan-500 text-dark-950 shadow-md transition-all">
                        1. Màn Hình Quản Lý Slot
                    </button>
                    <button onclick="switchTab('config')" id="btn-tab-config" data-i18n="tab_config_btn" class="px-5 py-2.5 rounded-xl font-bold text-xs uppercase tracking-wider text-slate-400 hover:text-white hover:bg-dark-800 transition-all">
                        2. Cấu Hình Bãi & Tọa Độ
                    </button>
                    <button onclick="switchTab('game')" id="btn-tab-game" data-i18n="tab_game_btn" class="px-5 py-2.5 rounded-xl font-bold text-xs uppercase tracking-wider text-slate-400 hover:text-white hover:bg-dark-800 transition-all">
                        3. Hình Ảnh Trong Game
                    </button>
                </div>
            </div>

            <!-- Tab 1: Accounts Screenshot -->
            <div id="panel-tab-accounts" class="max-w-5xl mx-auto glass-panel p-3 rounded-3xl border border-cyan-500/30 shadow-2xl">
                <img src="/assets/images/real_screenshots/real_tab_accounts.png" alt="Màn hình 10 Tài khoản MEGAMU Auto Train" class="w-full h-auto rounded-2xl border border-white/10 shadow-lg">
                <div class="p-5 text-sm text-slate-300 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <strong data-i18n="tab_accounts_title" class="text-cyan-400 text-base font-heading">Tab 1: Quản Lý 10 Slot Tài Khoản Tự Động</strong>
                        <p data-i18n="tab_accounts_desc" class="text-xs text-slate-400 mt-1">Tự quét PID game, kết nối hàng loạt, gán team 5 nhân vật, chọn tuyến đường Config 1..10 và giám sát trạng thái từng slot.</p>
                    </div>
                    <span data-i18n="tab_accounts_tag" class="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-xl border border-emerald-500/20 shrink-0">Chế độ Zero-Mouse Active</span>
                </div>
            </div>

            <!-- Tab 2: Config Screenshot -->
            <div id="panel-tab-config" class="max-w-5xl mx-auto glass-panel p-3 rounded-3xl border border-cyan-500/30 shadow-2xl hidden">
                <img src="/assets/images/real_screenshots/real_tab_config.png" alt="Màn hình Cấu hình Chặng Train MEGAMU Auto Train" class="w-full h-auto rounded-2xl border border-white/10 shadow-lg">
                <div class="p-5 text-sm text-slate-300 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <strong data-i18n="tab_config_title" class="text-cyan-400 text-base font-heading">Tab 2: Thiết Lập Chặng Train Theo Cấp Độ (Min/Max Level)</strong>
                        <p data-i18n="tab_config_desc" class="text-xs text-slate-400 mt-1">Cài đặt chuyển map tự động (Lorencia, Dungeon, Lost Tower, Arena...), nhập tọa độ X, Y bãi quái và thời gian chờ hồi sinh sau khi bị PK.</p>
                    </div>
                    <span data-i18n="tab_config_tag" class="text-xs font-mono text-cyan-400 bg-cyan-500/10 px-3 py-1.5 rounded-xl border border-cyan-500/20 shrink-0">Auto-Save vào JSON</span>
                </div>
            </div>

            <!-- Tab 3: Game In-Action Screenshot -->
            <div id="panel-tab-game" class="max-w-5xl mx-auto glass-panel p-3 rounded-3xl border border-cyan-500/30 shadow-2xl hidden">
                <div class="flex justify-center bg-dark-950/80 p-2 rounded-2xl">
                    <img src="/assets/images/real_screenshots/dashboard_main.png" alt="Nhân vật MEGAMU trong game" class="max-h-[600px] w-auto rounded-xl border border-white/10 shadow-lg object-contain">
                </div>
                <div class="p-5 text-sm text-slate-300 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <strong data-i18n="tab_game_title" class="text-cyan-400 text-base font-heading">Tab 3: Săn Đồ & Gom Ngọc Trong Game MEGAMU</strong>
                        <p data-i18n="tab_game_desc" class="text-xs text-slate-400 mt-1">Hỗ trợ săn đồ Hoàn Hảo (Exl), trang bị Blood Angel, tự nhặt ngọc Soul, Bless, Chaos và tích lũy Zen tự động liên tục 24/7.</p>
                    </div>
                    <span data-i18n="tab_game_tag" class="text-xs font-mono text-amber-400 bg-amber-500/10 px-3 py-1.5 rounded-xl border border-amber-500/20 shrink-0">Loot Filter Tự Động</span>
                </div>
            </div>

        </div>
    </section>

    <!-- CORE FEATURES SECTION -->
    <section id="features" class="py-20 lg:py-28 relative">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            
            <div class="text-center max-w-3xl mx-auto mb-16">
                <h2 data-i18n="feat_badge" class="text-xs font-extrabold uppercase tracking-widest text-cyan-400 mb-3">TÍNH NĂNG VƯỢT TRỘI</h2>
                <h3 data-i18n="feat_title" class="text-3xl sm:text-5xl font-black font-heading text-white">Công Nghệ Tự Động Hóa Chuyên Sâu</h3>
                <p data-i18n="feat_desc" class="mt-4 text-slate-400 text-base">Thiết kế tối ưu từng micro-giây giúp nhân vật của bạn luôn dẫn đầu bảng xếp hạng cấp độ, reset và gom ngọc.</p>
            </div>

            <!-- Features Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                
                <!-- Feature 1 -->
                <div class="p-8 rounded-3xl glass-panel glass-card-hover border border-white/5 relative group">
                    <div class="w-14 h-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
                        </svg>
                    </div>
                    <h4 data-i18n="f1_title" class="text-xl font-bold font-heading text-white mb-3">Warp Surface & Tọa Độ Chuẩn</h4>
                    <p data-i18n="f1_desc" class="text-sm text-slate-400 leading-relaxed">
                        Tự động di chuyển tới bãi train theo tọa độ X, Y cực chuẩn. Dò đường thông minh, né chướng ngại vật và tự động trở lại đúng spot sau khi chết hoặc hồi sinh.
                    </p>
                </div>

                <!-- Feature 2 -->
                <div class="p-8 rounded-3xl glass-panel glass-card-hover border border-white/5 relative group">
                    <div class="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122"></path>
                        </svg>
                    </div>
                    <h4 data-i18n="f2_title" class="text-xl font-bold font-heading text-white mb-3">Zero-Mouse Direct Engine</h4>
                    <p data-i18n="f2_desc" class="text-sm text-slate-400 leading-relaxed">
                        Điều khiển trực tiếp thông qua Frida Native Bridge. Chuột máy tính hoàn toàn tự do 100%, bạn thoải mái làm việc văn phòng, xem phim hoặc chơi game khác.
                    </p>
                </div>

                <!-- Feature 3 -->
                <div class="p-8 rounded-3xl glass-panel glass-card-hover border border-white/5 relative group">
                    <div class="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"></path>
                        </svg>
                    </div>
                    <h4 data-i18n="f3_title" class="text-xl font-bold font-heading text-white mb-3">Smart Loot Filter (Nhặt Đồ)</h4>
                    <p data-i18n="f3_desc" class="text-sm text-slate-400 leading-relaxed">
                        Tự động nhặt ngọc (Bless, Soul, Chaos, Life, Creation...), đồ Hoàn Hảo (Exl), đồ Thần (Ancient) và Zen. Tự bỏ qua rác vô giá trị giúp thùng đồ không bị đầy.
                    </p>
                </div>

                <!-- Feature 4 -->
                <div class="p-8 rounded-3xl glass-panel glass-card-hover border border-white/5 relative group">
                    <div class="w-14 h-14 rounded-2xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                        </svg>
                    </div>
                    <h4 data-i18n="f4_title" class="text-xl font-bold font-heading text-white mb-3">Combo Skill & Auto Bơm Máu</h4>
                    <p data-i18n="f4_desc" class="text-sm text-slate-400 leading-relaxed">
                        Hỗ trợ tất cả các phái (DK, DW, Elf, MG, DL, Summoner, RF, GL...). Tùy chỉnh vòng lặp skill đánh quái, tự động buff công/thủ và auto bơm máu, mana khi dưới ngưỡng an toàn.
                    </p>
                </div>

                <!-- Feature 5 -->
                <div class="p-8 rounded-3xl glass-panel glass-card-hover border border-white/5 relative group">
                    <div class="w-14 h-14 rounded-2xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path>
                        </svg>
                    </div>
                    <h4 data-i18n="f5_title" class="text-xl font-bold font-heading text-white mb-3">Quản Lý Multi-Client Đa Acc</h4>
                    <p data-i18n="f5_desc" class="text-sm text-slate-400 leading-relaxed">
                        Quản lý cùng lúc 10 đến 50 cửa sổ game trên cùng một màn hình. Hiển thị thông số thời gian thực, cấp độ, vị trí và trạng thái sống/chết của từng nhân vật.
                    </p>
                </div>

                <!-- Feature 6 -->
                <div class="p-8 rounded-3xl glass-panel glass-card-hover border border-white/5 relative group">
                    <div class="w-14 h-14 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                        <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                        </svg>
                    </div>
                    <h4 data-i18n="f6_title" class="text-xl font-bold font-heading text-white mb-3">Bảo Mật C++ Native Bridge</h4>
                    <p data-i18n-html="f6_desc" class="text-sm text-slate-400 leading-relaxed">
                        Module bảo vệ Native C++ (<code class="text-rose-300 font-mono">meg_license_bridge.dll</code>) gắn chặt với mã máy cứng HWID, chống giả mạo, mã hóa an toàn 100%.
                    </p>
                </div>

            </div>

        </div>
    </section>

    <!-- STEP-BY-STEP QUICK START GUIDE -->
    <section id="guide" class="py-20 lg:py-28 relative bg-dark-900/60 border-y border-white/5">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            
            <div class="text-center max-w-3xl mx-auto mb-16">
                <span data-i18n="guide_badge" class="text-xs font-extrabold uppercase tracking-widest text-emerald-400">DỄ DÀNG VẬN HÀNH</span>
                <h2 data-i18n="guide_title" class="text-3xl sm:text-5xl font-black font-heading text-white mt-2">Hướng Dẫn Chạy Chương Trình Trong 4 Bước</h2>
                <p data-i18n="guide_desc" class="mt-4 text-slate-400 text-base">Thao tác trực tiếp trên giao diện Dashboard, không đòi hỏi kiến thức IT.</p>
            </div>

            <!-- 4 Step Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                
                <!-- Step 1 -->
                <div class="glass-panel p-6 rounded-2xl border border-white/10 relative">
                    <div class="flex items-center justify-between mb-4">
                        <span class="w-10 h-10 rounded-xl bg-cyan-500/20 text-cyan-400 font-extrabold font-heading text-lg flex items-center justify-center border border-cyan-500/30">01</span>
                        <span data-i18n="step1_badge" class="text-xs font-semibold text-slate-400">Chuẩn bị</span>
                    </div>
                    <h3 data-i18n="step1_title" class="text-lg font-bold font-heading text-white mb-2">Xin File Cài & Key Dùng Thử</h3>
                    <p data-i18n="step1_desc" class="text-xs text-slate-400 leading-relaxed mb-3">
                        Nhắn tin Zalo / Telegram hoặc gọi Hotline <a href="https://zalo.me/0362031354" target="_blank" class="text-cyan-400 hover:underline font-bold font-mono">036.203.1354</a> để nhận file cài đặt và kích hoạt mã dùng thử miễn phí. Hỗ trợ gửi file và cài Ultraview trong 2 phút.
                    </p>
                    <a href="https://zalo.me/0362031354" target="_blank" class="inline-flex items-center space-x-1.5 text-xs text-blue-400 hover:text-blue-300 font-bold">
                        <span data-i18n="step1_btn">Nhắn Zalo xin file</span>
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                    </a>
                </div>

                <!-- Step 2 -->
                <div class="glass-panel p-6 rounded-2xl border border-white/10 relative">
                    <div class="flex items-center justify-between mb-4">
                        <span class="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 font-extrabold font-heading text-lg flex items-center justify-center border border-emerald-500/30">02</span>
                        <span data-i18n="step2_badge" class="text-xs font-semibold text-slate-400">Vào Game</span>
                    </div>
                    <h3 data-i18n="step2_title" class="text-lg font-bold font-heading text-white mb-2">Mở Game MEGAMU</h3>
                    <p data-i18n="step2_desc" class="text-xs text-slate-400 leading-relaxed">
                        Khởi động MEGAMU Launcher và đăng nhập các tài khoản game của bạn vào thế giới MEGAMU trước khi bật Auto.
                    </p>
                </div>

                <!-- Step 3 -->
                <div class="glass-panel p-6 rounded-2xl border border-white/10 relative">
                    <div class="flex items-center justify-between mb-4">
                        <span class="w-10 h-10 rounded-xl bg-purple-500/20 text-purple-400 font-extrabold font-heading text-lg flex items-center justify-center border border-purple-500/30">03</span>
                        <span data-i18n="step3_badge" class="text-xs font-semibold text-slate-400">Quyền Admin</span>
                    </div>
                    <h3 data-i18n="step3_title" class="text-lg font-bold font-heading text-white mb-2">Chạy Quyền Admin</h3>
                    <p data-i18n-html="step3_desc" class="text-xs text-slate-400 leading-relaxed">
                        Nhấp chuột phải chọn <span class="text-purple-300 font-bold">Run as Administrator</span> vào file <code class="text-purple-300 font-mono">MEGAMU Auto Train Dashboard.exe</code> để cấp quyền kết nối ngầm.
                    </p>
                </div>

                <!-- Step 4 -->
                <div class="glass-panel p-6 rounded-2xl border border-white/10 relative">
                    <div class="flex items-center justify-between mb-4">
                        <span class="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 font-extrabold font-heading text-lg flex items-center justify-center border border-amber-500/30">04</span>
                        <span data-i18n="step4_badge" class="text-xs font-semibold text-slate-400">Vận hành</span>
                    </div>
                    <h3 data-i18n="step4_title" class="text-lg font-bold font-heading text-white mb-2">Kích Hoạt & Bật Auto</h3>
                    <p data-i18n-html="step4_desc" class="text-xs text-slate-400 leading-relaxed">
                        Bấm nút <span class="text-amber-300 font-bold">Kích Hoạt</span> nhập License Key được cấp, sau đó bấm <span class="text-amber-300 font-bold">"Làm mới Game"</span> hoặc <span class="text-amber-300 font-bold">"Kết nối tất cả"</span> để bắt đầu train!
                    </p>
                </div>

            </div>

            <!-- Pro Tip Note -->
            <div class="mt-8 p-4 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-start space-x-3 text-xs text-cyan-200">
                <svg class="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <span>
                    <strong data-i18n="guide_tip_title">Mẹo thiết lập bãi train:</strong>
                    <span data-i18n-html="guide_tip_body"> Vào tab <strong class="text-white">"Cấu hình"</strong> trên Dashboard để chỉnh sửa bãi train theo tọa độ VIP do MEGATEAM cung cấp sẵn cho từng class nhân vật.</span>
                </span>
            </div>

        </div>
    </section>

    <!-- PRICING SECTION -->
    <section id="pricing" class="py-20 lg:py-28 relative">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            
            <div class="text-center max-w-3xl mx-auto mb-16">
                <span data-i18n="pricing_badge" class="text-xs font-extrabold uppercase tracking-widest text-cyan-400">BẢNG GIÁ THAM KHẢO & DÙNG THỬ</span>
                <h2 data-i18n="pricing_title" class="text-3xl sm:text-5xl font-black font-heading text-white mt-2">Báo Giá Tham Khảo & Đăng Ký Dùng Thử</h2>
                <p data-i18n="pricing_subtitle" class="mt-4 text-slate-400 text-base">Bảng giá tham khảo các gói dịch vụ. Quý khách vui lòng liên hệ trực tiếp qua Zalo hoặc Hotline để nhận file cài đặt và kích hoạt dùng thử miễn phí.</p>
            </div>

            <!-- 4 Pricing Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5 lg:gap-3 xl:gap-5 items-stretch pt-6">
                
                <!-- Plan 1: Ngày -->
                <div class="glass-panel p-5 xl:p-6 rounded-3xl border border-white/10 flex flex-col justify-between glass-card-hover relative bg-dark-900/80 shadow-lg">
                    <!-- Top Badge -->
                    <div class="absolute -top-3.5 left-1/2 transform -translate-x-1/2 px-3.5 py-1 rounded-full bg-dark-800 text-slate-300 border border-white/10 font-bold text-[10px] uppercase tracking-wider whitespace-nowrap shadow-md">
                        <span data-i18n="p1_badge">TEST NHANH</span>
                    </div>

                    <div>
                        <div class="h-5 flex items-center mb-1">
                            <span data-i18n="p1_sub" class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Trải Nghiệm</span>
                        </div>
                        <h3 data-i18n="p1_title" class="text-2xl font-black font-heading text-white h-8 flex items-center">Gói Ngày</h3>
                        <p data-i18n="p1_desc" class="text-xs text-slate-400 mt-2 h-11 flex items-start line-clamp-2 leading-relaxed">
                            Thử nghiệm đầy đủ tính năng trước khi quyết định mua dài hạn.
                        </p>
                        
                        <!-- Synchronized Price Box (No Clipping) -->
                        <div class="my-5 py-3.5 border-y border-white/10 min-h-[102px] flex flex-col justify-center">
                            <div class="flex items-baseline gap-1.5 flex-wrap">
                                <span data-i18n="p1_price" class="text-3xl lg:text-[28px] xl:text-4xl font-black font-heading text-white tracking-tight">15.000</span>
                                <span data-i18n="p1_unit" class="text-xs font-bold text-slate-400 whitespace-nowrap">VNĐ / Ngày</span>
                            </div>
                            <div class="mt-1.5 min-h-[1.75rem] flex items-center">
                                <span data-i18n="p1_subtext" class="text-[11px] text-cyan-400 font-medium leading-snug">Kích hoạt nhanh chóng qua Zalo / Telegram</span>
                            </div>
                        </div>

                        <!-- Synchronized Features List -->
                        <ul class="space-y-3 text-xs text-slate-300 mb-6">
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n-html="p1_f1" class="leading-snug">Thời hạn: <strong>24 Giờ</strong> (1 Ngày)</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p1_f2" class="leading-snug">Đầy đủ tính năng Auto Train</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p1_f3" class="leading-snug">Zero-Mouse không chiếm chuột</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p1_f4" class="leading-snug">Hỗ trợ tối đa 3 tài khoản/máy</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px] text-slate-500">
                                <svg class="w-4 h-4 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                                <span data-i18n="p1_f5" class="leading-snug">Không hỗ trợ đổi máy (Reset HWID)</span>
                            </li>
                        </ul>
                    </div>

                    <button onclick="openOrderModal('p1')" data-i18n="p1_btn" class="w-full h-12 px-3 rounded-xl font-bold text-xs uppercase tracking-wider bg-dark-800 hover:bg-dark-750 text-white border border-white/10 hover:border-cyan-400/40 transition flex items-center justify-center text-center">
                        Liên Hệ Dùng Thử Gói Ngày
                    </button>
                </div>

                <!-- Plan 2: Tháng (Popular Highlight) -->
                <div class="glass-panel p-5 xl:p-6 rounded-3xl border-2 border-cyan-400/80 flex flex-col justify-between glass-card-hover relative shadow-2xl shadow-cyan-950/60 bg-gradient-to-b from-dark-850 via-dark-850 to-dark-900">
                    <!-- Top Badge -->
                    <div class="absolute -top-3.5 left-1/2 transform -translate-x-1/2 px-4 py-1 rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 text-dark-950 font-black text-[10px] uppercase tracking-wider shadow-lg shadow-cyan-500/40 whitespace-nowrap">
                        <span data-i18n="p2_badge">⭐ PHỔ BIẾN NHẤT</span>
                    </div>

                    <div>
                        <div class="h-5 flex items-center mb-1">
                            <span data-i18n="p2_sub" class="text-[11px] font-bold uppercase tracking-wider text-cyan-400">Đua Top & Cày Cuốc</span>
                        </div>
                        <h3 data-i18n="p2_title" class="text-2xl font-black font-heading text-white h-8 flex items-center">Gói Tháng</h3>
                        <p data-i18n="p2_desc" class="text-xs text-slate-400 mt-2 h-11 flex items-start line-clamp-2 leading-relaxed">
                            Lựa chọn tối ưu nhất cho game thủ cày level và gom ngọc dài ngày.
                        </p>
                        
                        <!-- Synchronized Price Box (No Clipping) -->
                        <div class="my-5 py-3.5 border-y border-white/10 min-h-[102px] flex flex-col justify-center">
                            <div class="flex items-baseline gap-1.5 flex-wrap">
                                <span data-i18n="p2_price" class="text-3xl lg:text-[28px] xl:text-4xl font-black font-heading text-cyan-400 tracking-tight">120.000</span>
                                <span data-i18n="p2_unit" class="text-xs font-bold text-slate-400 whitespace-nowrap">VNĐ / 30 Ngày</span>
                            </div>
                            <div class="mt-1.5 min-h-[1.75rem] flex items-center">
                                <span data-i18n="p2_subtext" class="text-[11px] text-emerald-400 font-medium leading-snug">Chỉ 4.000đ / ngày (Tiết kiệm 75%)</span>
                            </div>
                        </div>

                        <!-- Synchronized Features List -->
                        <ul class="space-y-3 text-xs text-slate-300 mb-6">
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n-html="p2_f1" class="leading-snug">Thời hạn: <strong>30 Ngày</strong> liên tục</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p2_f2" class="leading-snug">Full tính năng: Auto Warp, Loot, Skill</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n-html="p2_f3" class="leading-snug">Hỗ trợ <strong>Multi-Client 10 Acc</strong> cùng lúc</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p2_f4" class="leading-snug">Cập nhật update miễn phí liên tục</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p2_f5" class="leading-snug">Hỗ trợ đổi máy: 1 lần / tháng</span>
                            </li>
                        </ul>
                    </div>

                    <button onclick="openOrderModal('p2')" data-i18n="p2_btn" class="w-full h-12 px-3 rounded-xl font-extrabold text-xs uppercase tracking-wider bg-gradient-to-r from-cyan-400 to-blue-500 hover:from-cyan-300 hover:to-blue-400 text-dark-950 shadow-lg shadow-cyan-500/25 transition-all transform hover:scale-[1.02] flex items-center justify-center text-center">
                        Liên Hệ Dùng Thử Gói Tháng
                    </button>
                </div>

                <!-- Plan 3: Quý -->
                <div class="glass-panel p-5 xl:p-6 rounded-3xl border border-white/10 flex flex-col justify-between glass-card-hover relative bg-dark-900/80 shadow-lg">
                    <!-- Top Badge -->
                    <div class="absolute -top-3.5 left-1/2 transform -translate-x-1/2 px-3.5 py-1 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-bold text-[10px] uppercase tracking-wider whitespace-nowrap shadow-md">
                        <span data-i18n="p3_badge">🔥 TIẾT KIỆM 20%</span>
                    </div>

                    <div>
                        <div class="h-5 flex items-center mb-1">
                            <span data-i18n="p3_sub" class="text-[11px] font-bold uppercase tracking-wider text-purple-400">Tiết Kiệm Cao</span>
                        </div>
                        <h3 data-i18n="p3_title" class="text-2xl font-black font-heading text-white h-8 flex items-center">Gói Quý (3T)</h3>
                        <p data-i18n="p3_desc" class="text-xs text-slate-400 mt-2 h-11 flex items-start line-clamp-2 leading-relaxed">
                            Thảnh thơi cày game trọn vẹn cả mùa Season mà không lo gia hạn.
                        </p>
                        
                        <!-- Synchronized Price Box (No Clipping) -->
                        <div class="my-5 py-3.5 border-y border-white/10 min-h-[102px] flex flex-col justify-center">
                            <div class="flex items-baseline gap-1.5 flex-wrap">
                                <span data-i18n="p3_price" class="text-3xl lg:text-[28px] xl:text-4xl font-black font-heading text-white tracking-tight">300.000</span>
                                <span data-i18n="p3_unit" class="text-xs font-bold text-slate-400 whitespace-nowrap">VNĐ / 90 Ngày</span>
                            </div>
                            <div class="mt-1.5 min-h-[1.75rem] flex items-center">
                                <span data-i18n="p3_subtext" class="text-[11px] text-purple-400 font-medium leading-snug">Chỉ 100.000đ / tháng (Tiết kiệm thêm 20%)</span>
                            </div>
                        </div>

                        <!-- Synchronized Features List -->
                        <ul class="space-y-3 text-xs text-slate-300 mb-6">
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-purple-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n-html="p3_f1" class="leading-snug">Thời hạn: <strong>90 Ngày</strong> (3 Tháng)</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-purple-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p3_f2" class="leading-snug">Multi-Client 15 Acc cùng lúc</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-purple-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p3_f3" class="leading-snug">Tặng kèm danh sách tọa độ bãi train VIP</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-purple-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p3_f4" class="leading-snug">Hỗ trợ Ultraview cài đặt từ A - Z</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-purple-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p3_f5" class="leading-snug">Hỗ trợ đổi máy: 3 lần / kỳ</span>
                            </li>
                        </ul>
                    </div>

                    <button onclick="openOrderModal('p3')" data-i18n="p3_btn" class="w-full h-12 px-3 rounded-xl font-bold text-xs uppercase tracking-wider bg-dark-800 hover:bg-dark-750 text-white border border-white/10 hover:border-purple-400/40 transition flex items-center justify-center text-center">
                        Liên Hệ Dùng Thử Gói Quý
                    </button>
                </div>

                <!-- Plan 4: Vĩnh Viễn (VIP Highlight) -->
                <div class="glass-panel p-5 xl:p-6 rounded-3xl border-2 border-amber-400/60 flex flex-col justify-between glass-card-hover relative shadow-xl shadow-amber-950/30 bg-gradient-to-b from-dark-850 via-dark-850 to-dark-900">
                    <!-- Top Badge -->
                    <div class="absolute -top-3.5 left-1/2 transform -translate-x-1/2 px-4 py-1 rounded-full bg-gradient-to-r from-amber-400 to-amber-500 text-dark-950 font-black text-[10px] uppercase tracking-wider shadow-lg shadow-amber-500/40 whitespace-nowrap">
                        <span data-i18n="p4_badge">👑 LIFETIME VIP</span>
                    </div>

                    <div>
                        <div class="h-5 flex items-center mb-1">
                            <span data-i18n="p4_sub" class="text-[11px] font-bold uppercase tracking-wider text-amber-400">Trọn Đời Mãi Mãi</span>
                        </div>
                        <h3 data-i18n="p4_title" class="text-2xl font-black font-heading text-white h-8 flex items-center">Gói Vĩnh Viễn</h3>
                        <p data-i18n="p4_desc" class="text-xs text-slate-400 mt-2 h-11 flex items-start line-clamp-2 leading-relaxed">
                            Thanh toán 1 lần duy nhất, dùng trọn đời mọi bản cập nhật.
                        </p>
                        
                        <!-- Synchronized Price Box (No Clipping) -->
                        <div class="my-5 py-3.5 border-y border-white/10 min-h-[102px] flex flex-col justify-center">
                            <div class="flex items-baseline gap-1.5 flex-wrap">
                                <span data-i18n="p4_price" class="text-3xl lg:text-[28px] xl:text-4xl font-black font-heading text-gradient-gold tracking-tight">799.000</span>
                                <span data-i18n="p4_unit" class="text-xs font-bold text-slate-400 whitespace-nowrap">VNĐ (Trọn đời)</span>
                            </div>
                            <div class="mt-1.5 min-h-[1.75rem] flex items-center">
                                <span data-i18n="p4_subtext" class="text-[11px] text-amber-300 font-medium leading-snug">Bản quyền vĩnh viễn không giới hạn</span>
                            </div>
                        </div>

                        <!-- Synchronized Features List -->
                        <ul class="space-y-3 text-xs text-slate-300 mb-6">
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n-html="p4_f1" class="leading-snug">Thời hạn: <strong class="text-amber-400">VĨNH VIỄN</strong></span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p4_f2" class="leading-snug">Không giới hạn Multi-Client (50 Slots)</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p4_f3" class="leading-snug">Cập nhật miễn phí mọi season mới</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p4_f4" class="leading-snug">Reset đổi máy không giới hạn số lần</span>
                            </li>
                            <li class="flex items-start space-x-2.5 min-h-[28px]">
                                <svg class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                                <span data-i18n="p4_f5" class="leading-snug">Group VIP Telegram hỗ trợ 24/7</span>
                            </li>
                        </ul>
                    </div>

                    <button onclick="openOrderModal('p4')" data-i18n="p4_btn" class="w-full h-12 px-3 rounded-xl font-extrabold text-xs uppercase tracking-wider bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-dark-950 shadow-lg shadow-amber-500/25 transition-all transform hover:scale-[1.02] flex items-center justify-center text-center">
                        Liên Hệ Tư Vấn & Dùng Thử
                    </button>
                </div>

            </div>

        </div>
    </section>

    <!-- FREQUENTLY ASKED QUESTIONS (FAQ) -->
    <section id="faq" class="py-20 lg:py-28 relative bg-dark-900/40 border-t border-white/5">
        <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            
            <div class="text-center mb-16">
                <span data-i18n="faq_badge" class="text-xs font-extrabold uppercase tracking-widest text-cyan-400">GIẢI ĐÁP THẮC MẮC</span>
                <h2 data-i18n="faq_title" class="text-3xl sm:text-5xl font-black font-heading text-white mt-2">Câu Hỏi Thường Gặp (FAQ)</h2>
                <p data-i18n="faq_desc" class="mt-4 text-slate-400 text-sm">Tất cả những điều bạn cần biết trước khi bắt đầu sử dụng DAuto MEGAMU.</p>
            </div>

            <!-- Accordion List -->
            <div class="space-y-4">
                
                <!-- FAQ 1 -->
                <div class="glass-panel rounded-2xl border border-white/10 overflow-hidden">
                    <button onclick="toggleFaq(1)" class="w-full px-6 py-5 text-left flex items-center justify-between font-bold font-heading text-white hover:text-cyan-400 transition">
                        <span data-i18n="faq1_q">1. Sử dụng DAuto MEGAMU có bị khóa tài khoản game không?</span>
                        <svg id="faq-icon-1" class="w-5 h-5 text-cyan-400 transform transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                    </button>
                    <div id="faq-content-1" data-i18n="faq1_a" class="hidden px-6 pb-5 text-sm text-slate-400 leading-relaxed border-t border-white/5 pt-3">
                        DAuto sử dụng cơ chế Native Hook trực tiếp và mô phỏng hành vi di chuyển tự nhiên của nhân vật, không can thiệp thay đổi file hệ thống của server. Bạn hoàn toàn an tâm khi cày cuốc, đua top và săn ngọc hàng ngày.
                    </div>
                </div>

                <!-- FAQ 2 -->
                <div class="glass-panel rounded-2xl border border-white/10 overflow-hidden">
                    <button onclick="toggleFaq(2)" class="w-full px-6 py-5 text-left flex items-center justify-between font-bold font-heading text-white hover:text-cyan-400 transition">
                        <span data-i18n="faq2_q">2. Tính năng "Zero-Mouse Không Chiếm Chuột" hoạt động như thế nào?</span>
                        <svg id="faq-icon-2" class="w-5 h-5 text-cyan-400 transform transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                    </button>
                    <div id="faq-content-2" data-i18n="faq2_a" class="hidden px-6 pb-5 text-sm text-slate-400 leading-relaxed border-t border-white/5 pt-3">
                        Khác với các phần mềm auto thông thường bắt chuột và click giả lập trên màn hình, DAuto gửi trực tiếp các lệnh di chuyển, xuất skill và nhặt đồ qua bộ nhớ ngầm. Bạn có thể thu nhỏ cửa sổ game xuống thanh taskbar, vừa auto vừa làm việc, đánh Word, Excel hoặc lướt web mà không bị gián đoạn.
                    </div>
                </div>

                <!-- FAQ 3 -->
                <div class="glass-panel rounded-2xl border border-white/10 overflow-hidden">
                    <button onclick="toggleFaq(3)" class="w-full px-6 py-5 text-left flex items-center justify-between font-bold font-heading text-white hover:text-cyan-400 transition">
                        <span data-i18n="faq3_q">3. Khi tôi đổi máy tính hoặc cài lại Windows thì License Key có dùng tiếp được không?</span>
                        <svg id="faq-icon-3" class="w-5 h-5 text-cyan-400 transform transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                    </button>
                    <div id="faq-content-3" data-i18n="faq3_a" class="hidden px-6 pb-5 text-sm text-slate-400 leading-relaxed border-t border-white/5 pt-3">
                        Hoàn toàn được! Đối với gói Tháng, Quý và Vĩnh Viễn, hệ thống hỗ trợ reset mã phần cứng (HWID) nhanh chóng. Bạn chỉ cần nhắn tin cho admin kèm mã License Key để được cấp quyền mở khóa sang máy tính mới ngay lập tức.
                    </div>
                </div>

                <!-- FAQ 4 -->
                <div class="glass-panel rounded-2xl border border-white/10 overflow-hidden">
                    <button onclick="toggleFaq(4)" class="w-full px-6 py-5 text-left flex items-center justify-between font-bold font-heading text-white hover:text-cyan-400 transition">
                        <span data-i18n="faq4_q">4. Làm sao để tôi nhận được file cài đặt và mã kích hoạt dùng thử?</span>
                        <svg id="faq-icon-4" class="w-5 h-5 text-cyan-400 transform transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                    </button>
                    <div id="faq-content-4" data-i18n="faq4_a" class="hidden px-6 pb-5 text-sm text-slate-400 leading-relaxed border-t border-white/5 pt-3">
                        Rất đơn giản! Bạn chỉ cần liên hệ trực tiếp qua Zalo, Telegram hoặc Hotline 036.203.1354. Đội ngũ MEGATEAM sẽ gửi ngay file cài đặt mới nhất kèm mã bản quyền trải nghiệm dùng thử miễn phí và hỗ trợ cấu hình Ultraview nếu cần.
                    </div>
                </div>

            </div>

        </div>
    </section>

    <!-- CONTACT & SUPPORT BANNER -->
    <section id="contact" class="py-20 lg:py-24 relative overflow-hidden">
        <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="glass-panel p-8 sm:p-14 rounded-3xl border border-cyan-500/30 bg-gradient-to-r from-dark-900 via-dark-850 to-dark-900 shadow-2xl relative overflow-hidden text-center">
                
                <div class="max-w-2xl mx-auto relative z-10">
                    <h2 data-i18n="contact_banner_title" class="text-3xl sm:text-4xl font-black font-heading text-white">Bạn Cần Tư Vấn Hoặc Cài Đặt Thử Nghiệm?</h2>
                    <p data-i18n="contact_banner_desc" class="mt-4 text-slate-400 text-sm sm:text-base leading-relaxed">
                        Đội ngũ hỗ trợ kỹ thuật của chúng tôi luôn trực tuyến 24/7 để hỗ trợ bạn cài đặt qua Ultraview, giải đáp thắc mắc và cấp mã bản quyền ngay lập tức.
                    </p>

                    <div class="mt-8 flex flex-wrap justify-center gap-4">
                        <!-- Zalo Button -->
                        <a href="https://zalo.me/0362031354" target="_blank" class="px-6 py-3.5 rounded-xl font-bold text-xs uppercase tracking-wider bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/30 transition flex items-center space-x-2">
                            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12c0 2.21.72 4.25 1.94 5.91L3.06 21.2a1 1 0 001.24 1.24l3.29-.88C9.25 21.78 10.59 22 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2z"></path></svg>
                            <span>Zalo: 036.203.1354</span>
                        </a>

                        <!-- Hotline / Call Button -->
                        <a href="tel:0362031354" class="px-6 py-3.5 rounded-xl font-bold text-xs uppercase tracking-wider bg-dark-800 hover:bg-dark-750 text-white border border-white/10 hover:border-emerald-500/40 transition flex items-center space-x-2">
                            <svg class="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                            <span>Hotline: 036.203.1354</span>
                        </a>

                        <!-- Telegram Button -->
                        <a href="https://t.me" target="_blank" class="px-6 py-3.5 rounded-xl font-bold text-xs uppercase tracking-wider bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-600/30 transition flex items-center space-x-2">
                            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.75-.55 2.92-1.27 4.86-2.11 5.83-2.52 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"></path></svg>
                            <span data-i18n="contact_btn_telegram">Telegram Hỗ Trợ</span>
                        </a>
                    </div>
                </div>

            </div>
        </div>
    </section>

    <!-- FOOTER -->
    <footer class="border-t border-white/5 bg-dark-950 py-12 text-sm text-slate-500">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-6">
            
            <div class="flex items-center space-x-3">
                <img src="/assets/images/megamu_dashboard_logo.png" alt="DAuto MEGAMU Logo" class="h-8 w-auto object-contain">
                <div>
                    <span class="font-extrabold font-heading text-white">DAuto MEGAMU</span>
                    <p data-i18n="footer_desc" class="text-xs text-slate-400 mt-0.5">Giải pháp tự động hóa hàng đầu cho cộng đồng MEGAMU.</p>
                    <p class="text-[11px] text-slate-500 mt-0.5">&copy; {{ date('Y') }} MEGATEAM Solutions &bull; <span data-i18n="footer_rights">Bảo lưu mọi quyền.</span></p>
                </div>
            </div>

            <div class="flex flex-wrap items-center gap-6 text-xs font-semibold">
                <a href="#showcase" data-i18n="nav_showcase" class="hover:text-cyan-400 transition">Hình Ảnh Thực Tế</a>
                <a href="#features" data-i18n="nav_features" class="hover:text-cyan-400 transition">Tính Năng</a>
                <a href="#guide" data-i18n="nav_guide" class="hover:text-cyan-400 transition">Hướng Dẫn Chạy</a>
                <a href="#pricing" data-i18n="nav_pricing" class="hover:text-cyan-400 transition">Báo Giá</a>
                <a href="#faq" data-i18n="nav_faq" class="hover:text-cyan-400 transition">Hỏi Đáp</a>
                <a href="#contact" data-i18n="nav_contact" class="hover:text-cyan-400 transition">Liên Hệ</a>
            </div>

        </div>
    </footer>

    <!-- ORDER / PURCHASE MODAL -->
    <div id="orderModal" class="fixed inset-0 z-50 hidden flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
        <div class="glass-panel max-w-lg w-full rounded-3xl p-6 sm:p-8 border border-cyan-500/40 shadow-2xl relative animate-fade-in">
            
            <!-- Close Button -->
            <button onclick="closeOrderModal()" class="absolute top-5 right-5 text-slate-400 hover:text-white transition">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
            </button>

            <!-- Modal Header -->
            <div class="text-center mb-6">
                <div class="w-12 h-12 rounded-2xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center mx-auto mb-3 border border-cyan-500/20">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
                </div>
                <h3 data-i18n="modal_title" class="text-2xl font-black font-heading text-white">Đăng Ký Trải Nghiệm & Dùng Thử</h3>
                <p data-i18n="modal_subtitle" class="text-xs text-slate-400 mt-1">Liên hệ nhận file cài đặt & kích hoạt key dùng thử DAuto MEGAMU</p>
            </div>

            <!-- Selected Package Box -->
            <div class="p-4 rounded-2xl bg-dark-850 border border-white/10 mb-6 flex items-center justify-between">
                <div>
                    <span data-i18n="modal_plan_label" class="text-xs text-slate-400 block">Gói quan tâm:</span>
                    <strong id="modalPlanName" class="text-sm font-bold text-white">Gói Tháng</strong>
                </div>
                <div class="text-right">
                    <span data-i18n="modal_price_label" class="text-xs text-slate-400 block">Giá tham khảo:</span>
                    <strong id="modalPlanPrice" class="text-lg font-black font-heading text-cyan-400">120.000 VNĐ</strong>
                </div>
            </div>

            <!-- Contact Instruction (No Bank Details) -->
            <div class="space-y-4 mb-6 text-xs text-slate-300">
                <div class="p-5 rounded-2xl bg-dark-900 border border-white/5 space-y-3">
                    <div class="flex items-center space-x-2 text-emerald-400 font-bold">
                        <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                        <span data-i18n="modal_box_title">Cấp Key Dùng Thử & Hỗ Trợ Cài Đặt Trực Tiếp</span>
                    </div>
                    <p data-i18n="modal_box_desc" class="text-slate-400 leading-relaxed text-xs">
                        Để nhận file cài đặt và kích hoạt mã dùng thử trải nghiệm gói này, quý khách vui lòng liên hệ trực tiếp qua Zalo hoặc Hotline. Đội ngũ MEGATEAM sẽ gửi file và hỗ trợ bạn cài đặt qua Ultraview nhanh chóng trong 2 phút.
                    </p>
                    <div class="pt-3 border-t border-white/5 flex items-center justify-between">
                        <span data-i18n="modal_hotline_label" class="text-slate-400">Hotline / Zalo hỗ trợ:</span>
                        <a href="https://zalo.me/0362031354" target="_blank" class="font-mono font-bold text-cyan-400 text-sm hover:underline">036.203.1354</a>
                    </div>
                </div>
                <p data-i18n="modal_instruction" class="text-slate-400 text-[11px] text-center">
                    Bấm vào nút bên dưới để nhắn tin Zalo hoặc gọi Hotline nhận file cài đặt ngay:
                </p>
            </div>

            <!-- Modal Action Buttons -->
            <div class="flex flex-col sm:flex-row gap-3">
                <a href="https://zalo.me/0362031354" target="_blank" class="flex-1 py-3 px-4 rounded-xl font-bold text-xs uppercase tracking-wider bg-gradient-to-r from-cyan-400 to-blue-500 text-dark-950 text-center shadow-lg shadow-cyan-500/25 hover:from-cyan-300 transition flex items-center justify-center space-x-2">
                    <svg class="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12c0 2.21.72 4.25 1.94 5.91L3.06 21.2a1 1 0 001.24 1.24l3.29-.88C9.25 21.78 10.59 22 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2z"></path></svg>
                    <span data-i18n="modal_btn_zalo">Nhắn Zalo Nhận Bản Dùng Thử</span>
                </a>
                <a href="tel:0362031354" class="py-3 px-4 rounded-xl font-bold text-xs uppercase tracking-wider bg-dark-800 hover:bg-dark-750 text-emerald-400 border border-emerald-500/30 text-center transition flex items-center justify-center space-x-1.5 font-mono">
                    <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                    <span data-i18n="modal_btn_call">Gọi 036.203.1354</span>
                </a>
                <button onclick="closeOrderModal()" data-i18n="modal_btn_close" class="py-3 px-4 rounded-xl font-bold text-xs text-slate-400 hover:text-white bg-dark-800 transition">
                    Đóng
                </button>
            </div>

        </div>
    </div>

    <!-- FLOATING CONTACT WIDGET (HOTLINE & ZALO) -->
    <div class="fixed bottom-6 right-6 z-40 flex flex-col items-end space-y-3">
        <!-- Hotline Floating Button -->
        <a href="tel:0362031354" class="group flex items-center space-x-2.5 pl-3.5 pr-2 py-2 rounded-full bg-dark-900/90 hover:bg-dark-850 text-white border border-emerald-500/40 shadow-xl backdrop-blur-md transition-all transform hover:-translate-x-1 hover:scale-105">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping shrink-0"></span>
            <span class="text-xs font-bold text-emerald-400 font-mono tracking-tight">Hotline: 036.203.1354</span>
            <div class="w-8 h-8 rounded-full bg-emerald-500 text-dark-950 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
            </div>
        </a>

        <!-- Zalo Floating Button -->
        <a href="https://zalo.me/0362031354" target="_blank" class="group flex items-center space-x-2.5 pl-4 pr-2 py-2 rounded-full bg-blue-600 hover:bg-blue-500 text-white shadow-xl shadow-blue-600/30 transition-all transform hover:-translate-x-1 hover:scale-105">
            <span class="text-xs font-bold tracking-tight">Zalo: 036.203.1354</span>
            <div class="w-8 h-8 rounded-full bg-white text-blue-600 flex items-center justify-center shadow">
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12c0 2.21.72 4.25 1.94 5.91L3.06 21.2a1 1 0 001.24 1.24l3.29-.88C9.25 21.78 10.59 22 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2z"></path></svg>
            </div>
        </a>
    </div>

    <!-- Vanilla Javascript Logic -->
    <script>
        // Modal Handlers with i18n support
        function openOrderModal(planKeyOrName, planPrice) {
            let name = planKeyOrName;
            let price = planPrice;

            if (typeof getTranslation === 'function') {
                if (planKeyOrName === 'p1') {
                    name = getTranslation('p1_title') + ' (24H)';
                    price = getTranslation('p1_price') + ' ' + getTranslation('p1_unit');
                } else if (planKeyOrName === 'p2') {
                    name = getTranslation('p2_title') + ' (30D)';
                    price = getTranslation('p2_price') + ' ' + getTranslation('p2_unit');
                } else if (planKeyOrName === 'p3') {
                    name = getTranslation('p3_title') + ' (90D)';
                    price = getTranslation('p3_price') + ' ' + getTranslation('p3_unit');
                } else if (planKeyOrName === 'p4') {
                    name = getTranslation('p4_title') + ' (Lifetime)';
                    price = getTranslation('p4_price') + ' ' + getTranslation('p4_unit');
                }
            }

            document.getElementById('modalPlanName').innerText = name;
            document.getElementById('modalPlanPrice').innerText = price;
            const modal = document.getElementById('orderModal');
            modal.classList.remove('hidden');
        }

        function closeOrderModal() {
            document.getElementById('orderModal').classList.add('hidden');
        }

        // Close modal on click outside
        document.getElementById('orderModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeOrderModal();
            }
        });

        // Screenshot Showcase Tab Switcher
        function switchTab(tabId) {
            const tabs = ['accounts', 'config', 'game'];
            tabs.forEach(t => {
                const panel = document.getElementById('panel-tab-' + t);
                const btn = document.getElementById('btn-tab-' + t);
                if (t === tabId) {
                    panel.classList.remove('hidden');
                    btn.className = "px-5 py-2.5 rounded-xl font-bold text-xs uppercase tracking-wider bg-cyan-500 text-dark-950 shadow-md transition-all";
                } else {
                    panel.classList.add('hidden');
                    btn.className = "px-5 py-2.5 rounded-xl font-bold text-xs uppercase tracking-wider text-slate-400 hover:text-white hover:bg-dark-800 transition-all";
                }
            });
        }

        // FAQ Accordion Toggle
        function toggleFaq(id) {
            const content = document.getElementById('faq-content-' + id);
            const icon = document.getElementById('faq-icon-' + id);
            
            if (content.classList.contains('hidden')) {
                content.classList.remove('hidden');
                icon.classList.add('rotate-180');
            } else {
                content.classList.add('hidden');
                icon.classList.remove('rotate-180');
            }
        }
    </script>

</body>
</html>
