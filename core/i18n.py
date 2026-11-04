"""
Core Module: Internationalization (i18n) & Localization Engine.
Supports VI (Vietnamese), EN (English), PT-BR (Portuguese).
"""

import json
from pathlib import Path

CONFIG_DIR = Path("config")
UI_SETTINGS_FILE = CONFIG_DIR / "ui_settings.json"

CURRENT_LANG = "vi"

I18N = {
    "vi": {
        "characters": "Tài khoản",
        "configuration": "Cấu hình",
        "logs": "Nhật ký",
        "text_config": "Mở thư mục",
        "connect_all": "Kết nối tất cả",
        "assign_team5": "Gán toàn bộ",
        "refresh_games": "Làm mới Game",
        "add": "Thêm",
        "remove": "Xóa",
        "col_no": "STT",
        "col_char_pid": "Nhân vật / PID",
        "col_route_preset": "Cấu hình",
        "col_level": "Cấp độ & Point",
        "col_coordinates": "Tọa độ",
        "col_status": "Trạng thái",
        "col_actions": "Thao tác",
        "edit_profile": "Sửa cấu hình:",
        "pk_delay": "Thời gian chờ PK/Hồi sinh:",
        "reload": "Tải lại",
        "save_profile": "Lưu cấu hình",
        "team_note": "Team mặc định: 1-5=C1, 6-10=C2, ... 46-50=C10. Có thể chọn cấu hình khác cho từng dòng.",
        "show": "Hiện:",
        "clear_view": "Xóa hiển thị",
        "all": "Tất cả",
        "stage_min": "Min",
        "stage_max": "Max",
        "stage_map": "Map",
        "stage_x": "X",
        "stage_y": "Y",
        "status_running": "Đang chạy",
        "status_moving": "Di chuyển",
        "status_disconnected": "Mất kết nối",
        "status_stopped": "Đã dừng",
        "status_idle": "Chờ",
        "total_accounts": "Tổng số tài khoản: {n}",
        "connected": "Đã kết nối",
        "license": "Bản quyền",
        "expiry_label": "Hạn",
        "header_stats": "Game: {games} | Đã kết nối: {conn}/{slots} | Auto: {auto} | Bản quyền: {license}",
        "footer_stats": "Tổng số: {slots} Tài khoản | Đã kết nối: {conn} | Đang chạy: {auto}",
        "lang_changed": "Đã chuyển đổi ngôn ngữ sang: {lang}",
        "ram_optimizer": "Tối ưu RAM",
        "ram_trim_now": "Tối ưu RAM",
        "ram_auto_trim": "Tự động dọn RAM:",
        "ram_active_clients": "CLIENT HOẠT ĐỘNG",
        "ram_current_ram": "RAM ĐANG DÙNG",
        "ram_total_saved": "TỔNG ĐÃ TIẾT KIỆM",
        "ram_optimize_all_btn": "TỐI ƯU TOÀN BỘ MEGAMU (TRIM RAM NGAY)",
        "moss_merchant": "Moss Merchant",
        "moss_title": "🎰 MEGAMU MOSS THE GAMBLER • AUTO ROLL PRO",
        "moss_subtitle": "Quay đồ may rủi tự động tại NPC Moss (Elbeland) • Hỗ trợ mở giao diện ngầm & quay đồ Zero-Focus",
        "moss_slot": "Chọn Slot / Nhân vật:",
        "moss_category": "Danh mục vật phẩm:",
        "moss_delay": "Delay mỗi lượt (ms):",
        "moss_max_rolls": "Giới hạn số lượt (0 = Vô hạn):",
        "moss_btn_open": "Mở Giao Diện NPC",
        "moss_btn_roll_once": "Quay Thử 1 Lần",
        "moss_btn_start": "BẮT ĐẦU AUTO QUAY",
        "moss_btn_stop": "DỪNG AUTO QUAY",
        "moss_kpi_total": "TỔNG ĐÃ QUAY",
        "moss_kpi_status": "TRẠNG THÁI",
        "moss_kpi_cat": "DANH MỤC",
        "moss_kpi_target": "NHÂN VẬT ĐANG CHỌN",
        "mirror_event": "Double Goer (Mirror)",
        "mirror_title": "🪞 MEGAMU DOUBLE GOER • MIRROR OF DIMENSIONS",
        "mirror_subtitle": "Tự động tham gia sự kiện Gương Không Gian (Doppelganger) • Vào cửa Native & Auto Move tới NPC Lugard",
        "mirror_btn_enter": "Vào Cửa Mirror (Native)",
        "mirror_btn_npc": "Mở Đối Thoại NPC Lugard",
        "mirror_btn_move": "Chạy Tới Lugard (Elbeland)",
        "mirror_btn_start": "BẮT ĐẦU AUTO MIRROR",
        "mirror_btn_stop": "DỪNG AUTO MIRROR"
    },
    "en": {
        "characters": "Characters",
        "configuration": "Configuration",
        "logs": "Logs",
        "text_config": "Text config",
        "connect_all": "Connect All",
        "assign_team5": "Assign All",
        "refresh_games": "Refresh Game",
        "add": "Add",
        "remove": "Remove",
        "col_no": "No.",
        "col_char_pid": "Character / PID",
        "col_route_preset": "Profile",
        "col_level": "Level & Points",
        "col_coordinates": "Coordinates",
        "col_status": "Status",
        "col_actions": "Actions",
        "edit_profile": "Edit profile:",
        "pk_delay": "PK/Respawn delay:",
        "reload": "Reload",
        "save_profile": "Save Profile",
        "team_note": "Default teams: 1-5=C1, 6-10=C2, ... 46-50=C10. You can also choose a different profile per row.",
        "show": "Show:",
        "clear_view": "Clear View",
        "all": "All",
        "stage_min": "Min",
        "stage_max": "Max",
        "stage_map": "Map",
        "stage_x": "X",
        "stage_y": "Y",
        "status_running": "Running",
        "status_moving": "Moving",
        "status_disconnected": "Disconnected",
        "status_stopped": "Stopped",
        "status_idle": "Idle",
        "total_accounts": "Total accounts: {n}",
        "connected": "Connected",
        "license": "License",
        "expiry_label": "Exp",
        "header_stats": "Games: {games} | Connected: {conn}/{slots} | Auto: {auto} | License: {license}",
        "footer_stats": "Total: {slots} Accounts | Connected: {conn} | Running: {auto}",
        "lang_changed": "Language switched to: {lang}",
        "ram_optimizer": "RAM Optimizer",
        "ram_trim_now": "Trim RAM",
        "ram_auto_trim": "Auto-Trim RAM:",
        "ram_active_clients": "ACTIVE CLIENTS",
        "ram_current_ram": "CURRENT RAM",
        "ram_total_saved": "TOTAL SAVED",
        "ram_optimize_all_btn": "OPTIMIZE MEGAMU (TRIM RAM NOW)",
        "moss_merchant": "Moss Merchant",
        "moss_title": "🎰 MEGAMU MOSS THE GAMBLER • AUTO ROLL PRO",
        "moss_subtitle": "Auto Gamble Item Roll at NPC Moss (Elbeland) • Zero-Focus Native Packet Dispatch",
        "moss_slot": "Select Slot / Character:",
        "moss_category": "Item Category:",
        "moss_delay": "Delay per roll (ms):",
        "moss_max_rolls": "Max Rolls (0 = Unlimited):",
        "moss_btn_open": "Open NPC Window",
        "moss_btn_roll_once": "Roll Once",
        "moss_btn_start": "START AUTO ROLL",
        "moss_btn_stop": "STOP AUTO ROLL",
        "moss_kpi_total": "TOTAL ROLLS",
        "moss_kpi_status": "STATUS",
        "moss_kpi_cat": "CATEGORY",
        "moss_kpi_target": "TARGET CHARACTER",
        "mirror_event": "Double Goer (Mirror)",
        "mirror_title": "🪞 MEGAMU DOUBLE GOER • MIRROR OF DIMENSIONS",
        "mirror_subtitle": "Auto Double Goer / Doppelganger Event • Zero-Focus Native Packet & Auto Move to NPC Lugard",
        "mirror_btn_enter": "Enter Event (Native)",
        "mirror_btn_npc": "Talk to NPC Lugard",
        "mirror_btn_move": "Move to Lugard (Elbeland)",
        "mirror_btn_start": "START AUTO MIRROR",
        "mirror_btn_stop": "STOP AUTO MIRROR"
    },
    "pt-BR": {
        "characters": "Personagens",
        "configuration": "Configurações",
        "logs": "Registros",
        "text_config": "Arquivos config",
        "connect_all": "Conectar Todos",
        "assign_team5": "Atribuir Todos",
        "refresh_games": "Atualizar Jogos",
        "add": "Adicionar",
        "remove": "Remover",
        "col_no": "Nº",
        "col_char_pid": "Personagem / PID",
        "col_route_preset": "Perfil",
        "col_level": "Nível & Pontos",
        "col_coordinates": "Coordenadas",
        "col_status": "Status",
        "col_actions": "Ações",
        "edit_profile": "Editar perfil:",
        "pk_delay": "Espera PK/Respawn:",
        "reload": "Recarregar",
        "save_profile": "Salvar Perfil",
        "team_note": "Times padrão: 1-5=C1, 6-10=C2, ... 46-50=C10. Você có pode escolher outro perfil por linha.",
        "show": "Mostrar:",
        "clear_view": "Limpar Visão",
        "all": "Todos",
        "stage_min": "Mín",
        "stage_max": "Máx",
        "stage_map": "Mapa",
        "stage_x": "X",
        "stage_y": "Y",
        "status_running": "Executando",
        "status_moving": "Movendo",
        "status_disconnected": "Desconectado",
        "status_stopped": "Parado",
        "status_idle": "Aguardando",
        "total_accounts": "Total de contas: {n}",
        "connected": "Conectados",
        "license": "Licença",
        "expiry_label": "Val",
        "header_stats": "Jogos: {games} | Conectados: {conn}/{slots} | Auto: {auto} | Licença: {license}",
        "footer_stats": "Total: {slots} Contas | Conectados: {conn} | Executando: {auto}",
        "lang_changed": "Idioma alterado para: {lang}",
        "ram_optimizer": "Otimizar RAM",
        "ram_trim_now": "Otimizar RAM",
        "ram_auto_trim": "Limpeza Automática:",
        "ram_active_clients": "CLIENTS ATIVOS",
        "ram_current_ram": "RAM ATUAL",
        "ram_total_saved": "TOTAL ECONOMIZADO",
        "ram_optimize_all_btn": "OTIMIZAR MEGAMU (TRIM RAM AGORA)",
        "moss_merchant": "Moss Merchant",
        "moss_title": "🎰 MEGAMU MOSS THE GAMBLER • AUTO ROLL PRO",
        "moss_subtitle": "Giro Automático no NPC Moss (Elbeland) • Disparo Nativo Zero-Focus",
        "moss_slot": "Selecionar Slot / Personagem:",
        "moss_category": "Categoria de Item:",
        "moss_delay": "Espera por giro (ms):",
        "moss_max_rolls": "Limite de Giros (0 = Infinito):",
        "moss_btn_open": "Abrir Janela do NPC",
        "moss_btn_roll_once": "Girar 1 Vez",
        "moss_btn_start": "INICIAR AUTO GIRO",
        "moss_btn_stop": "PARAR AUTO GIRO",
        "moss_kpi_total": "TOTAL DE GIROS",
        "moss_kpi_status": "STATUS",
        "moss_kpi_cat": "CATEGORIA",
        "moss_kpi_target": "PERSONAGEM ALVO",
        "mirror_event": "Double Goer (Mirror)",
        "mirror_title": "🪞 MEGAMU DOUBLE GOER • MIRROR OF DIMENSIONS",
        "mirror_subtitle": "Evento Automático Double Goer (Doppelganger) • Entrada Nativa e Auto Mover para NPC Lugard",
        "mirror_btn_enter": "Entrar no Evento (Nativo)",
        "mirror_btn_npc": "Falar com NPC Lugard",
        "mirror_btn_move": "Mover para Lugard (Elbeland)",
        "mirror_btn_start": "INICIAR AUTO MIRROR",
        "mirror_btn_stop": "PARAR AUTO MIRROR"
    }
}

CURRENT_LANG = "vi"

def load_language_preference() -> str:
    global CURRENT_LANG
    try:
        if UI_SETTINGS_FILE.exists():
            data = json.loads(UI_SETTINGS_FILE.read_text(encoding="utf-8"))
            lang = str(data.get("language", "vi")).strip().lower()
            for k in I18N.keys():
                if k.lower() == lang:
                    CURRENT_LANG = k
                    return CURRENT_LANG
    except Exception:
        pass
    CURRENT_LANG = "vi"
    return CURRENT_LANG

def save_language_preference(lang: str):
    global CURRENT_LANG
    for k in I18N.keys():
        if k.lower() == lang.lower():
            CURRENT_LANG = k
            break
    try:
        data = {"language": CURRENT_LANG}
        UI_SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def tr(key: str, **kwargs) -> str:
    lang_dict = None
    for k, v in I18N.items():
        if k.lower() == CURRENT_LANG.lower():
            lang_dict = v
            break
    if not lang_dict:
        lang_dict = I18N.get("vi", {})
    text = lang_dict.get(key, I18N.get("vi", {}).get(key, key))
    try:
        return text.format(**kwargs)
    except Exception:
        return text

# ==============================================================================
# QUẢN LÝ TIẾN TRÌNH & TIÊU ĐỀ CỬA SỔ
# ==============================================================================
