import streamlit as st
import streamlit.components.v1 as components
import subprocess
import os
import json
import time
import html

# ==========================================
# CONFIG
# ==========================================
st.set_page_config(
    page_title="EV Routing MPC - Hà Nội",
    page_icon="EV",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Thông tin các dòng xe (VinFast + BYD)
VEHICLES = {
    "VF 9":     {"name": "VF 9",     "soc_max": 92.0,  "battery": "92 kWh",     "image": "assets/vf9.png"},
    "VF 8":     {"name": "VF 8",     "soc_max": 82.0,  "battery": "82 kWh",     "image": "assets/vf8.png"},
    "VF 7":     {"name": "VF 7",     "soc_max": 75.3,  "battery": "75.3 kWh",   "image": "assets/vf7.png"},
    "VF 6":     {"name": "VF 6",     "soc_max": 59.6,  "battery": "59.6 kWh",   "image": "assets/vf6.png"},
    "VF MPV7":  {"name": "VF MPV7",  "soc_max": 60.1,  "battery": "60.1 kWh",   "image": "assets/vf_mpv7.png"},
    "VF 5":     {"name": "VF 5",     "soc_max": 37.0,  "battery": "37 kWh",     "image": "assets/vf5.png"},
    "VF 3":     {"name": "VF 3",     "soc_max": 18.6,  "battery": "18.6 kWh",   "image": "assets/vf3.png"},
    # [NEW] BYD — dùng đầu sạc CCS2, tương thích trạm V-Green
    "BYD Seal":   {"name": "BYD Seal",   "soc_max": 82.5,  "battery": "82.5 kWh",  "image": "assets/byd_seal.png"},
    "BYD Atto 3": {"name": "BYD Atto 3", "soc_max": 60.48, "battery": "60.48 kWh", "image": "assets/byd_atto3.png"},
    "BYD Dolphin":{"name": "BYD Dolphin","soc_max": 44.9,  "battery": "44.9 kWh",  "image": "assets/byp_dolphyn.png"},
}

# ==========================================
# CSS
# ==========================================
st.markdown("""
<style>
    :root {
        --bg: #0f0f10;
        --surface: #171719;
        --surface-2: #202124;
        --line: rgba(255, 255, 255, 0.09);
        --text: #f4f4f5;
        --muted: #a1a1aa;
        --subtle: #71717a;
        --accent: #e82127;
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
    }

    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 2.4rem;
        max-width: 1180px;
    }

    section[data-testid="stSidebar"] {
        background: #141416;
        border-right: 1px solid var(--line);
    }

    section[data-testid="stSidebar"] h2 {
        color: var(--text) !important;
        font-size: 1.15rem;
        font-weight: 750;
    }

    section[data-testid="stSidebar"] h3 {
        color: var(--text);
        font-size: 0.82rem;
        font-weight: 750;
        text-transform: uppercase;
        margin-top: 1.15rem;
    }

    section[data-testid="stSidebar"] hr {
        margin: 0.55rem 0 0.9rem;
        border-color: var(--line);
    }

    div[data-testid="stTextInput"] input,
    div[data-baseweb="select"] > div,
    div[data-testid="stNumberInput"] input {
        background: #1d1d20;
        border: 1px solid var(--line);
        border-radius: 8px;
    }

    div[data-testid="stTextInput"] input:focus {
        border-color: rgba(232, 33, 39, 0.7);
        box-shadow: 0 0 0 1px rgba(232, 33, 39, 0.2);
    }

    .stButton button,
    .stDownloadButton button {
        min-height: 2.9rem;
        border-radius: 8px;
        border: 1px solid var(--line);
        font-weight: 720;
        transition: background 160ms ease, border-color 160ms ease, transform 160ms ease;
    }

    .stButton button:hover,
    .stDownloadButton button:hover {
        transform: translateY(-1px);
        border-color: rgba(255, 255, 255, 0.18);
    }

    .stButton button[kind="primary"],
    .stDownloadButton button[kind="primary"] {
        background: var(--accent);
        border-color: var(--accent);
        color: white;
    }

    .ev-hero,
    .ev-panel,
    .ev-metric,
    .ev-route-card,
    .ev-download-panel {
        animation: softIn 240ms ease both;
    }

    @keyframes softIn {
        from { opacity: 0; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .ev-hero {
        display: grid;
        grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr);
        gap: 1rem;
        align-items: stretch;
        padding: 1.1rem 0 1.2rem;
        border-bottom: 1px solid var(--line);
        margin-bottom: 1rem;
    }

    .ev-kicker {
        color: var(--muted);
        font-size: 0.76rem;
        font-weight: 720;
        text-transform: uppercase;
        margin-bottom: 0.42rem;
    }

    .ev-title {
        margin: 0;
        color: var(--text);
        font-size: 2.2rem;
        line-height: 1.08;
        letter-spacing: 0;
        font-weight: 760;
    }

    .ev-subtitle {
        color: var(--muted);
        margin: 0.7rem 0 0;
        max-width: 760px;
        font-size: 1rem;
        line-height: 1.5;
    }

    .ev-status-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.95rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 0.7rem;
    }

    .ev-status-row {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        color: var(--muted);
        font-size: 0.9rem;
    }

    .ev-status-row strong {
        color: var(--text);
        text-align: right;
        font-weight: 680;
    }

    .ev-panel,
    .ev-download-panel {
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface);
        padding: 1rem;
    }

    .ev-metric {
        min-height: 104px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface);
        padding: 0.95rem;
    }

    .ev-metric-label {
        color: var(--muted);
        font-size: 0.75rem;
        font-weight: 720;
        text-transform: uppercase;
    }

    .ev-metric-value {
        color: var(--text);
        font-size: 1.55rem;
        font-weight: 780;
        margin-top: 0.34rem;
        line-height: 1.1;
    }

    .ev-metric-note {
        color: var(--subtle);
        font-size: 0.84rem;
        margin-top: 0.42rem;
    }

    .ev-route-card {
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface);
        padding: 0.95rem;
        margin: 0.8rem 0 1rem;
    }

    .ev-route-main {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        color: var(--text);
        font-weight: 760;
        font-size: 1.02rem;
        flex-wrap: wrap;
    }

    .ev-pill {
        display: inline-flex;
        align-items: center;
        min-height: 1.65rem;
        padding: 0.22rem 0.58rem;
        border-radius: 999px;
        background: var(--surface-2);
        border: 1px solid var(--line);
        color: #d4d4d8;
        font-size: 0.8rem;
        font-weight: 650;
        margin-top: 0.7rem;
        margin-right: 0.35rem;
    }

    .ev-soc-track {
        height: 8px;
        border-radius: 999px;
        overflow: hidden;
        background: #2b2b2f;
        margin-top: 0.45rem;
    }

    .ev-soc-fill {
        height: 100%;
        border-radius: inherit;
        background: var(--accent);
    }

    .ev-section-title {
        color: var(--text);
        font-size: 0.98rem;
        font-weight: 760;
        margin: 0 0 0.58rem;
    }

    div[data-testid="stMetric"] {
        background: transparent;
        border: 0;
        padding: 0;
    }

    div[data-testid="stTabs"] button {
        border-radius: 8px;
        color: var(--muted);
        font-weight: 680;
    }

    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--text);
    }

    @media (max-width: 900px) {
        .ev-hero {
            grid-template-columns: 1fr;
        }

        .ev-title {
            font-size: 1.6rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# HELPER
# ==========================================
def load_summary():
    if os.path.exists("data/summary.json"):
        try:
            with open("data/summary.json", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return None

def clear_old_outputs():
    for f in ["data/summary.json", "results/ev_routing_map.html", "results/ev_routing_result.png", "results/DriveCycle_Data.mat"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass

def h(value):
    return html.escape(str(value), quote=True)

def render_soc_bar(percent):
    safe_percent = max(0, min(100, float(percent)))
    st.markdown(
        f"""
        <div class="ev-soc-track">
            <div class="ev-soc-fill" style="width:{safe_percent:.1f}%"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_metric_card(label, value, note=""):
    st.markdown(
        f"""
        <div class="ev-metric">
            <div class="ev-metric-label">{h(label)}</div>
            <div class="ev-metric-value">{h(value)}</div>
            <div class="ev-metric-note">{h(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    col1, col2 = st.columns([1, 3])
    with col1:
        if os.path.exists("assets/logo_hust.png"):
            st.image("assets/logo_hust.png", width=72)
    with col2:
        st.markdown("<h2 style='margin:0;'>EV Routing MPC</h2>", unsafe_allow_html=True)
        st.caption("Hà Nội / TomTom traffic")

    st.markdown("### Phương tiện")
    st.markdown("---")

    vehicle_choice = st.selectbox(
        "Dòng xe",
        options=list(VEHICLES.keys()),
        index=1,   
    )

    selected = VEHICLES[vehicle_choice]

    col_img, col_info = st.columns([1, 2])
    with col_img:
        if os.path.exists(selected["image"]):
            st.image(selected["image"], width=104)
        else:
            st.markdown("EV")

    with col_info:
        st.markdown(f"**{h(selected['name'])}**")
        st.caption(f"Dung lượng pin: **{h(selected['battery'])}**")

    st.markdown("### Lộ trình")
    st.markdown("---")

    start_point = st.text_input("Điểm xuất phát", value="Bách Khoa Hà Nội")
    end_point   = st.text_input("Điểm đến", value="Sân bay Nội Bài")

    soc_init = st.slider(
        "Mức pin khởi hành (kWh)",
        min_value=1.0,
        max_value=selected["soc_max"],
        value=min(30.0, selected["soc_max"] * 0.4),
        step=0.5
    )

    soc_pct = (soc_init / selected["soc_max"]) * 100
    st.caption(f"Tương đương **{soc_pct:.1f}%** dung lượng pin")
    render_soc_bar(soc_pct)

    st.markdown("### Pin & sạc")
    allow_charging = st.checkbox("Cho phép dừng sạc dọc đường", value=True)

    max_soc_pct = st.slider(
        "Mức sạc tối đa tại trạm (%)",
        min_value=75,
        max_value=100,
        value=92,
        step=1,
        help="Thực tế thường sạc đến 90-95% để bảo vệ pin và tiết kiệm thời gian"
    )

    st.markdown("### Chiến lược tối ưu")
    priority = st.selectbox(
        "Ưu tiên chính",
        options=["Cân bằng thời gian & năng lượng", 
                 "Tiết kiệm năng lượng nhất", 
                 "Nhanh nhất"],
        index=0
    )

    priority_map = {
        "Cân bằng thời gian & năng lượng": "balanced",
        "Tiết kiệm năng lượng nhất":       "energy",
        "Nhanh nhất":                       "time"
    }

    # ── [NEW] ĐIỀU KIỆN MÔI TRƯỜNG ──
    with st.expander("Điều kiện môi trường", expanded=False):
        ambient_temp = st.slider(
            "Nhiệt độ ngoài trời (°C)",
            min_value=5, max_value=45, value=28, step=1,
            help="Ảnh hưởng đến dung lượng pin khả dụng và mức tiêu thụ điều hòa. "
                 "Hà Nội mùa hè ~35°C, mùa đông ~15°C."
        )
        ac_on = st.checkbox("Bật điều hòa / hệ thống làm mát-sưởi", value=True,
            help="Khi tắt, P_aux giảm xuống ~350W (chỉ điện tử cơ bản)")
        n_passengers = st.slider(
            "Số người trên xe",
            min_value=1, max_value=7, value=1, step=1,
            help="Mỗi hành khách thêm tăng phụ tải HVAC ~200W"
        )

        # Cảnh báo nhiệt độ
        if ambient_temp < 10:
            st.warning(f"{ambient_temp}°C: Pin có thể mất 15-22% dung lượng khả dụng")
        elif ambient_temp > 40:
            st.warning(f"{ambient_temp}°C: Pin mất ~10-15% dung lượng + sạc chậm hơn")

    st.markdown("---")
    run_btn = st.button("Chạy mô phỏng", width="stretch", type="primary")

# ==========================================
# MAIN
# ==========================================
st.markdown(
    f"""
    <div class="ev-hero">
        <div>
            <div class="ev-kicker">EV Routing MPC / Hanoi traffic</div>
            <h1 class="ev-title">Energy routing</h1>
            <p class="ev-subtitle">
                {h(start_point)} <span style="color:#e82127;font-weight:760;">→</span> {h(end_point)}
            </p>
        </div>
        <div class="ev-status-card">
            <div class="ev-status-row"><span>Xe đang chọn</span><strong>{h(selected['name'])}</strong></div>
            <div class="ev-status-row"><span>Dung lượng pin</span><strong>{h(selected['battery'])}</strong></div>
            <div class="ev-status-row"><span>Pin khởi hành</span><strong>{soc_init:.1f} kWh · {soc_pct:.1f}%</strong></div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not run_btn:
    summary = load_summary()
    if summary:
        st.markdown(
            f"""
            <div class="ev-route-card">
                <div class="ev-route-main">Kết quả lần chạy trước: {h(summary.get('start_name','?'))} → {h(summary.get('end_name','?'))}</div>
                <span class="ev-pill">Có thể chạy lại với cấu hình mới ở sidebar</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="ev-panel">
                <div class="ev-section-title">Sẵn sàng mô phỏng</div>
                Chưa có kết quả cho cấu hình hiện tại.
            </div>
            """,
            unsafe_allow_html=True,
        )

# ==========================================
# CHẠY MÔ PHỎNG
# ==========================================
if run_btn:
    if not start_point.strip() or not end_point.strip():
        st.error("Vui lòng nhập đầy đủ điểm xuất phát và điểm đến.")
        st.stop()
    if start_point.strip().lower() == end_point.strip().lower():
        st.error("Điểm xuất phát và điểm đến không được trùng nhau.")
        st.stop()

    params = {
        "start_node":     start_point.strip(),
        "end_node":       end_point.strip(),
        "soc_init":       float(soc_init),
        "allow_charging": allow_charging,
        "priority":       priority_map[priority],
        "vehicle":        vehicle_choice,
        "max_soc_pct":    max_soc_pct,
        # [NEW] Điều kiện môi trường
        "ambient_temp":   int(ambient_temp),
        "ac_on":          bool(ac_on),
        "n_passengers":   int(n_passengers),
    }

    os.makedirs('data', exist_ok=True)
    with open("data/ui_params.json", "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

    clear_old_outputs()

    st.markdown("### Đang tính toán lộ trình")
    progress_bar = st.progress(0, text="Khởi động hệ thống...")
    log_container = st.empty()

    try:
        proc = subprocess.Popen(
            ["python", "src/Base.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        stdout_lines = []
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                stdout_lines.append(line)

            if "[1/4]" in line:
                progress_bar.progress(25, text="Xác định vị trí...")
            elif "[2/4]" in line:
                progress_bar.progress(50, text="Xây dựng đồ thị đường...")
            elif "[3/4]" in line:
                progress_bar.progress(75, text="Chạy thuật toán MPC...")
            elif "[4/4]" in line or "Hoan tat" in line.lower() or "[INFO] Da xuat" in line:
                progress_bar.progress(95, text="Đang xuất kết quả...")

            log_container.code("\n".join(stdout_lines[-10:]), language="text")

        proc.wait()

        if proc.returncode != 0:
            st.error("Mô phỏng gặp lỗi.")
            with st.expander("Chi tiết lỗi"):
                st.code(proc.stderr.read(), language="bash")
            st.stop()

    except Exception as e:
        st.error(f"Lỗi thực thi: {e}")
        st.stop()

    progress_bar.progress(100, text="Hoàn tất")
    st.success("Mô phỏng hoàn tất.")

# ==========================================
# HIỂN THỊ KẾT QUẢ
# ==========================================
summary = load_summary()

if summary:
    drive_time   = summary.get('total_time_min', 0)
    charge_time  = summary.get('total_charge_min', 0)
    total_time   = drive_time + charge_time
    charge_note = f"Sạc {charge_time:.0f} phút" if charge_time > 0 else "Không cần dừng sạc"

    st.markdown(
        f"""
        <div class="ev-route-card">
            <div class="ev-route-main">{h(summary.get('start_name','?'))} <span style="color:#e82127;">→</span> {h(summary.get('end_name','?'))}</div>
            <span class="ev-pill">{h(summary.get('vehicle', selected['name']))}</span>
            <span class="ev-pill">{charge_note}</span>
            <span class="ev-pill">MPC / TomTom</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("Quãng đường", f"{summary.get('total_dist_km', 0):.1f} km", "Tuyến tối ưu")
    with col2:
        render_metric_card("Tổng thời gian", f"{total_time:.0f} phút", f"Lái {drive_time:.0f} phút · {charge_note}")
    with col3:
        render_metric_card("Năng lượng", f"{summary.get('total_energy_kwh', 0):.2f} kWh", "Tổng tiêu hao")
    with col4:
        render_metric_card("Hiệu suất", f"{summary.get('efficiency_kwh100km', 0):.2f}", "kWh / 100 km")

    tab_overview, tab_map, tab_sim, tab_export = st.tabs(["Tổng quan", "Bản đồ", "Mô phỏng", "Xuất dữ liệu"])

    with tab_overview:
        if summary.get("n_charging_stops", 0) > 0:
            st.markdown(
                f"""
                <div class="ev-panel">
                    <div class="ev-section-title">Kế hoạch sạc</div>
                    Lộ trình bao gồm <strong>{summary['n_charging_stops']} lần dừng sạc</strong>.
                    Trạm sạc đã được thêm tự động vào file Drive Cycle để dùng trong MATLAB/Simulink.
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="ev-panel">
                    <div class="ev-section-title">Kế hoạch sạc</div>
                    Pin khởi hành đủ cho tuyến này, hệ thống không thêm điểm dừng sạc.
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tab_map:
        st.markdown('<div class="ev-section-title">Lộ trình tối ưu trên bản đồ</div>', unsafe_allow_html=True)
        if os.path.exists("results/ev_routing_map.html"):
            with open("results/ev_routing_map.html", "r", encoding="utf-8") as f:
                components.html(f.read(), height=680, scrolling=True)
        else:
            st.warning("Không tìm thấy file bản đồ.")

    with tab_sim:
        st.markdown('<div class="ev-section-title">Biểu đồ kết quả mô phỏng</div>', unsafe_allow_html=True)
        if os.path.exists("results/ev_routing_result.png"):
            st.image("results/ev_routing_result.png", width="stretch")
        else:
            st.warning("Không tìm thấy ảnh kết quả mô phỏng.")

    with tab_export:
        st.markdown(
            """
            <div class="ev-download-panel">
                <div class="ev-section-title">Tải xuống dữ liệu mô phỏng</div>
                Sử dụng file .mat để đưa chu trình lái, bao gồm cả thời gian dừng sạc, vào MATLAB/Simulink.
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            if os.path.exists("results/DriveCycle_Data.mat"):
                with open("results/DriveCycle_Data.mat", "rb") as f:
                    st.download_button(
                        label="Lấy file Drive Cycle (.mat)",
                        data=f,
                        file_name="DriveCycle_Data.mat",
                        mime="application/octet-stream",
                        width="stretch",
                        type="primary"
                    )
        with col_dl2:
            if os.path.exists("data/summary.json"):
                with open("data/summary.json", "rb") as f:
                    st.download_button(
                        label="Lấy báo cáo tổng hợp (JSON)",
                        data=f,
                        file_name="summary.json",
                        mime="application/json",
                        width="stretch"
                    )

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#546E7A; font-size:13px;'>"
    "EV Routing MPC / Kỹ thuật Ô tô / Đại học Bách Khoa Hà Nội"
    "</p>",
    unsafe_allow_html=True
)
