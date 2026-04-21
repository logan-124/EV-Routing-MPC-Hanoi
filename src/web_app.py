import streamlit as st
import streamlit.components.v1 as components
import subprocess
import os
import json
import time

# ==========================================
# CONFIG
# ==========================================
st.set_page_config(
    page_title="EV Routing MPC - Hà Nội",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Thông tin các dòng xe VinFast
VEHICLES = {
    "VF 9":     {"name": "VF 9",     "soc_max": 92.0,  "battery": "92 kWh",     "image": "assets/vf9.png"},
    "VF 8":     {"name": "VF 8",     "soc_max": 82.0,  "battery": "82 kWh",     "image": "assets/vf8.png"},
    "VF 7":     {"name": "VF 7",     "soc_max": 75.3,  "battery": "75.3 kWh",   "image": "assets/vf7.png"},
    "VF 6":     {"name": "VF 6",     "soc_max": 59.6,  "battery": "59.6 kWh",   "image": "assets/vf6.png"},
    "VF MPV7":  {"name": "VF MPV7",  "soc_max": 60.1,  "battery": "60.1 kWh",   "image": "assets/vf_mpv7.png"},
    "VF 5":     {"name": "VF 5",     "soc_max": 37.0,  "battery": "37 kWh",     "image": "assets/vf5.png"},
    "VF 3":     {"name": "VF 3",     "soc_max": 18.6,  "battery": "18.6 kWh",   "image": "assets/vf3.png"},
}

# ==========================================
# CSS
# ==========================================
st.markdown("""
<style>
    .main { background-color: #0E1117; }
    section[data-testid="stSidebar"] {
        background-color: #161B2E;
        border-right: 2px solid #1F2A44;
    }
    .stButton button {
        height: 3.3rem;
        font-size: 1.08rem;
        font-weight: 600;
        border-radius: 10px;
    }
    .stMetric {
        background-color: #1A2338;
        border-radius: 10px;
        padding: 14px 12px;
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

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    col1, col2 = st.columns([1, 3])
    with col1:
        if os.path.exists("assets/logo_hust.png"):
            st.image("assets/logo_hust.png", width=80)
    with col2:
        st.markdown("<h2 style='margin:0;color:#00E5A0;'>EV Routing MPC</h2>", unsafe_allow_html=True)
        st.caption("Hà Nội • TomTom Real-time Traffic")

    st.markdown("### Chọn phương tiện")
    st.markdown("---")

    vehicle_choice = st.selectbox(
        "Dòng xe VinFast",
        options=list(VEHICLES.keys()),
        index=1,   
    )

    selected = VEHICLES[vehicle_choice]

    col_img, col_info = st.columns([1, 2])
    with col_img:
        if os.path.exists(selected["image"]):
            st.image(selected["image"], width=90)
        else:
            st.markdown("🚗")

    with col_info:
        st.markdown(f"**{selected['name']}**")
        st.caption(f"Dung lượng pin: **{selected['battery']}**")

    st.markdown("---")

    start_point = st.text_input("📍 Điểm xuất phát", value="Bách Khoa Hà Nội")
    end_point   = st.text_input("🏁 Điểm đến", value="Sân bay Nội Bài")

    soc_init = st.slider(
        "🔋 Mức pin khởi hành (kWh)",
        min_value=1.0,
        max_value=selected["soc_max"],
        value=min(30.0, selected["soc_max"] * 0.4),
        step=0.5
    )

    soc_pct = (soc_init / selected["soc_max"]) * 100
    st.caption(f"Tương đương **{soc_pct:.1f}%** dung lượng pin")

    st.markdown("### Tùy chọn tối ưu")
    allow_charging = st.checkbox("Cho phép dừng sạc dọc đường", value=True)

    max_soc_pct = st.slider(
        "Mức sạc tối đa tại trạm (%)",
        min_value=75,
        max_value=100,
        value=92,
        step=1,
        help="Thực tế thường sạc đến 90-95% để bảo vệ pin và tiết kiệm thời gian"
    )

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

    st.markdown("---")
    run_btn = st.button("🚀 Chạy mô phỏng MPC", use_container_width=True, type="primary")

# ==========================================
# MAIN
# ==========================================
st.title("Định tuyến & Quản lý năng lượng xe điện VinFast")
st.markdown("Hệ thống tối ưu hóa lộ trình thông minh sử dụng **Model Predictive Control** và dữ liệu giao thông thời gian thực từ TomTom.")

if not run_btn:
    summary = load_summary()
    if summary:
        st.info(f"📌 Kết quả lần chạy trước: **{summary.get('start_name','?')} → {summary.get('end_name','?')}**")
    else:
        st.info("👈 Vui lòng chọn thông tin ở thanh bên trái và nhấn **Chạy mô phỏng MPC**")

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
        "max_soc_pct":    max_soc_pct
    }

    os.makedirs('data', exist_ok=True)
    with open("data/ui_params.json", "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

    clear_old_outputs()

    st.markdown("### ⏳ Đang tính toán lộ trình...")
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
    st.success("✅ Mô phỏng hoàn tất!")

# ==========================================
# HIỂN THỊ KẾT QUẢ
# ==========================================
summary = load_summary()

if summary:
    drive_time   = summary.get('total_time_min', 0)
    charge_time  = summary.get('total_charge_min', 0)
    total_time   = drive_time + charge_time

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Quãng đường", f"{summary.get('total_dist_km', 0):.1f} km")
    with col2:
        st.metric("Tổng thời gian (Lái + Sạc)", f"{total_time:.0f} phút", 
                  delta=f"Sạc mất {charge_time:.0f} phút" if charge_time > 0 else "Không dừng sạc", 
                  delta_color="off")
    with col3:
        st.metric("Tiêu hao năng lượng", f"{summary.get('total_energy_kwh', 0):.2f} kWh")
    with col4:
        st.metric("Hiệu suất", f"{summary.get('efficiency_kwh100km', 0):.2f} kWh/100km")

    if summary.get("n_charging_stops", 0) > 0:
        st.info(f"🔌 Lộ trình bao gồm **{summary['n_charging_stops']} lần dừng sạc**. "
                f"Trạm sạc đã được thêm tự động vào file xuất Drive Cycle.")

    st.markdown("#### Lộ trình tối ưu trên bản đồ")
    if os.path.exists("results/ev_routing_map.html"):
        with open("results/ev_routing_map.html", "r", encoding="utf-8") as f:
            components.html(f.read(), height=680, scrolling=True)
    else:
        st.warning("Không tìm thấy file bản đồ.")

    if os.path.exists("results/ev_routing_result.png"):
        st.image("results/ev_routing_result.png", use_container_width=True)

    # ==========================================
    # DOWNLOAD DỮ LIỆU
    # ==========================================
    st.markdown("### 📥 Tải xuống Dữ liệu Mô phỏng")
    st.caption("Sử dụng file .mat để đưa chu trình lái (Drive Cycle) bao gồm cả thời gian dừng sạc vào MATLAB/Simulink.")
    
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        if os.path.exists("results/DriveCycle_Data.mat"):
            with open("results/DriveCycle_Data.mat", "rb") as f:
                st.download_button(
                    label="Lấy file Drive Cycle (MATLAB .mat)",
                    data=f,
                    file_name="DriveCycle_Data.mat",
                    mime="application/octet-stream",
                    use_container_width=True,
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
                    use_container_width=True
                )

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#546E7A; font-size:13px;'>"
    "EV Routing MPC • Kỹ thuật Ô tô • Đại học Bách Khoa Hà Nội"
    "</p>",
    unsafe_allow_html=True
)
