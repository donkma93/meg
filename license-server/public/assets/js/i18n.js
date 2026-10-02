/**
 * DAuto MEGAMU - Multi-language (i18n) Engine
 * Supported Languages:
 *   - vi: Tiếng Việt (Vietnamese - Default)
 *   - en: English
 *   - es: Español (Spanish)
 *   - pt: Português (Portuguese - Brazil)
 */

const I18N_DICTIONARY = {
    vi: {
        page_title: "DAuto MEGAMU - Hệ Thống Auto Train Dashboard Đỉnh Cao",
        meta_desc: "Phần mềm DAuto MEGAMU Auto Train Dashboard - Tự động tìm đường, di chuyển bãi quái theo tọa độ X, Y, gom quái, đánh skill, nhặt ngọc, hồi sinh về bãi train và hỗ trợ Multi-Client siêu mượt.",
        
        // Navigation
        nav_showcase: "Hình Ảnh Thực Tế",
        nav_features: "Tính Năng",
        nav_guide: "Hướng Dẫn Chạy",
        nav_pricing: "Báo Giá",
        nav_faq: "Hỏi Đáp",
        nav_contact: "Liên Hệ",
        nav_trial_btn: "Liên Hệ Dùng Thử",
        nav_subtitle: "Auto Train Dashboard • v1.5.2",

        // Hero Section
        hero_badge: "PHẦN MỀM THỰC TẾ • MEGAMU AUTO TRAIN DASHBOARD V1.5.2 CHÍNH THỨC",
        hero_title_1: "Hệ Thống Auto Train Đỉnh Cao Cho ",
        hero_desc_1: "Giao diện điều khiển chuyên nghiệp quản lý từ 10 đến 50 tài khoản đồng thời. Tự động kết nối, tự dò đường bãi train, auto nhặt đồ và hồi sinh về spot chuẩn xác. ",
        hero_desc_2: "Công nghệ Zero-Mouse Hook không chiếm chuột và phím!",
        hero_btn_pricing: "Báo Giá Tham Khảo & Dùng Thử",
        hero_btn_installer: "Nhắn Nhận File Cài Đặt",
        hero_btn_showcase: "Xem Ảnh Thực Tế",
        hero_support_note: "• Hỗ trợ cài đặt Ultraview 24/7",
        hero_stat_slots: "Slot Quản Lý Đa Acc",
        hero_stat_mouse: "Chiếm Chuột & Phím",
        hero_stat_bridge: "Native C++ Bridge",
        hero_stat_auto: "Tự Động Hóa Toàn Diện",
        hero_mockup_title: "MEGAMU Auto Train Dashboard - Màn Hình Quản Lý 10 Slot Tài Khoản",
        hero_mockup_badge: "Ảnh chụp trực tiếp từ ứng dụng",

        // Showcase Section
        showcase_badge: "TRẢI NGHIỆM THỰC TẾ",
        showcase_title: "Giao Diện Thực Tế Của Phần Mềm",
        showcase_desc: "Xem trực tiếp các màn hình làm việc trong ứng dụng: Quản lý 10 Tài khoản, Cấu hình bãi train theo tọa độ và Nhật ký hoạt động.",
        tab_accounts_btn: "1. Màn Hình Quản Lý Slot",
        tab_config_btn: "2. Cấu Hình Bãi & Tọa Độ",
        tab_game_btn: "3. Hình Ảnh Trong Game",
        tab_accounts_title: "Tab 1: Quản Lý 10 Slot Tài Khoản Tự Động",
        tab_accounts_desc: "Tự quét PID game, kết nối hàng loạt, gán team 5 nhân vật, chọn tuyến đường Config 1..10 và giám sát trạng thái từng slot.",
        tab_accounts_tag: "Chế độ Zero-Mouse Active",
        tab_config_title: "Tab 2: Thiết Lập Chặng Train Theo Cấp Độ (Min/Max Level)",
        tab_config_desc: "Cài đặt chuyển map tự động (Lorencia, Dungeon, Lost Tower, Arena...), nhập tọa độ X, Y bãi quái và thời gian chờ hồi sinh sau khi bị PK.",
        tab_config_tag: "Auto-Save vào JSON",
        tab_game_title: "Tab 3: Săn Đồ & Gom Ngọc Trong Game MEGAMU",
        tab_game_desc: "Hỗ trợ săn đồ Hoàn Hảo (Exl), trang bị Blood Angel, tự nhặt ngọc Soul, Bless, Chaos và tích lũy Zen tự động liên tục 24/7.",
        tab_game_tag: "Loot Filter Tự Động",

        // Features Section
        feat_badge: "TÍNH NĂNG VƯỢT TRỘI",
        feat_title: "Công Nghệ Tự Động Hóa Chuyên Sâu",
        feat_desc: "Thiết kế tối ưu từng micro-giây giúp nhân vật của bạn luôn dẫn đầu bảng xếp hạng cấp độ, reset và gom ngọc.",
        f1_title: "Warp Surface & Tọa Độ Chuẩn",
        f1_desc: "Tự động di chuyển tới bãi train theo tọa độ X, Y cực chuẩn. Dò đường thông minh, né chướng ngại vật và tự động trở lại đúng spot sau khi chết hoặc hồi sinh.",
        f2_title: "Zero-Mouse Direct Engine",
        f2_desc: "Điều khiển trực tiếp thông qua Frida Native Bridge. Chuột máy tính hoàn toàn tự do 100%, bạn thoải mái làm việc văn phòng, xem phim hoặc chơi game khác.",
        f3_title: "Smart Loot Filter (Nhặt Đồ)",
        f3_desc: "Tự động nhặt ngọc (Bless, Soul, Chaos, Life, Creation...), đồ Hoàn Hảo (Exl), đồ Thần (Ancient) và Zen. Tự bỏ qua rác vô giá trị giúp thùng đồ không bị đầy.",
        f4_title: "Combo Skill & Auto Bơm Máu",
        f4_desc: "Hỗ trợ tất cả các phái (DK, DW, Elf, MG, DL, Summoner, RF, GL...). Tùy chỉnh vòng lặp skill đánh quái, tự động buff công/thủ và auto bơm máu, mana khi dưới ngưỡng an toàn.",
        f5_title: "Quản Lý Multi-Client Đa Acc",
        f5_desc: "Quản lý cùng lúc 10 đến 50 cửa sổ game trên cùng một màn hình. Hiển thị thông số thời gian thực, cấp độ, vị trí và trạng thái sống/chết của từng nhân vật.",
        f6_title: "Bảo Mật C++ Native Bridge",
        f6_desc: "Module bảo vệ Native C++ (meg_license_bridge.dll) gắn chặt với mã máy cứng HWID, chống giả mạo, mã hóa an toàn 100%.",

        // Guide Section
        guide_badge: "DỄ DÀNG VẬN HÀNH",
        guide_title: "Hướng Dẫn Chạy Chương Trình Trong 4 Bước",
        guide_desc: "Thao tác trực tiếp trên giao diện Dashboard, không đòi hỏi kiến thức IT.",
        step1_badge: "Chuẩn bị",
        step1_title: "Xin File Cài & Key Dùng Thử",
        step1_desc: "Nhắn tin Zalo / Telegram hoặc gọi Hotline 036.203.1354 để nhận file cài đặt và kích hoạt mã dùng thử miễn phí. Hỗ trợ gửi file và cài Ultraview trong 2 phút.",
        step1_btn: "Nhắn tin xin file",
        step2_badge: "Vào Game",
        step2_title: "Mở Game MEGAMU",
        step2_desc: "Khởi động MEGAMU Launcher và đăng nhập các tài khoản game của bạn vào thế giới MEGAMU trước khi bật Auto.",
        step3_badge: "Quyền Admin",
        step3_title: "Chạy Quyền Admin",
        step3_desc: "Nhấp chuột phải chọn Run as Administrator vào file MEGAMU Auto Train Dashboard.exe để cấp quyền kết nối ngầm.",
        step4_badge: "Vận hành",
        step4_title: "Kích Hoạt & Bật Auto",
        step4_desc: "Bấm nút \"Kích Hoạt\" nhập License Key được cấp, sau đó bấm \"Làm mới Game\" hoặc \"Kết nối tất cả\" để bắt đầu train!",
        guide_tip_title: "Mẹo thiết lập bãi train:",
        guide_tip_body: "Vào tab \"Cấu hình\" trên Dashboard để chỉnh sửa bãi train theo ý muốn. Bạn có thể chọn map (Lorencia, Devias, Dungeon, Lost Tower, Arena...) và điền trực tiếp tọa độ X, Y bãi quái để nhân vật tự động tìm đến và cắm cọc 24/24.",

        // Pricing Section
        pricing_badge: "BẢNG GIÁ THAM KHẢO & DÙNG THỬ",
        pricing_title: "Báo Giá Tham Khảo & Đăng Ký Dùng Thử",
        pricing_desc: "Bảng giá tham khảo các gói dịch vụ. Quý khách vui lòng liên hệ trực tiếp qua Zalo hoặc Hotline để nhận file cài đặt và kích hoạt dùng thử miễn phí.",
        p1_badge: "TEST NHANH",
        p1_sub: "Trải Nghiệm",
        p1_title: "Gói Ngày",
        p1_desc: "Thử nghiệm đầy đủ tính năng trước khi quyết định mua dài hạn.",
        p1_price: "15.000",
        p1_unit: "VNĐ / Ngày",
        p1_subtext: "Kích hoạt nhanh chóng qua Zalo / Telegram",
        p1_f1: "Thời hạn: 24 Giờ (1 Ngày)",
        p1_f2: "Đầy đủ tính năng Auto Train",
        p1_f3: "Zero-Mouse không chiếm chuột",
        p1_f4: "Hỗ trợ tối đa 3 tài khoản/máy",
        p1_f5: "Không hỗ trợ đổi máy (Reset HWID)",
        p1_btn: "Liên Hệ Dùng Thử Gói Ngày",

        p2_badge: "⭐ PHỔ BIẾN NHẤT",
        p2_sub: "Đua Top & Cày Cuốc",
        p2_title: "Gói Tháng",
        p2_desc: "Lựa chọn tối ưu nhất cho game thủ cày level và gom ngọc dài ngày.",
        p2_price: "120.000",
        p2_unit: "VNĐ / 30 Ngày",
        p2_subtext: "Chỉ 4.000đ / ngày (Tiết kiệm 75%)",
        p2_f1: "Thời hạn: 30 Ngày liên tục",
        p2_f2: "Full tính năng: Auto Warp, Loot, Skill",
        p2_f3: "Hỗ trợ Multi-Client 10 Acc cùng lúc",
        p2_f4: "Cập nhật update miễn phí liên tục",
        p2_f5: "Hỗ trợ đổi máy: 1 lần / tháng",
        p2_btn: "Liên Hệ Dùng Thử Gói Tháng",

        p3_badge: "🔥 TIẾT KIỆM 20%",
        p3_sub: "Tiết Kiệm Cao",
        p3_title: "Gói Quý (3T)",
        p3_desc: "Thảnh thơi cày game trọn vẹn cả mùa Season mà không lo gia hạn.",
        p3_price: "300.000",
        p3_unit: "VNĐ / 90 Ngày",
        p3_subtext: "Chỉ 100.000đ / tháng (Tiết kiệm thêm 20%)",
        p3_f1: "Thời hạn: 90 Ngày (3 Tháng)",
        p3_f2: "Multi-Client 15 Acc cùng lúc",
        p3_f3: "Tặng kèm danh sách tọa độ bãi train VIP",
        p3_f4: "Hỗ trợ Ultraview cài đặt từ A - Z",
        p3_f5: "Hỗ trợ đổi máy: 3 lần / kỳ",
        p3_btn: "Liên Hệ Dùng Thử Gói Quý",

        p4_badge: "👑 LIFETIME VIP",
        p4_sub: "Trọn Đời Mãi Mãi",
        p4_title: "Gói Vĩnh Viễn",
        p4_desc: "Thanh toán 1 lần duy nhất, dùng trọn đời mọi bản cập nhật.",
        p4_price: "799.000",
        p4_unit: "VNĐ",
        p4_subtext: "Bản quyền vĩnh viễn không giới hạn",
        p4_f1: "Thời hạn: VĨNH VIỄN (TRỌN ĐỜI)",
        p4_f2: "Không giới hạn số Acc Multi-Client (50 Slots)",
        p4_f3: "Cập nhật miễn phí mọi season mới",
        p4_f4: "Reset đổi máy không giới hạn số lần",
        p4_f5: "Vào Group Telegram VIP hỗ trợ riêng 24/7",
        p4_btn: "Liên Hệ Tư Vấn & Dùng Thử",

        // FAQ Section
        faq_badge: "GIẢI ĐÁP THẮC MẮC",
        faq_title: "Câu Hỏi Thường Gặp (FAQ)",
        faq_desc: "Tất cả những điều bạn cần biết trước khi bắt đầu sử dụng DAuto MEGAMU.",
        faq1_q: "1. Sử dụng DAuto MEGAMU có bị khóa tài khoản game không?",
        faq1_a: "DAuto sử dụng cơ chế Native Hook trực tiếp và mô phỏng hành vi di chuyển tự nhiên của nhân vật, không can thiệp thay đổi file hệ thống của server. Bạn hoàn toàn an tâm khi cày cuốc, đua top và săn ngọc hàng ngày.",
        faq2_q: "2. Tính năng \"Zero-Mouse Không Chiếm Chuột\" hoạt động như thế nào?",
        faq2_a: "Khác với các phần mềm auto thông thường bắt chuột và click giả lập trên màn hình, DAuto gửi trực tiếp các lệnh di chuyển, xuất skill và nhặt đồ qua bộ nhớ ngầm. Bạn có thể thu nhỏ cửa sổ game xuống thanh taskbar, vừa auto vừa làm việc, đánh Word, Excel hoặc lướt web mà không bị gián đoạn.",
        faq3_q: "3. Khi tôi đổi máy tính hoặc cài lại Windows thì License Key có dùng tiếp được không?",
        faq3_a: "Hoàn toàn được! Đối với gói Tháng, Quý và Vĩnh Viễn, hệ thống hỗ trợ reset mã phần cứng (HWID) nhanh chóng. Bạn chỉ cần nhắn tin cho admin kèm mã License Key để được cấp quyền mở khóa sang máy tính mới ngay lập tức.",
        faq4_q: "4. Làm sao để tôi nhận được file cài đặt và mã kích hoạt dùng thử?",
        faq4_a: "Rất đơn giản! Bạn chỉ cần liên hệ trực tiếp qua Zalo, Telegram hoặc Hotline 036.203.1354. Đội ngũ MEGATEAM sẽ gửi ngay file cài đặt mới nhất kèm mã bản quyền trải nghiệm dùng thử miễn phí và hỗ trợ cấu hình Ultraview nếu cần.",

        // Contact Section
        contact_banner_title: "Bạn Cần Tư Vấn Hoặc Cài Đặt Thử Nghiệm?",
        contact_banner_desc: "Đội ngũ hỗ trợ kỹ thuật của chúng tôi luôn trực tuyến 24/7 để hỗ trợ bạn cài đặt qua Ultraview, giải đáp thắc mắc và cấp mã bản quyền ngay lập tức.",
        contact_btn_telegram: "Telegram Hỗ Trợ",
        contact_btn_whatsapp: "WhatsApp Hỗ Trợ",

        // Footer
        footer_desc: "Giải pháp tự động hóa hàng đầu cho cộng đồng MEGAMU.",
        footer_rights: "Bảo lưu mọi quyền.",

        // Modal
        modal_title: "Đăng Ký Trải Nghiệm & Dùng Thử",
        modal_subtitle: "Liên hệ nhận file cài đặt & kích hoạt key dùng thử DAuto MEGAMU",
        modal_plan_label: "Gói quan tâm:",
        modal_price_label: "Giá tham khảo:",
        modal_box_title: "Cấp Key Dùng Thử & Hỗ Trợ Cài Đặt Trực Tiếp",
        modal_box_desc: "Để nhận file cài đặt và kích hoạt mã dùng thử trải nghiệm gói này, quý khách vui lòng liên hệ trực tiếp qua Zalo hoặc Hotline. Đội ngũ MEGATEAM sẽ gửi file và hỗ trợ bạn cài đặt qua Ultraview nhanh chóng trong 2 phút.",
        modal_hotline_label: "Hotline / Zalo hỗ trợ:",
        modal_instruction: "Bấm vào nút bên dưới để nhắn tin Zalo hoặc gọi Hotline nhận file cài đặt ngay:",
        modal_btn_zalo: "Nhắn Zalo Nhận Bản Dùng Thử",
        modal_btn_call: "Gọi 036.203.1354",
        modal_btn_close: "Đóng"
    },

    en: {
        page_title: "DAuto MEGAMU - Elite Auto Train Dashboard System",
        meta_desc: "DAuto MEGAMU Auto Train Dashboard - Intelligent pathfinding, move to spots by X, Y coords, mob pulling, skill combos, auto pick jewels, revive back to spot, ultra-smooth Multi-Client support.",
        
        // Navigation
        nav_showcase: "Live Showcase",
        nav_features: "Features",
        nav_guide: "Quick Guide",
        nav_pricing: "Pricing",
        nav_faq: "FAQ",
        nav_contact: "Contact",
        nav_trial_btn: "Free Trial",
        nav_subtitle: "Auto Train Dashboard • v1.5.2",

        // Hero Section
        hero_badge: "OFFICIAL SOFTWARE • MEGAMU AUTO TRAIN DASHBOARD V1.5.2 RELEASE",
        hero_title_1: "Elite Auto Train System For ",
        hero_desc_1: "Professional control dashboard managing 10 to 50 game accounts simultaneously. Auto connect, intelligent spot pathfinding, auto loot, and accurate spot revival. ",
        hero_desc_2: "Zero-Mouse Hook technology leaves your mouse and keyboard 100% free!",
        hero_btn_pricing: "Pricing & Free Trial",
        hero_btn_installer: "Request Setup Files",
        hero_btn_showcase: "View Live Screenshots",
        hero_support_note: "• 24/7 Remote setup support (Ultraviewer / AnyDesk)",
        hero_stat_slots: "Multi-Account Slots",
        hero_stat_mouse: "Mouse & Key Capture",
        hero_stat_bridge: "Native C++ Bridge",
        hero_stat_auto: "Full 24/7 Automation",
        hero_mockup_title: "MEGAMU Auto Train Dashboard - 10 Account Slots Management Screen",
        hero_mockup_badge: "Live screenshot from actual app",

        // Showcase Section
        showcase_badge: "LIVE EXPERIENCE",
        showcase_title: "Actual Software User Interface",
        showcase_desc: "Explore actual working screens in the application: 10 Account Management, Spot & Coordinate Configuration, and Live System Logs.",
        tab_accounts_btn: "1. Account Slot Manager",
        tab_config_btn: "2. Spot & Coordinate Config",
        tab_game_btn: "3. In-Game In Action",
        tab_accounts_title: "Tab 1: Automated 10-Slot Multi-Account Manager",
        tab_accounts_desc: "Auto scans game PIDs, bulk connects, assigns 5-character party teams, selects Config 1..10 routes, and monitors realtime slot status.",
        tab_accounts_tag: "Zero-Mouse Mode Active",
        tab_config_title: "Tab 2: Level-Based Route Setup (Min/Max Level)",
        tab_config_desc: "Configure automated map travel (Lorencia, Dungeon, Lost Tower, Arena...), enter spot X, Y coordinates, and post-PK respawn delays.",
        tab_config_tag: "Auto-Saves to JSON",
        tab_game_title: "Tab 3: Item Farming & Jewel Gathering in MEGAMU",
        tab_game_desc: "Supports hunting Excellent items, Blood Angel gear, auto looting Soul, Bless, Chaos jewels and accumulating Zen 24/7 nonstop.",
        tab_game_tag: "Smart Loot Filter",

        // Features Section
        feat_badge: "OUTSTANDING FEATURES",
        feat_title: "Advanced Automation Technology",
        feat_desc: "Engineered down to the microsecond so your characters dominate level rankings, resets, and jewel farming.",
        f1_title: "Warp Surface & Spot Coordinates",
        f1_desc: "Automatically moves to train spots using pinpoint X, Y coordinates. Smart pathfinding evades obstacles and returns right to your spot after dying or reviving.",
        f2_title: "Zero-Mouse Direct Engine",
        f2_desc: "Direct control via Frida Native Bridge. Computer mouse is 100% free; you can comfortably work, watch movies, or play other games.",
        f3_title: "Smart Loot Filter (Auto Pick)",
        f3_desc: "Auto loots jewels (Bless, Soul, Chaos, Life, Creation...), Excellent gear (Exl), Ancient items, and Zen. Skips junk items so inventory stays clean.",
        f4_title: "Skill Combos & Auto Potion",
        f4_desc: "Supports all classes (DK, DW, Elf, MG, DL, Summoner, RF, GL...). Customize monster attack rotations, auto buffs, and auto potions when HP/MP falls low.",
        f5_title: "Multi-Client Multi-Account Manager",
        f5_desc: "Manage 10 to 50 game windows on a single monitor. Displays realtime stats, level, coordinates, and alive/dead status for every character.",
        f6_title: "C++ Native Bridge Security",
        f6_desc: "Native C++ protection module (meg_license_bridge.dll) strictly bound to hardware HWID, tamper-resistant, and 100% secure.",

        // Guide Section
        guide_badge: "EASY OPERATION",
        guide_title: "Run The Software In 4 Simple Steps",
        guide_desc: "Straightforward controls on the dashboard, zero IT background required.",
        step1_badge: "Preparation",
        step1_title: "Get Setup File & Free Trial Key",
        step1_desc: "Contact via WhatsApp / Telegram or Hotline to receive installation files and your free trial license key. Fast remote setup assistance within 2 minutes.",
        step1_btn: "Message for files",
        step2_badge: "Launch Game",
        step2_title: "Launch MEGAMU Game",
        step2_desc: "Start the MEGAMU Launcher and log your game accounts into the MEGAMU world before starting the Auto.",
        step3_badge: "Admin Privilege",
        step3_title: "Run As Administrator",
        step3_desc: "Right-click and select Run as Administrator on MEGAMU Auto Train Dashboard.exe to grant background hook permissions.",
        step4_badge: "Operation",
        step4_title: "Activate & Start Auto",
        step4_desc: "Click \"Activate\" to paste your License Key, then click \"Refresh Games\" or \"Connect All\" to start training!",
        guide_tip_title: "Spot Setup Pro Tip:",
        guide_tip_body: "Open the \"Profiles\" tab on the Dashboard to configure custom train spots. Select any map (Lorencia, Devias, Dungeon, Lost Tower, Arena...) and enter exact X, Y spot coordinates for automated 24/7 farming.",

        // Pricing Section
        pricing_badge: "PRICING & FREE TRIAL",
        pricing_title: "Pricing Reference & Free Trial",
        pricing_desc: "Pricing reference for service packages. Please contact us directly to receive installer files and free trial license key.",
        p1_badge: "QUICK TRIAL",
        p1_sub: "Experience",
        p1_title: "Daily Plan",
        p1_desc: "Full features preview before committing to longer term plans.",
        p1_price: "15,000",
        p1_unit: "VND / Day (~$0.60 USD)",
        p1_subtext: "Instant activation via WhatsApp / Telegram",
        p1_f1: "Duration: 24 Hours (1 Day)",
        p1_f2: "Full Auto Train features enabled",
        p1_f3: "Zero-Mouse keeps mouse free",
        p1_f4: "Supports up to 3 accounts/PC",
        p1_f5: "Hardware reset (HWID) not supported",
        p1_btn: "Contact for Daily Trial",

        p2_badge: "⭐ MOST POPULAR",
        p2_sub: "Rank Racing & Grinding",
        p2_title: "Monthly Plan",
        p2_desc: "The optimal choice for leveling, resetting, and continuous jewel farming.",
        p2_price: "120,000",
        p2_unit: "VND / 30 Days (~$4.80 USD)",
        p2_subtext: "Only 4,000 VND / day (Save 75%)",
        p2_f1: "Duration: 30 Days continuous",
        p2_f2: "Full features: Auto Warp, Loot, Skill",
        p2_f3: "Supports Multi-Client 10 Accs",
        p2_f4: "Free continuous updates included",
        p2_f5: "PC change support: 1 time / month",
        p2_btn: "Contact for Monthly Trial",

        p3_badge: "🔥 SAVE 20%",
        p3_sub: "High Savings",
        p3_title: "Quarterly Plan (3M)",
        p3_desc: "Play relaxed throughout entire seasons without worrying about renewals.",
        p3_price: "300,000",
        p3_unit: "VND / 90 Days (~$12.00 USD)",
        p3_subtext: "Only 100,000 VND / month (Extra 20% off)",
        p3_f1: "Duration: 90 Days (3 Months)",
        p3_f2: "Multi-Client 15 Accounts simultaneously",
        p3_f3: "Includes curated VIP spot coordinates list",
        p3_f4: "Full remote setup support from A to Z",
        p3_f5: "PC change support: 3 times / period",
        p3_btn: "Contact for Quarterly Trial",

        p4_badge: "👑 LIFETIME VIP",
        p4_sub: "Lifetime VIP Access",
        p4_title: "Lifetime Plan",
        p4_desc: "Pay once, enjoy permanent access across all future updates.",
        p4_price: "799,000",
        p4_unit: "VND (~$32.00 USD)",
        p4_subtext: "Unlimited lifetime license",
        p4_f1: "Duration: LIFETIME (PERMANENT)",
        p4_f2: "Unlimited Multi-Client accounts (up to 50 slots)",
        p4_f3: "Free upgrades for all new game seasons",
        p4_f4: "Unlimited PC change / HWID resets",
        p4_f5: "Private VIP Telegram support group 24/7",
        p4_btn: "Contact for Lifetime VIP",

        // FAQ Section
        faq_badge: "FREQUENT QUESTIONS",
        faq_title: "Frequently Asked Questions (FAQ)",
        faq_desc: "Everything you need to know before getting started with DAuto MEGAMU.",
        faq1_q: "1. Is there a ban risk when using DAuto MEGAMU?",
        faq1_a: "DAuto employs direct native hooks and simulates natural character movements without altering server files. You can safely grind levels, race ranks, and hunt jewels every single day with peace of mind.",
        faq2_q: "2. How does \"Zero-Mouse Direct Engine\" work?",
        faq2_a: "Unlike traditional bots that hijack your cursor and simulate screen clicks, DAuto transmits movement, skill execution, and looting directly through background memory. You can minimize game windows to the taskbar and continue working, typing, or browsing uninterrupted.",
        faq3_q: "3. Can I keep using my License Key if I change PC or reinstall Windows?",
        faq3_a: "Absolutely! For Monthly, Quarterly, and Lifetime plans, our system supports swift hardware ID (HWID) resets. Just message the admin with your License Key to immediately transfer your license to your new machine.",
        faq4_q: "4. How do I get the installation files and free trial license key?",
        faq4_a: "Very simple! Just reach out directly via Telegram, WhatsApp, or Zalo. The MEGATEAM crew will promptly send the latest build along with a free trial key, plus remote assistance if needed.",

        // Contact Section
        contact_banner_title: "Need Consultation or Free Trial Setup?",
        contact_banner_desc: "Our technical team is available 24/7 to provide remote setup via Ultraviewer / AnyDesk, answer questions, and provide license keys instantly.",
        contact_btn_telegram: "Telegram Support",
        contact_btn_whatsapp: "WhatsApp Support",

        // Footer
        footer_desc: "Leading automation solution for the MEGAMU gaming community.",
        footer_rights: "All Rights Reserved.",

        // Modal
        modal_title: "Register For Trial & Consultation",
        modal_subtitle: "Contact us to receive setup files & trial key for DAuto MEGAMU",
        modal_plan_label: "Selected Plan:",
        modal_price_label: "Reference Price:",
        modal_box_title: "Free Trial Key & Direct Setup Support",
        modal_box_desc: "To receive setup files and activate your free trial for this plan, please contact us directly via WhatsApp, Telegram, or Hotline. Our team will send files and assist with remote setup in 2 minutes.",
        modal_hotline_label: "Online Support Channels:",
        modal_instruction: "Click the buttons below to request your setup files immediately:",
        modal_btn_zalo: "Contact via Zalo / WhatsApp",
        modal_btn_call: "Call Support (+84 362.031.354)",
        modal_btn_close: "Close"
    },

    es: {
        page_title: "DAuto MEGAMU - Sistema Dashboard Auto Train Definitivo",
        meta_desc: "DAuto MEGAMU Auto Train Dashboard - Navegación inteligente, movimiento a spots por coordenadas X, Y, combo de skills, auto loot de joyas, revivir al spot y soporte Multi-Client fluido.",
        
        // Navigation
        nav_showcase: "Capturas Reales",
        nav_features: "Características",
        nav_guide: "Guía Rápida",
        nav_pricing: "Precios",
        nav_faq: "Preguntas",
        nav_contact: "Contacto",
        nav_trial_btn: "Probar Gratis",
        nav_subtitle: "Auto Train Dashboard • v1.5.2",

        // Hero Section
        hero_badge: "SOFTWARE OFICIAL • MEGAMU AUTO TRAIN DASHBOARD V1.5.2 LANZAMIENTO",
        hero_title_1: "El Mejor Sistema Auto Train Para ",
        hero_desc_1: "Dashboard profesional que gestiona de 10 a 50 cuentas simultáneas. Conexión automática, navegación inteligente a spots, auto loot y revivir en spot con precisión. ",
        hero_desc_2: "¡Tecnología Zero-Mouse Hook sin capturar ratón ni teclado!",
        hero_btn_pricing: "Precios y Prueba Gratis",
        hero_btn_installer: "Pedir Instalador y Prueba",
        hero_btn_showcase: "Ver Capturas Reales",
        hero_support_note: "• Soporte de instalación remota 24/7 (Ultraviewer / AnyDesk)",
        hero_stat_slots: "Slots Multi-Cuentas",
        hero_stat_mouse: "Captura de Ratón y Teclas",
        hero_stat_bridge: "Native C++ Bridge",
        hero_stat_auto: "Automatización Total 24/7",
        hero_mockup_title: "MEGAMU Auto Train Dashboard - Pantalla de Gestión de 10 Slots de Cuentas",
        hero_mockup_badge: "Captura real de la aplicación",

        // Showcase Section
        showcase_badge: "EXPERIENCIA REAL",
        showcase_title: "Interfaz Real del Software",
        showcase_desc: "Explora las pantallas de trabajo reales en la aplicación: Gestión de 10 cuentas, Configuración de spots y coordenadas, y Registro de actividad.",
        tab_accounts_btn: "1. Administrador de Slots",
        tab_config_btn: "2. Configuración de Spots",
        tab_game_btn: "3. En Juego en Directo",
        tab_accounts_title: "Tab 1: Gestor Automático de 10 Slots de Cuentas",
        tab_accounts_desc: "Escanea PIDs del juego, conecta en masa, asigna party de 5 pjs, elige rutas Config 1..10 y monitorea el estado en tiempo real.",
        tab_accounts_tag: "Modo Zero-Mouse Activo",
        tab_config_title: "Tab 2: Configuración de Rutas por Nivel (Min/Max Level)",
        tab_config_desc: "Configura cambio de mapas automático (Lorencia, Dungeon, Lost Tower, Arena...), ingresa coordenadas X, Y del spot y espera tras PK.",
        tab_config_tag: "Auto-Guardado en JSON",
        tab_game_title: "Tab 3: Farmeo de Items y Joyas en MEGAMU",
        tab_game_desc: "Soporta farmeo de items Excelentes, equipo Blood Angel, auto loot de Soul, Bless, Chaos y acumulación de Zen 24/7.",
        tab_game_tag: "Filtro de Loot Inteligente",

        // Features Section
        feat_badge: "CARACTERÍSTICAS DESTACADAS",
        feat_title: "Tecnología Avanzada de Automatización",
        feat_desc: "Diseñado al microsegundo para que tus personajes lideren en nivel, resets y farmeo de joyas.",
        f1_title: "Warp Surface y Coordenadas Precisas",
        f1_desc: "Se mueve automáticamente al spot de train por coordenadas X, Y exactas. Ruta inteligente esquivando obstáculos y regreso automático al spot tras morir o revivir.",
        f2_title: "Zero-Mouse Direct Engine",
        f2_desc: "Control directo a través de Frida Native Bridge. El ratón de tu PC queda 100% libre; puedes trabajar, ver películas o jugar otros juegos tranquilamente.",
        f3_title: "Filtro de Loot Inteligente (Auto Pick)",
        f3_desc: "Recoge automáticamente joyas (Bless, Soul, Chaos, Life, Creation...), equipo Excelente (Exl), items Ancient y Zen. Descarta basura para evitar llenar el inventario.",
        f4_title: "Combo de Skills y Auto Pociones",
        f4_desc: "Compatible con todas las clases (DK, DW, Elf, MG, DL, Summoner, RF, GL...). Personaliza rotaciones de skill, auto buff y uso automático de pociones HP/MP.",
        f5_title: "Gestión Multi-Client Multi-Cuentas",
        f5_desc: "Gestiona de 10 a 50 ventanas de juego simultáneamente. Muestra estadísticas en tiempo real, nivel, coordenadas y estado vivo/muerto de cada pj.",
        f6_title: "Seguridad C++ Native Bridge",
        f6_desc: "Módulo nativo C++ (meg_license_bridge.dll) vinculado al HWID del hardware, resistente a manipulaciones y 100% seguro.",

        // Guide Section
        guide_badge: "FÁCIL OPERACIÓN",
        guide_title: "Ejecuta El Programa En 4 Sencillos Pasos",
        guide_desc: "Operación directa en el Dashboard, sin requerir conocimientos técnicos.",
        step1_badge: "Preparación",
        step1_title: "Obtén Instalador y Key de Prueba",
        step1_desc: "Escríbenos por WhatsApp / Telegram / Zalo para recibir los archivos del instalador y activar tu clave de prueba gratuita. Instalación remota en 2 minutos.",
        step1_btn: "Pedir instalador",
        step2_badge: "Iniciar Juego",
        step2_title: "Abrir Juego MEGAMU",
        step2_desc: "Inicia el Launcher de MEGAMU e inicia sesión con tus cuentas en el juego antes de iniciar el Auto.",
        step3_badge: "Permiso Admin",
        step3_title: "Ejecutar Como Administrador",
        step3_desc: "Haz clic derecho y selecciona Ejecutar como Administrador en MEGAMU Auto Train Dashboard.exe para otorgar permisos.",
        step4_badge: "Operación",
        step4_title: "Activar e Iniciar Auto",
        step4_desc: "Haz clic en \"Activar\", pega tu clave de licencia y pulsa \"Refrescar Juego\" o \"Conectar Todos\" para comenzar.",
        guide_tip_title: "Consejo para spots de train:",
        guide_tip_body: "Ve a la pestaña \"Configuración\" en el Dashboard para personalizar tus spots de train. Elige mapa (Lorencia, Devias, Dungeon, Lost Tower, Arena...) e ingresa coordenadas X, Y para farmear 24/7.",

        // Pricing Section
        pricing_badge: "LISTA DE PRECIOS Y PRUEBA",
        pricing_title: "Precios de Referencia y Registro",
        pricing_desc: "Precios de referencia de planes. Contáctanos directamente para recibir el instalador y activar tu prueba gratuita.",
        p1_badge: "PRUEBA RÁPIDA",
        p1_sub: "Experiencia",
        p1_title: "Plan Diario",
        p1_desc: "Prueba todas las funciones antes de optar por planes a largo plazo.",
        p1_price: "15.000",
        p1_unit: "VND / Día (~$0.60 USD)",
        p1_subtext: "Activación rápida por WhatsApp / Telegram",
        p1_f1: "Duración: 24 Horas (1 Día)",
        p1_f2: "Todas las funciones de Auto Train",
        p1_f3: "Zero-Mouse sin capturar ratón",
        p1_f4: "Hasta 3 cuentas simultáneas",
        p1_f5: "Sin soporte para cambio de PC (HWID)",
        p1_btn: "Probar Plan Diario",

        p2_badge: "⭐ MÁS POPULAR",
        p2_sub: "Carrera de Nivel y Farmeo",
        p2_title: "Plan Mensual",
        p2_desc: "La opción ideal para subir nivel, hacer resets y juntar joyas de forma continua.",
        p2_price: "120.000",
        p2_unit: "VND / 30 Días (~$4.80 USD)",
        p2_subtext: "Solo 4.000 VND / día (Ahorra 75%)",
        p2_f1: "Duración: 30 Días continuos",
        p2_f2: "Full funciones: Auto Warp, Loot, Skill",
        p2_f3: "Soporte para 10 Cuentas a la vez",
        p2_f4: "Actualizaciones gratuitas continuas",
        p2_f5: "Cambio de PC: 1 vez / mes",
        p2_btn: "Probar Plan Mensual",

        p3_badge: "🔥 AHORRA 20%",
        p3_sub: "Gran Ahorro",
        p3_title: "Plan Trimestral (3M)",
        p3_desc: "Juega toda la temporada despreocupado por renovaciones.",
        p3_price: "300.000",
        p3_unit: "VND / 90 Días (~$12.00 USD)",
        p3_subtext: "Solo 100.000 VND / mes (20% ahorro extra)",
        p3_f1: "Duración: 90 Días (3 Meses)",
        p3_f2: "Multi-Client 15 cuentas a la vez",
        p3_f3: "Incluye lista de coordenadas VIP de spots",
        p3_f4: "Soporte de instalación completo A a Z",
        p3_f5: "Cambio de PC: 3 veces / periodo",
        p3_btn: "Probar Plan Trimestral",

        p4_badge: "👑 LIFETIME VIP",
        p4_sub: "Acceso Vitalicio",
        p4_title: "Plan Vitalicio",
        p4_desc: "Un único pago para disfrutar de por vida todas las actualizaciones.",
        p4_price: "799.000",
        p4_unit: "VND (~$32.00 USD)",
        p4_subtext: "Licencia vitalicia sin límites",
        p4_f1: "Duración: VITALICIA (DE POR VIDA)",
        p4_f2: "Sin límite de cuentas Multi-Client (50 slots)",
        p4_f3: "Actualizaciones gratis para nuevas seasons",
        p4_f4: "Cambios de PC ilimitados (Reset HWID)",
        p4_f5: "Grupo VIP de Telegram con soporte 24/7",
        p4_btn: "Consultar Plan Vitalicio",

        // FAQ Section
        faq_badge: "PREGUNTAS FRECUENTES",
        faq_title: "Preguntas Frecuentes (FAQ)",
        faq_desc: "Todo lo que necesitas saber antes de empezar con DAuto MEGAMU.",
        faq1_q: "1. ¿Existe riesgo de baneo usando DAuto MEGAMU?",
        faq1_a: "DAuto utiliza hooks nativos simulando movimientos naturales de personajes sin modificar archivos del servidor. Puedes farmear, subir nivel y buscar joyas con total tranquilidad.",
        faq2_q: "2. ¿Cómo funciona la tecnología \"Zero-Mouse\" sin capturar ratón?",
        faq2_a: "A diferencia de bots convencionales que controlan tu cursor en pantalla, DAuto envía comandos de movimiento, skills y loot directo en memoria de fondo. Puedes minimizar el juego y seguir trabajando o navegando sin interrupciones.",
        faq3_q: "3. ¿Puedo seguir usando mi clave si cambio de PC o reinstalo Windows?",
        faq3_a: "¡Por supuesto! Para planes Mensual, Trimestral y Vitalicio, el sistema permite resetear tu HWID rápidamente. Solo envía un mensaje al soporte con tu clave para desbloquearla en tu nueva PC.",
        faq4_q: "4. ¿Cómo obtengo los archivos de instalación y la clave de prueba?",
        faq4_a: "¡Muy fácil! Contáctanos directamente vía WhatsApp, Telegram o Zalo. Nuestro equipo te enviará la versión más reciente con una key de prueba y asistencia remota si la necesitas.",

        // Contact Section
        contact_banner_title: "¿Necesitas Asesoría o Configuración de Prueba?",
        contact_banner_desc: "Nuestro equipo de soporte técnico está disponible 24/7 para asistirte con instalación remota, resolver dudas y activar licencias de inmediato.",
        contact_btn_telegram: "Soporte Telegram",
        contact_btn_whatsapp: "Soporte WhatsApp",

        // Footer
        footer_desc: "La solución líder de automatización para la comunidad de MEGAMU.",
        footer_rights: "Todos los derechos reservados.",

        // Modal
        modal_title: "Registro para Prueba y Consulta",
        modal_subtitle: "Contáctanos para recibir el instalador y la key de prueba de DAuto MEGAMU",
        modal_plan_label: "Plan seleccionado:",
        modal_price_label: "Precio de referencia:",
        modal_box_title: "Key de Prueba Gratuita y Soporte Directo",
        modal_box_desc: "Para recibir el instalador y activar tu key de prueba, contáctanos directamente por WhatsApp, Telegram o Zalo. Te enviaremos los archivos y te asistiremos remotamente en 2 minutos.",
        modal_hotline_label: "Canales de soporte directo:",
        modal_instruction: "Haz clic en los botones siguientes para solicitar los archivos:",
        modal_btn_zalo: "Contactar por WhatsApp / Zalo",
        modal_btn_call: "Llamar al Soporte (+84 362.031.354)",
        modal_btn_close: "Cerrar"
    },

    pt: {
        page_title: "DAuto MEGAMU - Sistema Definitivo de Auto Train Dashboard",
        meta_desc: "DAuto MEGAMU Auto Train Dashboard - Navegação inteligente, movimentação para spots por coordenadas X, Y, combo de skills, auto loot de joias, reviver no spot e suporte Multi-Client super fluido.",
        
        // Navigation
        nav_showcase: "Fotos Reais",
        nav_features: "Recursos",
        nav_guide: "Guia Rápido",
        nav_pricing: "Preços",
        nav_faq: "FAQ",
        nav_contact: "Contato",
        nav_trial_btn: "Teste Grátis",
        nav_subtitle: "Auto Train Dashboard • v1.5.2",

        // Hero Section
        hero_badge: "SOFTWARE OFICIAL • MEGAMU AUTO TRAIN DASHBOARD V1.5.2 LANÇAMENTO",
        hero_title_1: "O Melhor Sistema de Auto Train Para ",
        hero_desc_1: "Dashboard profissional para gerenciar de 10 a 50 contas simultâneas. Conexão automática, navegação inteligente para spots, auto loot e retorno preciso ao spot após morrer. ",
        hero_desc_2: "Tecnologia Zero-Mouse Hook que não ocupa mouse nem teclado!",
        hero_btn_pricing: "Preços e Teste Grátis",
        hero_btn_installer: "Pedir Instalador e Teste",
        hero_btn_showcase: "Ver Telas Reais",
        hero_support_note: "• Suporte de instalação remota 24/7 (Ultraviewer / AnyDesk)",
        hero_stat_slots: "Slots Multi-Contas",
        hero_stat_mouse: "Uso de Mouse e Teclado",
        hero_stat_bridge: "Native C++ Bridge",
        hero_stat_auto: "Automação Total 24/7",
        hero_mockup_title: "MEGAMU Auto Train Dashboard - Tela de Gerenciamento de 10 Slots de Contas",
        hero_mockup_badge: "Captura real do aplicativo",

        // Showcase Section
        showcase_badge: "EXPERIÊNCIA REAL",
        showcase_title: "Interface Real do Software",
        showcase_desc: "Veja as telas reais do aplicativo: Gerenciamento de 10 contas, Configuração de spots e coordenadas, e Registro de atividades.",
        tab_accounts_btn: "1. Gerenciador de Slots",
        tab_config_btn: "2. Configuração de Spots",
        tab_game_btn: "3. Em Jogo em Ação",
        tab_accounts_title: "Tab 1: Gerenciador Automático de 10 Slots de Contas",
        tab_accounts_desc: "Varre PIDs do jogo, conecta em massa, define party de 5 bonecos, escolhe rotas Config 1..10 e monitora status em tempo real.",
        tab_accounts_tag: "Modo Zero-Mouse Ativo",
        tab_config_title: "Tab 2: Configuração de Rotas por Nível (Min/Max Level)",
        tab_config_desc: "Configure troca automática de mapas (Lorencia, Dungeon, Lost Tower, Arena...), defina coordenadas X, Y do spot e delay pós-PK.",
        tab_config_tag: "Auto-Save em JSON",
        tab_game_title: "Tab 3: Farme de Itens e Coleta de Joias no MEGAMU",
        tab_game_desc: "Suporte a caça de itens Excelentes, set Blood Angel, auto loot de Soul, Bless, Chaos e acúmulo contínuo de Zen 24/7.",
        tab_game_tag: "Filtro de Loot Inteligente",

        // Features Section
        feat_badge: "RECURSOS DE DESTAQUE",
        feat_title: "Tecnologia Avançada de Automação",
        feat_desc: "Projetado ao microssegundo para seus personagens dominarem o ranking de nível, resets e farme de joias.",
        f1_title: "Warp Surface e Coordenadas Precisas",
        f1_desc: "Move-se automaticamente para o spot de train por coordenadas X, Y exatas. Desvio inteligente de obstáculos e retorno automático ao spot após morrer ou renascer.",
        f2_title: "Zero-Mouse Direct Engine",
        f2_desc: "Controle direto através da Frida Native Bridge. O mouse do PC fica 100% livre; trabalhe, assista a filmes ou jogue outros jogos com tranquilidade.",
        f3_title: "Filtro de Loot Inteligente (Auto Coleta)",
        f3_desc: "Coleta automaticamente joias (Bless, Soul, Chaos, Life, Creation...), equipamentos Excelentes (Exl), itens Ancient e Zen. Ignora lixo para manter o inventário limpo.",
        f4_title: "Combo de Skills e Auto Poções",
        f4_desc: "Compatível com todas as classes (DK, DW, Elf, MG, DL, Summoner, RF, GL...). Rotações de ataque customizadas, auto buff e auto poção de vida/mana quando necessário.",
        f5_title: "Gerenciador Multi-Client Multi-Contas",
        f5_desc: "Gerencie de 10 a 50 janelas do jogo em uma única tela. Exibe métricas em tempo real, level, coordenadas e status vivo/morto de cada personagem.",
        f6_title: "Segurança C++ Native Bridge",
        f6_desc: "Módulo nativo C++ (meg_license_bridge.dll) vinculado ao HWID da máquina, blindado contra fraudes e 100% seguro.",

        // Guide Section
        guide_badge: "FÁCIL OPERAÇÃO",
        guide_title: "Execute o Programa Em 4 Passos Simples",
        guide_desc: "Operação direta no Dashboard, sem necessidade de conhecimentos de TI.",
        step1_badge: "Preparação",
        step1_title: "Pegue o Instalador e Key de Teste",
        step1_desc: "Entre em contato por WhatsApp / Telegram / Zalo para receber o instalador e ativar sua licença de teste grátis. Suporte de instalação remota em 2 minutos.",
        step1_btn: "Pedir arquivos",
        step2_badge: "Entrar no Jogo",
        step2_title: "Abrir o Jogo MEGAMU",
        step2_desc: "Inicie o MEGAMU Launcher e faça login com suas contas no mundo MEGAMU antes de ligar o Auto.",
        step3_badge: "Permissão Admin",
        step3_title: "Executar Como Administrador",
        step3_desc: "Clique com botão direito e escolha Executar como Administrador no MEGAMU Auto Train Dashboard.exe para conceder permissões.",
        step4_badge: "Operação",
        step4_title: "Ativar e Iniciar o Auto",
        step4_desc: "Clique no botão \"Ativar\", cole a sua License Key e clique em \"Atualizar Games\" ou \"Conectar Todos\" para iniciar!",
        guide_tip_title: "Dica para spots de treino:",
        guide_tip_body: "Acesse a aba \"Perfis\" no Dashboard para customizar seus spots. Escolha o mapa (Lorencia, Devias, Dungeon, Lost Tower, Arena...) e informe as coordenadas X, Y para farmar 24/7.",

        // Pricing Section
        pricing_badge: "TABELA DE PREÇOS E TESTE",
        pricing_title: "Preços de Referência e Inscrição",
        pricing_desc: "Tabela de referência dos planos. Entre em contato diretamente para receber o instalador e ativar o teste grátis.",
        p1_badge: "TESTE RÁPIDO",
        p1_sub: "Experiência",
        p1_title: "Plano Diário",
        p1_desc: "Teste todas as funcionalidades antes de adquirir um plano maior.",
        p1_price: "15.000",
        p1_unit: "VND / Dia (~$0.60 USD)",
        p1_subtext: "Ativação rápida por WhatsApp / Telegram",
        p1_f1: "Duração: 24 Horas (1 Dia)",
        p1_f2: "Todas as funções de Auto Train",
        p1_f3: "Zero-Mouse sem ocupar o mouse",
        p1_f4: "Até 3 contas simultâneas",
        p1_f5: "Sem reset de máquina (HWID)",
        p1_btn: "Testar Plano Diário",

        p2_badge: "⭐ MAIS POPULAR",
        p2_sub: "Rush de Level e Farme",
        p2_title: "Plano Mensal",
        p2_desc: "A melhor opção para subir de level, dar resets e juntar joias sem parar.",
        p2_price: "120.000",
        p2_unit: "VND / 30 Dias (~$4.80 USD)",
        p2_subtext: "Apenas 4.000 VND / dia (75% de economia)",
        p2_f1: "Duração: 30 Dias contínuos",
        p2_f2: "Full recursos: Auto Warp, Loot, Skill",
        p2_f3: "Suporte para 10 Contas simultâneas",
        p2_f4: "Atualizações gratuitas contínuas",
        p2_f5: "Reset de PC: 1 vez / mês",
        p2_btn: "Testar Plano Mensal",

        p3_badge: "🔥 ECONOMIZE 20%",
        p3_sub: "Grande Economia",
        p3_title: "Plano Trimestral (3M)",
        p3_desc: "Jogue a season inteira tranquilo sem se preocupar em renovar.",
        p3_price: "300.000",
        p3_unit: "VND / 90 Dias (~$12.00 USD)",
        p3_subtext: "Apenas 100.000 VND / mês (Mais 20% desconto)",
        p3_f1: "Duração: 90 Dias (3 Meses)",
        p3_f2: "Multi-Client 15 contas simultâneas",
        p3_f3: "Inclui lista de coordenadas VIP de spots",
        p3_f4: "Suporte de instalação completo de A a Z",
        p3_f5: "Reset de PC: 3 vezes / período",
        p3_btn: "Testar Plano Trimestral",

        p4_badge: "👑 LIFETIME VIP",
        p4_sub: "Acesso Vitalício",
        p4_title: "Plano Vitalício",
        p4_desc: "Pague uma única vez e aproveite para sempre todas as atualizações.",
        p4_price: "799.000",
        p4_unit: "VND (~$32.00 USD)",
        p4_subtext: "Licença vitalícia ilimitada",
        p4_f1: "Duração: VITALÍCIA (PARA SEMPRE)",
        p4_f2: "Multi-Client liberado (até 50 slots)",
        p4_f3: "Atualizações grátis para todas as novas seasons",
        p4_f4: "Resets de PC ilimitados (HWID)",
        p4_f5: "Grupo VIP no Telegram com suporte 24/7",
        p4_btn: "Consultar Plano Vitalício",

        // FAQ Section
        faq_badge: "PERGUNTAS FREQUENTES",
        faq_title: "Perguntas Frequentes (FAQ)",
        faq_desc: "Tudo o que você precisa saber antes de começar a usar o DAuto MEGAMU.",
        faq1_q: "1. Há risco de banimento ao usar o DAuto MEGAMU?",
        faq1_a: "O DAuto utiliza hooks nativos simulando a movimentação natural dos personagens, sem alterar arquivos do servidor. Você pode farmar, upar e caçar joias com total tranquilidade.",
        faq2_q: "2. Como funciona a tecnologia \"Zero-Mouse\" sem ocupar o mouse?",
        faq2_a: "Ao contrário de bots comuns que travam seu ponteiro na tela, o DAuto envia comandos de movimento, skills e loot diretamente na memória em segundo plano. Você pode minimizar as janelas e continuar trabalhando normalmente sem interrupções.",
        faq3_q: "3. Posso continuar usando minha licença se trocar de PC ou formatar o Windows?",
        faq3_a: "Com certeza! Para os planos Mensal, Trimestral e Vitalício, nosso sistema realiza o reset de HWID com agilidade. Basta enviar uma mensagem ao suporte com sua chave para liberá-la no novo PC.",
        faq4_q: "4. Como recebo o arquivo de instalação e a chave de teste grátis?",
        faq4_a: "Muito simples! Basta entrar em contato pelo WhatsApp, Telegram ou Zalo. Nossa equipe enviará imediatamente o instalador mais recente com uma key de teste grátis e suporte remoto se precisar.",

        // Contact Section
        contact_banner_title: "Precisa de Suporte ou Instalação de Teste?",
        contact_banner_desc: "Nossa equipe de suporte técnico está online 24/7 para ajudar na instalação remota via Ultraviewer / AnyDesk, tirar dúvidas e liberar chaves na hora.",
        contact_btn_telegram: "Suporte no Telegram",
        contact_btn_whatsapp: "Suporte no WhatsApp",

        // Footer
        footer_desc: "A melhor solução de automação para a comunidade MEGAMU.",
        footer_rights: "Todos os direitos reservados.",

        // Modal
        modal_title: "Inscrição para Teste e Consulta",
        modal_subtitle: "Fale conosco para receber o instalador e a key de teste do DAuto MEGAMU",
        modal_plan_label: "Plano selecionado:",
        modal_price_label: "Preço de referência:",
        modal_box_title: "Key de Teste Grátis e Suporte de Instalação",
        modal_box_desc: "Para receber o instalador e ativar sua key de teste, fale conosco diretamente pelo WhatsApp, Telegram ou Zalo. Enviaremos os arquivos e faremos a instalação remota em 2 minutos.",
        modal_hotline_label: "Canais de suporte online:",
        modal_instruction: "Clique nos botões abaixo para solicitar os arquivos agora:",
        modal_btn_zalo: "Falar via WhatsApp / Zalo",
        modal_btn_call: "Ligar para o Suporte (+84 362.031.354)",
        modal_btn_close: "Fechar"
    }
};

const LANG_CONFIG = {
    vi: { code: 'VI', name: 'Tiếng Việt', flag: '🇻🇳' },
    en: { code: 'EN', name: 'English', flag: '🇬🇧' },
    es: { code: 'ES', name: 'Español', flag: '🇪🇸' },
    pt: { code: 'PT', name: 'Português', flag: '🇧🇷' }
};

let currentLanguage = 'vi';

function initI18n() {
    // 1. Detect language: URL param ?lang= > localStorage > browser language > default 'vi'
    const urlParams = new URLSearchParams(window.location.search);
    const urlLang = urlParams.get('lang');
    const storedLang = localStorage.getItem('meg_site_lang');
    
    let targetLang = 'vi';
    if (urlLang && ['vi', 'en', 'es', 'pt'].includes(urlLang.toLowerCase())) {
        targetLang = urlLang.toLowerCase();
    } else if (storedLang && ['vi', 'en', 'es', 'pt'].includes(storedLang.toLowerCase())) {
        targetLang = storedLang.toLowerCase();
    } else {
        const browserLang = (navigator.language || navigator.userLanguage || '').toLowerCase();
        if (browserLang.startsWith('pt')) {
            targetLang = 'pt';
        } else if (browserLang.startsWith('es')) {
            targetLang = 'es';
        } else if (browserLang.startsWith('en')) {
            targetLang = 'en';
        }
    }

    setLanguage(targetLang, false);

    // Close dropdown on outside click
    document.addEventListener('click', function(e) {
        const langDropdown = document.getElementById('langMenu');
        const langBtn = document.getElementById('langDropdownBtn');
        if (langDropdown && langBtn && !langBtn.contains(e.target) && !langDropdown.contains(e.target)) {
            langDropdown.classList.add('hidden');
        }
    });
}

function toggleLangDropdown() {
    const langDropdown = document.getElementById('langMenu');
    if (langDropdown) {
        langDropdown.classList.toggle('hidden');
    }
}

function setLanguage(lang, updateUrl = true) {
    if (!I18N_DICTIONARY[lang]) lang = 'vi';
    currentLanguage = lang;
    localStorage.setItem('meg_site_lang', lang);

    if (updateUrl && window.history && window.history.replaceState) {
        const url = new URL(window.location);
        url.searchParams.set('lang', lang);
        window.history.replaceState({}, '', url);
    }

    document.documentElement.lang = lang;

    // Update Flag & Code in Trigger Button
    const flagEl = document.getElementById('currentLangFlag');
    const labelEl = document.getElementById('currentLangLabel');
    if (flagEl && LANG_CONFIG[lang]) flagEl.textContent = LANG_CONFIG[lang].flag;
    if (labelEl && LANG_CONFIG[lang]) labelEl.textContent = LANG_CONFIG[lang].code;

    // Update active highlight in dropdown
    ['vi', 'en', 'es', 'pt'].forEach(l => {
        const opt = document.getElementById('lang-opt-' + l);
        if (opt) {
            if (l === lang) {
                opt.classList.add('bg-cyan-500/20', 'text-cyan-400', 'font-bold');
                opt.classList.remove('text-slate-300');
            } else {
                opt.classList.remove('bg-cyan-500/20', 'text-cyan-400', 'font-bold');
                opt.classList.add('text-slate-300');
            }
        }
    });

    // Close dropdown
    const langMenu = document.getElementById('langMenu');
    if (langMenu) langMenu.classList.add('hidden');

    // Translate DOM elements
    applyTranslations();
}

function applyTranslations() {
    const dict = I18N_DICTIONARY[currentLanguage] || I18N_DICTIONARY.vi;

    // Update document title & meta description
    if (dict.page_title) {
        document.title = dict.page_title;
    }
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc && dict.meta_desc) {
        metaDesc.setAttribute('content', dict.meta_desc);
    }

    // Translate elements with data-i18n
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (dict[key] !== undefined) {
            el.textContent = dict[key];
        }
    });

    // Translate elements with data-i18n-html
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
        const key = el.getAttribute('data-i18n-html');
        if (dict[key] !== undefined) {
            el.innerHTML = dict[key];
        }
    });

    // Translate placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (dict[key] !== undefined) {
            el.setAttribute('placeholder', dict[key]);
        }
    });
}

function getTranslation(key) {
    const dict = I18N_DICTIONARY[currentLanguage] || I18N_DICTIONARY.vi;
    return dict[key] !== undefined ? dict[key] : (I18N_DICTIONARY.vi[key] || key);
}

// Auto init on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initI18n);
} else {
    initI18n();
}
