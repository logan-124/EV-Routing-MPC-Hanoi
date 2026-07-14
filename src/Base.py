
# ==========================================
# TỰ ĐỘNG CÀI THƯ VIỆN (chạy lần đầu sẽ tự cài)
# ==========================================
import subprocess
import sys

_REQUIRED_PACKAGES = {
    "requests":    "requests",
    "polyline":    "polyline",
    "networkx":    "networkx",
    "numpy":       "numpy",
    "scipy":       "scipy",
    "matplotlib":  "matplotlib",
    "folium":      "folium",
}

def _install_package(pip_name: str):
    print(f"[SETUP] Dang cai dat '{pip_name}'...", flush=True)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", pip_name, "--quiet"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"[SETUP] Da cai xong '{pip_name}'!", flush=True)

for _import_name, _pip_name in _REQUIRED_PACKAGES.items():
    try:
        __import__(_import_name)
    except ImportError:
        _install_package(_pip_name)


import os
import json
import time
import itertools
import requests
import polyline as pl
import networkx as nx
import numpy as np
import scipy.io as sio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import folium
import math 

# ==========================================
# CẤU HÌNH
# ==========================================
SOC_MAX   = 82.0
MAX_STEPS = 50

# ==========================================
# BẢNG THÔNG SỐ VẬT LÝ CÁC DÒNG XE VINFAST (Cập nhật 2026)
# ==========================================
VEHICLE_SPECS = {
    # ══ Giải thích các hệ số hàm chi phí ══════════════════════════
    # kappa_base : hệ số penalty stop-and-go cơ sở (xe nặng/lớn → cao hơn)
    # kappa_slope: tốc độ tăng penalty khi tốc độ giảm xuống dưới 35km/h
    # beta_base  : trọng số năng lượng β cơ sở trong hàm chi phí w = α·t + β·e
    # beta_slope : β tăng thêm bao nhiêu trên mỗi % SOC dưới ngưỡng
    # beta_thresh: ngưỡng SOC (% của SOC_MAX) bắt đầu kích hoạt β thích nghi
    # charge_buf : buffer an toàn khi kiểm tra tính khả thi SOC (% SOC_MAX)
    # ══════════════════════════════════════════════════════════════

    "VF 9": {
        "soc_max": 92.0,
        "mass_kg": 2630,
        "Cd": 0.31,            # Full-size SUV
        "A": 2.85,
        "Cr": 0.012,
        "eta": 0.89,           # AWD dual motor: tổn hao nhiều hơn single motor
        "eta_regen": 0.62,     # AWD regen tốt hơn RWD nhưng không tới 70%
        "P_aux_W": 2800,
        "motor_kw": 300,
        "drive_layout": "AWD",
        # Battery pack tham chiếu cho Simulink Thevenin/OCV
        "battery_chemistry": "NMC",
        "N_series": 96,
        "V_cell_full": 4.18,
        "V_cell_nom": 3.65,
        "V_cell_empty": 3.00,
        # Hàm chi phí: xe to nhất, nặng nhất → penalty cao nhất
        "kappa_base":  2.10,
        "kappa_slope": 0.045,
        "beta_base":   14.0,      # SOC_MAX lớn → cần beta cao để giữ tỷ lệ
        "beta_slope":  0.28,
        "beta_thresh": 0.55,      # Kích hoạt khi SOC < 55% SOC_MAX
        "charge_buf":  0.12,
    },

    "VF 8": {
        "soc_max": 82.0,
        "mass_kg": 2350,
        "Cd": 0.30,            # VF8 SUV Digital Twin tham chiếu
        "A": 2.55,
        "Cr": 0.012,
        "eta": 0.90,           # Hiệu suất tổng hệ truyền lực thực tế ~90%
        "eta_regen": 0.60,     # Phanh tái sinh thực tế ~55-65%, lấy 60%
        "P_aux_W": 2500,
        "motor_kw": 260,
        "drive_layout": "AWD",
        # Battery pack tham chiếu cho Simulink Thevenin/OCV
        "battery_chemistry": "NMC",
        "N_series": 96,
        "V_cell_full": 4.18,
        "V_cell_nom": 3.65,
        "V_cell_empty": 3.00,
        # Hàm chi phí: xe chuẩn tham chiếu
        "kappa_base":  1.85,
        "kappa_slope": 0.035,
        "beta_base":   12.0,
        "beta_slope":  0.25,
        "beta_thresh": 0.50,
        "charge_buf":  0.10,
    },

    "VF 7": {
        "soc_max": 75.3,
        "mass_kg": 1980,
        "Cd": 0.27,
        "A": 2.40,
        "Cr": 0.011,
        "eta": 0.91,
        "eta_regen": 0.64,
        "P_aux_W": 2300,
        "motor_kw": 200,
        # Hàm chi phí: nhẹ hơn VF8 một chút
        "kappa_base":  1.75,
        "kappa_slope": 0.030,
        "beta_base":   11.0,
        "beta_slope":  0.23,
        "beta_thresh": 0.50,
        "charge_buf":  0.10,
    },

    "VF 6": {
        "soc_max": 59.6,
        "mass_kg": 1720,
        "Cd": 0.27,
        "A": 2.30,
        "Cr": 0.011,
        "eta": 0.91,
        "eta_regen": 0.63,
        "P_aux_W": 2100,
        "motor_kw": 150,
        # Hàm chi phí: pin vừa, cân bằng tốt
        "kappa_base":  1.65,
        "kappa_slope": 0.028,
        "beta_base":   10.0,
        "beta_slope":  0.22,
        "beta_thresh": 0.48,
        "charge_buf":  0.10,
    },

    "VF MPV7": {
        "soc_max": 60.13,
        "mass_kg": 2050,
        "Cd": 0.31,
        "A": 2.95,
        "Cr": 0.013,
        "eta": 0.89,
        "eta_regen": 0.60,
        "P_aux_W": 2800,
        "motor_kw": 150,
        # Hàm chi phí: thân to, nhiều hành khách → penalty đô thị cao
        "kappa_base":  2.00,
        "kappa_slope": 0.040,
        "beta_base":   12.0,
        "beta_slope":  0.26,
        "beta_thresh": 0.52,
        "charge_buf":  0.12,
    },

    "VF 5": {
        "soc_max": 37.0,
        "mass_kg": 1450,
        "Cd": 0.30,
        "A": 2.15,
        "Cr": 0.012,
        "eta": 0.91,          # Hiệu suất thực tế ~91%
        "eta_regen": 0.55,    # Xe nhỏ, motor đơn → regen thấp hơn
        "P_aux_W": 1800,
        "motor_kw": 134,      # VF5 Plus tham chiếu
        "drive_layout": "AWD",
        # Battery pack tham chiếu cho Simulink Thevenin/OCV
        "battery_chemistry": "LFP/NMC-ref",
        "N_series": 96,
        "V_cell_full": 4.18,
        "V_cell_nom": 3.65,
        "V_cell_empty": 3.00,
        # Hàm chi phí: pin nhỏ → beta nhạy hơn để sạc đúng lúc
        "kappa_base":  1.60,
        "kappa_slope": 0.025,
        "beta_base":   13.0,      # Beta cao: mỗi kWh với VF5 là quý
        "beta_slope":  0.35,      # Tăng nhanh khi SOC xuống thấp
        "beta_thresh": 0.45,      # Kích hoạt sớm hơn
        "charge_buf":  0.08,
    },

    "VF 3": {
        "soc_max": 18.6,
        "mass_kg": 1150,
        "Cd": 0.32,
        "A": 2.0,
        "Cr": 0.013,
        "eta": 0.92,
        "eta_regen": 0.58,
        "P_aux_W": 1400,
        "motor_kw": 60,
        "drive_layout": "RWD",
        # VF3 pin nhỏ: dùng pack điện áp thấp hơn bản 400V tham chiếu.
        # Đây là tham số Digital Twin để Simulink vẽ điện áp, không làm thay đổi SOC/kWh.
        "battery_chemistry": "NMC-ref",
        "N_series": 84,
        "V_cell_full": 4.18,
        "V_cell_nom": 3.65,
        "V_cell_empty": 3.00,
        # Hàm chi phí: pin rất nhỏ → beta rất nhạy, kappa thấp nhất
        "kappa_base":  1.45,      # Xe nhỏ nhất → quán tính ít nhất
        "kappa_slope": 0.020,
        "beta_base":   15.0,      # Beta cao nhất — 1 kWh mất là rất đáng kể
        "beta_slope":  0.50,      # Tăng nhanh nhất
        "beta_thresh": 0.40,      # Kích hoạt sớm nhất (40% = 7.4 kWh)
        "charge_buf":  0.06,
    },

    # ══════════════════════════════════════════════════════════════
    # BYD — bổ sung 3 dòng phổ biến tại thị trường Việt Nam (2024-2025)
    # Cùng dùng đầu sạc CCS2 → tương thích trạm V-Green
    # ══════════════════════════════════════════════════════════════
    "BYD Atto 3": {
        "soc_max": 60.48,
        "mass_kg": 1750,
        "Cd": 0.30,
        "A": 2.50,
        "Cr": 0.012,
        "eta": 0.90,
        "eta_regen": 0.62,
        "P_aux_W": 2200,
        "motor_kw": 150,
        # Hàm chi phí: cỡ tương đương VF6/VF7 → tham chiếu theo khối lượng
        "kappa_base":  1.70,
        "kappa_slope": 0.030,
        "beta_base":   12.0,
        "beta_slope":  0.27,
        "beta_thresh": 0.48,
        "charge_buf":  0.10,
    },

    "BYD Dolphin": {
        "soc_max": 44.9,
        "mass_kg": 1430,
        "Cd": 0.29,
        "A": 2.20,
        "Cr": 0.012,
        "eta": 0.915,
        "eta_regen": 0.60,
        "P_aux_W": 1700,
        "motor_kw": 70,
        # Hàm chi phí: hatchback cỡ nhỏ → gần VF5, beta nhạy hơn vì pin nhỏ
        "kappa_base":  1.55,
        "kappa_slope": 0.024,
        "beta_base":   13.5,
        "beta_slope":  0.38,
        "beta_thresh": 0.44,
        "charge_buf":  0.08,
    },

    "BYD Seal": {
        "soc_max": 82.5,
        "mass_kg": 2055,
        "Cd": 0.219,
        "A": 2.34,
        "Cr": 0.011,
        "eta": 0.91,
        "eta_regen": 0.66,
        "P_aux_W": 2400,
        "motor_kw": 230,
        # Hàm chi phí: sedan thể thao, Cd rất thấp → kappa thấp hơn xe SUV cùng pin
        "kappa_base":  1.78,
        "kappa_slope": 0.032,
        "beta_base":   12.0,
        "beta_slope":  0.26,
        "beta_thresh": 0.50,
        "charge_buf":  0.10,
    },
}
# ==========================================
# TRAFFIC TIME-OF-DAY PROFILE CHO HÀ NỘI
# ==========================================
TRAFFIC_PROFILES = {
    "normal":       {"speed_factor": 0.88, "urban_penalty": 1.25},
    "morning_rush": {"speed_factor": 0.58, "urban_penalty": 1.85},
    "evening_rush": {"speed_factor": 0.62, "urban_penalty": 1.75},
    "night":        {"speed_factor": 1.18, "urban_penalty": 1.05},
}

DEFAULT_TIME_PERIOD = "normal"
DEFAULT_VEHICLE = "VF 8"

# ══════════════════════════════════════════════════════════════
# MOTOR SPECS — Thông số motor + truyền lực cho MATLAB co-simulation
# Tách riêng để không làm rối VEHICLE_SPECS phía trên
# ══════════════════════════════════════════════════════════════
_MOTOR_SPECS = {
    #  xe       T_max(Nm)  r_wheel(m)  n_max_rpm
    # [FIX] Cập nhật torque sát thực tế theo datasheet VinFast/BYD
    "VF 9":       (620, 0.377, 13500),  # 275/40R21 hoặc 275/45R20 → r≈0.377 m
    "VF 8":       (500, 0.364, 14000),  # VF8 AWD, 245/45R20 → r≈0.364 m
    "VF 7":       (350, 0.345, 14000),  # [FIX] CUV 200kW → ~350Nm thực tế
    "VF 6":       (310, 0.335, 16000),
    "VF MPV7":    (320, 0.345, 14000),
    "VF 5":       (190, 0.329, 15000),  # 205/55R17 → r≈0.329 m
    "VF 3":       (110, 0.334, 16000),  # 175/75R16 → r≈0.334 m
    "BYD Atto 3": (310, 0.335, 15500),
    "BYD Dolphin":(180, 0.305, 16000),
    "BYD Seal":   (360, 0.345, 15000),
}

# Merge motor specs vào VEHICLE_SPECS để truy cập đồng nhất
for _name, _spec in VEHICLE_SPECS.items():
    if _name in _MOTOR_SPECS:
        _T, _r, _n = _MOTOR_SPECS[_name]
        _spec.setdefault("torque_max_Nm",  _T)
        _spec.setdefault("wheel_radius_m", _r)
        _spec.setdefault("n_max_rpm",      _n)

_vehicle_spec   = VEHICLE_SPECS[DEFAULT_VEHICLE].copy()

# Khai báo global để các hàm khác sử dụng
SOC_CRITICAL = 0.0
SOC_WARNING  = 0.0
SOC_COMFORT  = 0.0

def set_vehicle(vehicle_name: str, ambient_temp: float = 28, ac_on: bool = True, n_passengers: int = 1):
    """
    Chọn xe và thiết lập các tham số môi trường vận hành.
    ambient_temp : nhiệt độ môi trường (độ C), ảnh hưởng cả P_aux lẫn SOC_MAX khả dụng
    ac_on        : có bật điều hòa không
    n_passengers : số hành khách (1 = chỉ tài xế)
    """
    global _vehicle_spec, SOC_MAX, SOC_CRITICAL, SOC_WARNING, SOC_COMFORT
    spec = VEHICLE_SPECS.get(vehicle_name, VEHICLE_SPECS[DEFAULT_VEHICLE])
    _vehicle_spec = spec.copy()
    _vehicle_spec["_vehicle_name"] = vehicle_name   # [NEW] Lưu tên để xuất MATLAB

    # [NEW] Lưu tham số môi trường vào spec để compute_energy dùng
    _vehicle_spec["_ambient_temp"] = ambient_temp
    _vehicle_spec["_ac_on"]        = ac_on
    _vehicle_spec["_n_passengers"] = n_passengers

    # [NEW] Áp hệ số suy giảm nhiệt vào dung lượng pin khả dụng
    thermal_factor = thermal_derate_factor(ambient_temp)
    soc_max_nominal = spec["soc_max"]
    SOC_MAX = soc_max_nominal * thermal_factor

    # Scale ngưỡng pin động theo dung lượng đã hiệu chỉnh
    SOC_CRITICAL = SOC_MAX * 0.05   # 5%
    SOC_WARNING  = SOC_MAX * 0.20   # 20%
    SOC_COMFORT  = SOC_MAX * 0.40   # 40%

    print(f"[XE]  {vehicle_name}: {soc_max_nominal}kWh nominal | "
          f"{spec['mass_kg']}kg | Cd={spec['Cd']} | motor={spec['motor_kw']}kW")
    if thermal_factor < 1.0:
        print(f"      [NHIET DO] {ambient_temp} độ C → pin khả dụng giảm còn "
              f"{SOC_MAX:.1f} kWh ({thermal_factor*100:.0f}% nominal)")
    if ac_on or n_passengers > 1:
        p_aux = P_aux_dynamic(spec, ambient_temp, ac_on, n_passengers)
        print(f"      [PHU TAI] AC={'ON' if ac_on else 'OFF'} | "
              f"{n_passengers} người | P_aux thực = {p_aux:.0f} W")


# ==========================================
# TRẠM SẠC THỰC TẾ TẠI HÀ NỘI
# ==========================================
CHARGING_STATION_INFO = {

    # ── SIÊU NHANH 300kW ─────────────────────────────────
    'VF-CoLoa': {
        'name':      'V-Green Trung tâm Triển lãm Cổ Loa, Đông Anh',
        'coord':     (21.1147, 105.8412),
        'brand':     'VinFast V-Green',
        'power_kw':  300,
        'connector': 'CCS2',
        'slots':     194,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },

    # ── DC FAST 120kW ─────────────────────────────────────
    'VF-YenVien': {
        'name':      'V-Green Yên Viên, Long Biên',
        'coord':     (21.0712, 105.9012),
        'brand':     'VinFast V-Green',
        'power_kw':  120,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     140,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-Nhon': {
        'name':      'V-Green Nhổn, Bắc Từ Liêm',
        'coord':     (21.0502, 105.7612),
        'brand':     'VinFast V-Green',
        'power_kw':  120,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     84,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-TranVy': {
        'name':      'V-Green Trần Vỹ, Cầu Giấy',
        'coord':     (21.0441, 105.7889),
        'brand':     'VinFast V-Green',
        'power_kw':  120,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     70,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-VinhomesRiverside': {
        'name':      'V-Green Vinhomes Riverside, Long Biên',
        'coord':     (21.0602, 105.9084),
        'brand':     'VinFast V-Green',
        'power_kw':  120,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     40,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-MaiLand': {
        'name':      'V-Green MaiLand Hanoi City, Đông Anh',
        'coord':     (21.1021, 105.8156),
        'brand':     'VinFast V-Green',
        'power_kw':  120,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     24,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },

    # ── DC FAST 150kW ─────────────────────────────────────
    'VF-BigCThangLong': {
        'name':      'V-Green Big C Thăng Long, 222 Trần Duy Hưng',
        'coord':     (21.0152, 105.7986),
        'brand':     'VinFast V-Green',
        'power_kw':  150,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     16,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-RoyalCity': {
        'name':      'V-Green Royal City, 72A Nguyễn Trãi, Thanh Xuân',
        'coord':     (20.9980, 105.8148),
        'brand':     'VinFast V-Green',
        'power_kw':  150,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     24,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-TimesCity': {
        'name':      'V-Green Times City, 458 Minh Khai, Hai Bà Trưng',
        'coord':     (20.9952, 105.8688),
        'brand':     'VinFast V-Green',
        'power_kw':  150,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     20,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-Metropolis': {
        'name':      'V-Green Vinhomes Metropolis, 29 Liễu Giai, Ba Đình',
        'coord':     (21.0355, 105.8193),
        'brand':     'VinFast V-Green',
        'power_kw':  150,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     18,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-SmartCity': {
        'name':      'V-Green Vinhomes Smart City, Tây Mỗ, Nam Từ Liêm',
        'coord':     (20.9978, 105.7512),
        'brand':     'VinFast V-Green',
        'power_kw':  150,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     20,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-OceanPark': {
        'name':      'V-Green Vinhomes Ocean Park, Gia Lâm',
        'coord':     (20.9892, 105.9421),
        'brand':     'VinFast V-Green',
        'power_kw':  150,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     30,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-WestPoint': {
        'name':      'V-Green Somerset West Point, 2 Tây Hồ',
        'coord':     (21.0601, 105.8312),
        'brand':     'VinFast V-Green',
        'power_kw':  150,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     12,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },
    'VF-HaDong': {
        'name':      'V-Green Hà Đông, Lê Trọng Tấn',
        'coord':     (20.9636, 105.7756),
        'brand':     'VinFast V-Green',
        'power_kw':  150,
        'connector': 'CCS2 / CHAdeMO',
        'slots':     16,
        'open_24h':  True,
        'price_vnd_kwh': 3858,
    },

    # ── AC 11kW (sạc thường tại chung cư) ─────────────────
    'VF-MyDinhPlaza': {
        'name':      'V-Green Mỹ Đình Plaza, Nam Từ Liêm',
        'coord':     (21.0257, 105.7766),
        'brand':     'VinFast V-Green',
        'power_kw':  11,
        'connector': 'Type 2 (AC)',
        'slots':     8,
        'open_24h':  False,
        'price_vnd_kwh': 3858,
    },
}

# Điểm mặc định (sẽ bị ghi đè nếu người dùng nhập)
DEFAULT_START = {
    'name':  'Hồ Hoàn Kiếm, Hà Nội',
    'coord': (21.0285, 105.8542)
}
DEFAULT_END = {
    'name':  'Hoàng Mai, Hà Nội',
    'coord': (20.9762, 105.8412)
}

# Giả lập sự cố giao thông: {bước: (từ_node, đến_node, tốc_độ_mới, mô_tả)}
TRAFFIC_EVENTS = {
    2: ('VF-TranVy', 'VF-Nhon', 5.0, 'Tai nan tren duong TranVy -> Nhon!'),
}

TRAFFIC_CACHE_TTL = 300
_traffic_cache    = {}

# ==========================================
# 1. MÔ HÌNH VẬT LÝ XE ĐIỆN
# ==========================================
def thermal_derate_factor(temp_celsius):
    """
    [NEW] Hệ số suy giảm dung lượng pin theo nhiệt độ môi trường.
    Pin Lithium-ion vận hành tối ưu 15-35 độ C.
    Lạnh sâu (<5 độ C): mất tới 22% dung lượng khả dụng (ion Li+ kém linh động).
    Nóng (>45 độ C): mất ~15% (BTMS phải làm mát + suy giảm điện hóa).

    Trả về hệ số 0.78 – 1.00 để nhân với SOC_MAX.
    """
    if 15 <= temp_celsius <= 35:
        return 1.00
    elif temp_celsius < 5:
        return 0.78
    elif temp_celsius < 15:
        # Nội suy tuyến tính 5-15 độ C
        return 0.78 + (temp_celsius - 5) * 0.022
    elif temp_celsius <= 40:
        # Nội suy 35-40 độ C
        return 1.00 - (temp_celsius - 35) * 0.020
    elif temp_celsius <= 45:
        # 40-45 độ C, suy giảm rõ rệt
        return 0.90 - (temp_celsius - 40) * 0.010
    else:
        # >45 độ C — không khuyến nghị vận hành
        return 0.85


def P_aux_dynamic(spec, ambient_temp=28, ac_on=True, n_passengers=1):
    """
    [NEW] Phụ tải phụ trợ động theo nhiệt độ môi trường và số hành khách.
    Thay thế P_aux cố định (chỉ đúng với 28 độ C, máy lạnh bật, 1 người).

    Logic:
      - Tắt điều hòa: chỉ điện tử cơ bản ~350W
      - Bật điều hòa: scale theo |delta T| so với 22 độ C mục tiêu
      - Sưởi mùa đông (<18 độ C): tốn nhiều điện hơn lạnh!
      - Mỗi hành khách thêm: +200W (cabin lớn cần làm lạnh thêm)
    """
    if not ac_on:
        return 350

    base = spec.get("P_aux_W", 2500) * 0.55  # 55% là baseline phụ tải HVAC
    target_temp = 22
    delta_T = abs(target_temp - ambient_temp)

    if ambient_temp < 18:
        # Mùa đông — sưởi (heat pump hoặc PTC) tốn điện gấp 1.5x làm lạnh
        ac_load = base + 130 * delta_T
    else:
        # Mùa hè — làm lạnh
        ac_load = base + 75 * delta_T

    passenger_load = 200 * max(0, n_passengers - 1)
    return ac_load + passenger_load


def compute_energy(dist_km, speed_kmh, grade_percent=0, delay_sec=None, time_period="normal"):
    """
    Tính năng lượng tiêu thụ (kWh) cho xe hiện tại.
    Dùng kappa_base / kappa_slope riêng của từng dòng xe thay vì hardcode.
    """
    spec  = _vehicle_spec
    m     = spec["mass_kg"]
    Cd    = spec["Cd"]
    A     = spec["A"]
    Cr    = spec["Cr"]
    eta   = spec["eta"]
    regen = spec["eta_regen"]
    # [NEW] P_aux động — đọc từ biến môi trường nếu set_vehicle đã set
    ambient_temp = _vehicle_spec.get("_ambient_temp", 28)
    ac_on        = _vehicle_spec.get("_ac_on", True)
    n_passengers = _vehicle_spec.get("_n_passengers", 1)
    P_aux        = P_aux_dynamic(spec, ambient_temp, ac_on, n_passengers)
    # [NEW] Hệ số stop-and-go riêng theo xe
    kappa_base  = spec.get("kappa_base",  1.85)
    kappa_slope = spec.get("kappa_slope", 0.035)

    g   = 9.81
    rho = 1.2

    dist_m    = dist_km * 1000
    v_ms      = max(speed_kmh / 3.6, 0.1)
    total_sec = dist_m / v_ms

    # Tách thời gian dừng / kẹt xe
    if delay_sec is None:
        stop_ratio = min(0.45, max(0.0, (35 - speed_kmh) / 35.0) * 0.45)
        delay_sec  = total_sec * stop_ratio

    drive_sec = max(total_sec - delay_sec, 1.0)
    v_cruise  = dist_m / drive_sec   # Tốc độ thực khi đang chạy

    theta   = np.arctan(grade_percent / 100.0)
    F_roll  = m * g * Cr * np.cos(theta)
    F_aero  = 0.5 * rho * Cd * A * (v_cruise ** 2)
    F_grade = m * g * np.sin(theta)
    F_total = F_roll + F_aero + F_grade

    # [FIX] Urban penalty dùng thông số riêng của xe thay vì hardcode
    urban_penalty = 1.0
    if speed_kmh < 35:
        urban_penalty = kappa_base + (35 - speed_kmh) * kappa_slope

    # Điều chỉnh theo khung giờ
    profile = TRAFFIC_PROFILES.get(time_period, TRAFFIC_PROFILES["normal"])
    urban_penalty *= profile["urban_penalty"]

    P_drive = F_total * v_cruise * urban_penalty

    if P_drive > 0:
        E_drive = (P_drive / eta) * drive_sec
    else:
        E_drive = (P_drive * regen) * drive_sec

    E_aux = P_aux * total_sec
    return (E_drive + E_aux) / 3.6e6

def update_edge_physics(graph, u, v, new_speed):
    graph[u][v]['speed']  = new_speed
    graph[u][v]['time']   = graph[u][v]['dist'] / new_speed
    graph[u][v]['energy'] = compute_energy(
        graph[u][v]['dist'], new_speed,
        graph[u][v].get('grade', 0),
        delay_sec=graph[u][v].get('delay_sec', None)
    )


def update_weights(graph, current_soc, charging_stations=None, visited_cs=None, priority="balanced"):
    """
    Cập nhật trọng số cạnh với beta thích nghi riêng theo từng dòng xe.

    Thay vì hardcode ngưỡng kWh (chỉ đúng với VF8), hàm này:
    - Normalize SOC theo SOC_MAX của xe hiện tại
    - Dùng beta_base / beta_slope / beta_thresh từ VEHICLE_SPECS
    → VF3 (18.6 kWh) và VF9 (92 kWh) sẽ có hành vi hoàn toàn khác nhau
    """
    spec         = _vehicle_spec
    beta_base    = spec.get("beta_base",   12.0)
    beta_slope   = spec.get("beta_slope",  0.25)
    beta_thresh  = spec.get("beta_thresh", 0.50)   # tỷ lệ SOC_MAX
    charge_buf   = spec.get("charge_buf",  0.10)

    # SOC normalize về [0, 1]
    soc_ratio = current_soc / max(SOC_MAX, 1.0)

    # Ngưỡng kích hoạt theo kWh thực tế của xe
    thresh_kwh = beta_thresh * SOC_MAX

    # [FIX] Beta thích nghi: tăng khi SOC xuống dưới ngưỡng đặc trưng của xe
    # VF3: beta_thresh=0.40 → kích hoạt khi SOC < 7.4 kWh
    # VF9: beta_thresh=0.55 → kích hoạt khi SOC < 50.6 kWh
    if current_soc < thresh_kwh:
        pct_below = (thresh_kwh - current_soc) / max(thresh_kwh, 1.0) * 100
        beta_adaptive = beta_base + beta_slope * pct_below
    else:
        beta_adaptive = beta_base

    # Alpha và beta_final theo priority
    if priority == "time":
        alpha      = 2.0
        beta_final = beta_adaptive * 0.50   # ít quan tâm năng lượng hơn
    elif priority == "energy":
        alpha      = 0.5
        beta_final = beta_adaptive * 2.00   # quan tâm năng lượng nhiều hơn
    else:  # balanced
        alpha      = 1.0
        beta_final = beta_adaptive

    for u, v, data in graph.edges(data=True):
        base_weight = alpha * data['time'] + beta_final * data['energy']

        charger_penalty = 0.0
        if charging_stations and (v in charging_stations):
            if visited_cs is not None and (v in visited_cs):
                charger_penalty = 9999.0                # Đã sạc → cấm tuyệt đối
            else:
                # [FIX] Ước lượng SOC sau khi đi tới v
                # Nếu SOC tại v vẫn an toàn (trên Warning + buffer) → KHÔNG cần ghé sạc
                # Nếu SOC tại v xuống thấp → mở đường vào sạc
                soc_at_v = current_soc - data.get('energy', 0)
                # Ngưỡng an toàn: Warning + buffer 5% SOC_MAX (tránh sát biên)
                safe_threshold = SOC_WARNING + 0.05 * SOC_MAX
                if soc_at_v > safe_threshold:
                    charger_penalty = 5000.0    # Pin đủ dư → né trạm sạc
                else:
                    charger_penalty = 0.0       # Pin sắp thấp → mở đường vào sạc

        data['weight'] = base_weight + charger_penalty

def get_path_energy(graph, path):
    return sum(graph[path[i]][path[i+1]]['energy'] for i in range(len(path)-1))


def is_path_feasible(graph, path, current_soc, margin=0.05):
    """Kiểm tra từng bước — phát hiện 'valley of death' độ kẹt xe."""
    soc = current_soc
    p_aux = _vehicle_spec.get('P_aux_W', 2500)
    
    for i in range(len(path)-1):
        u, v   = path[i], path[i+1]
        e_step = graph[u][v]['energy']
        delay  = graph[u][v].get('delay_sec', 0)
        
        # Thêm dự phòng kẹt xe: E_delay = (P_aux * t) / 3.6e6
        traffic_buffer = (p_aux * delay) / 3.6e6
        buf = max(margin, e_step * 0.05) + traffic_buffer
        
        if soc < e_step + buf:
            return False, f"Het pin tai {u}->{v} (delay {delay}s)"
        soc -= e_step
    return True, "OK"   


# ==========================================
# 2. TOMTOM API MODULE
# Thay thế hoàn toàn ORS — có real-time traffic thật
# ==========================================
# 1. Chỉ lấy từ biến môi trường, không để giá trị mặc định là key thật
TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY")

# 2. Nếu chạy local, thử load từ file .env
if not TOMTOM_API_KEY:
    try:
        from dotenv import load_dotenv
        load_dotenv("key/.env")
        TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")
    except ImportError:
        pass

# 3. Kiểm tra cuối cùng
if not TOMTOM_API_KEY:
    print("[LOI] Khong tim thay API Key! He thong se khong the goi du lieu giao thong.")
    TOMTOM_API_KEY = "MISSING_KEY_CHECK_YOUR_ENV"
TOMTOM_BASE_URL = "https://api.tomtom.com"
DISK_CACHE_FILE = "data/tomtom_cache.json"

# ---- Disk cache — tồn tại qua các lần chạy ----
def _load_disk_cache():
    if os.path.exists(DISK_CACHE_FILE):
        try:
            with open(DISK_CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_disk_cache(cache):
    try:
        with open(DISK_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass

_disk_cache = _load_disk_cache()


def _cache_key(coord_start, coord_end):
    return (f"{coord_start[0]:.4f},{coord_start[1]:.4f}"
            f"|{coord_end[0]:.4f},{coord_end[1]:.4f}")


def get_road_segment(coord_start, coord_end, retries=3):
    """
    TomTom Routing API — có real-time traffic thật.
    - traffic=true → travelTimeInSeconds tính cả kẹt xe
    - Disk cache để không gọi lại API khi chạy lại
    - Retry + fallback khi lỗi
    """
    key = _cache_key(coord_start, coord_end)

    # 1. Kiểm tra disk cache
    if key in _disk_cache:
        cached = _disk_cache[key]
        cached['geometry'] = [tuple(g) for g in cached['geometry']]
        return cached

    # 2. Gọi TomTom Routing API
    # Format: {lat,lng}:{lat,lng}
    locations = (f"{coord_start[0]},{coord_start[1]}"
                 f":{coord_end[0]},{coord_end[1]}")
    url    = f"{TOMTOM_BASE_URL}/routing/1/calculateRoute/{locations}/json"
    params = {
        "key":              TOMTOM_API_KEY,
        "traffic":          "true",          # ← Real-time traffic thật!
        "travelMode":       "car",
        "routeType":        "fastest",
        "computeBestOrder": "false",
    }

    for attempt in range(retries):
        try:
            time.sleep(1)   # TomTom free: 2500 req/ngày — nhẹ hơn ORS
            resp = requests.get(url, params=params, timeout=30)

            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"      [429] Rate limit! Doi {wait}s...", flush=True)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data    = resp.json()
            route   = data['routes'][0]
            summary = route['summary']

            dist_km = summary['lengthInMeters'] / 1000
            # Dùng travelTimeInSeconds (có traffic) thay vì noTrafficTravelTimeInSeconds
            dur_sec = summary['travelTimeInSeconds']
            delay_s = summary.get('trafficDelayInSeconds', 0)
            speed_kmh = dist_km / (dur_sec / 3600) if dur_sec > 0 else 30.0

            # Decode geometry từ GeoJSON
            points  = route['legs'][0]['points']
            geometry = [(p['latitude'], p['longitude']) for p in points]

            result = {
                'dist':      round(dist_km, 2),
                'speed':     round(max(speed_kmh, 5.0), 1),
                'geometry':  geometry,
                'delay_sec': delay_s,   # Thời gian delay độ traffic (giây)
            }

            # Hiển thị delay traffic nếu có
            if delay_s > 60:
                print(f"[TRAFFIC +{delay_s//60}ph] ", end='', flush=True)

            # Lưu cache
            cache_entry = result.copy()
            cache_entry['geometry'] = [list(g) for g in geometry]
            _disk_cache[key] = cache_entry
            _save_disk_cache(_disk_cache)

            return result

        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError):
            print(f"      [WARN] Timeout (lan {attempt+1}/{retries}). Thu lai...",
                  flush=True)
            time.sleep(3)
        except Exception as e:
            print(f"      [ERROR] {e}", flush=True)
            break

    # 3. Fallback đường thẳng
    print("      [FALLBACK] Dung duong thang gi lap.", flush=True)
    dx        = (coord_end[1] - coord_start[1]) * 100
    dy        = (coord_end[0] - coord_start[0]) * 111
    mock_dist = max((dx**2 + dy**2)**0.5 * 1.3, 0.5)
    return {'dist': round(mock_dist, 2), 'speed': 35.0,
            'geometry': [coord_start, coord_end], 'delay_sec': 0}


def get_realtime_traffic_speed(coord, retries=2):
    """
    TomTom Traffic Flow API — tốc độ thực tế tại điểm đang đứng.
    Dùng để cập nhật tốc độ trên từng cạnh theo thời gian thực.
    """
    url    = f"{TOMTOM_BASE_URL}/traffic/services/4/flowSegmentData/absolute/10/json"
    params = {
        "key":   TOMTOM_API_KEY,
        "point": f"{coord[0]},{coord[1]}",
    }
    for attempt in range(retries):
        try:
            time.sleep(1)
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                time.sleep(10)
                continue
            resp.raise_for_status()
            data          = resp.json()['flowSegmentData']
            current_speed = data.get('currentSpeed', None)   # km/h thực tế
            free_flow     = data.get('freeFlowSpeed', None)   # km/h không kẹt
            return current_speed, free_flow
        except Exception:
            pass
    return None, None


# Thêm bộ nhớ đệm để không gọi lại API cho các đoạn đường đã lấy độ cao
_elev_cache = {}

def get_elevation_grade(coord_start, coord_end, dist_km, retries=3):
    """
    Lấy độ dốc từ Open-Topo-Data SRTM có tích hợp Cache và chống Rate Limit 429.
    """
    return 0.0
    cache_key = f"{coord_start[0]:.4f},{coord_start[1]:.4f}|{coord_end[0]:.4f},{coord_end[1]:.4f}"
    
    # 1. Trả về ngay nếu đã có trong cache
    if cache_key in _elev_cache:
        return _elev_cache[cache_key]

    url    = "https://api.opentopodata.org/v1/srtm30m"
    params = {"locations": f"{coord_start[0]},{coord_start[1]}|{coord_end[0]},{coord_end[1]}"}
    
    for attempt in range(retries):
        try:
            # Tăng thời gian nghỉ cơ bản lên 1.2s để an toàn qua mặt server
            time.sleep(1.2)
            resp = requests.get(url, params=params, timeout=15)
            
            # Xử lý riêng lỗi 429: Chờ tăng dần 3s, 5s...
            if resp.status_code == 429:
                wait_time = 2 ** attempt + 2 
                # Có thể mở dòng in dưới đây nếu bạn muốn theo dõi nó đang chờ
                # print(f"      [ELEV 429] OpenTopoData đang bận. Đang chờ {wait_time}s...", flush=True)
                time.sleep(wait_time)
                continue
                
            resp.raise_for_status()
            results = resp.json()['results']
            elev_s  = results[0]['elevation'] or 0
            elev_e  = results[1]['elevation'] or 0
            dist_m  = max(dist_km * 1000, 1)
            grade   = ((elev_e - elev_s) / dist_m) * 100
            
            # 2. Lưu kết quả vào cache
            _elev_cache[cache_key] = round(grade, 2)
            return _elev_cache[cache_key]
            
        except Exception as e:
            if attempt == retries - 1: # Hết số lần thử nghiệm mới in ra cảnh báo
                print(f"  [WARN] Elevation fallback (grade=0) cho {coord_start}->{coord_end}")
                return 0.0
            time.sleep(2)
            
    return 0.0

def is_in_hanoi(coord):
    lat, lng = coord
    return 20.5 <= lat <= 21.5 and 105.5 <= lng <= 106.2


def geocode_address(address_text):
    """
    TomTom Fuzzy Search & Smart Alias:
    Tìm kiếm thông minh bao gồm cả POI (Sân bay, Bến xe, TTTM)
    """
    text_lower = address_text.lower()
    
    # --- 1. LỚP BẢO VỆ 1: SMART ALIASES (Tự động nhận diện địa danh lớn) ---
    aliases = {
        "nước ngầm": (20.9670, 105.8433, "Bến xe Nước Ngầm, Hoàng Mai"),
        "giáp bát":  (20.9806, 105.8422, "Bến xe Giáp Bát, Hoàng Mai"),
        "mỹ đình":   (21.0283, 105.7783, "Bến xe Mỹ Đình, Nam Từ Liêm"),
        "nội bài":   (21.2187, 105.8042, "Sân bay Quốc tế Nội Bài"),
        "hoàn kiếm": (21.0285, 105.8542, "Hồ Hoàn Kiếm, Hà Nội"),
        "lotte":     (21.0317, 105.8123, "Lotte Center, Đào Tấn, Ba Đình"),
        "aeon long biên": (21.0270, 105.9000, "Aeon Mall Long Biên"),
        "aeon hà đông":   (20.9712, 105.7790, "Aeon Mall Hà Đông"),
    }
    
    for key, data in aliases.items():
        if key in text_lower:
            print(f"      [Smart Match] Nhận diện nhanh địa danh: {data[2]}")
            return (data[0], data[1]), data[2]

    # --- 2. LỚP BẢO VỆ 2: TOMTOM FUZZY SEARCH (Tìm POI) ---
    query = address_text
    if 'hà nội' not in text_lower and 'ha noi' not in text_lower:
        query = address_text + " Hà Nội"

    print(f"      [Fuzzy Search] Đang tìm '{query}'...")
    
    # ĐỔI TỪ /geocode/ SANG /search/ (Tìm cả POI thay vì chỉ tìm Tên đường)
    url    = f"{TOMTOM_BASE_URL}/search/2/search/{requests.utils.quote(query)}.json"
    params = {
        "key":         TOMTOM_API_KEY,
        "countrySet":  "VN",
        "limit":       5,
        "lat":         21.0285,   # Bias về trung tâm Hà Nội
        "lon":         105.8542,
        "radius":      45000,     # Mở rộng bán kính 45km để quét được cả Nội Bài, Hòa Lạc
        "idxSet":      "POI,PAD,Str,Xstr,Geo", # Ưu tiên tìm POI (Point of Interest)
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get('results', [])
        
        for r in results:
            pos   = r['position']
            coord = (pos['lat'], pos['lon'])
            
            # Ưu tiên lấy tên của POI (ví dụ: "Nhà hát Lớn"), nếu không có mới lấy địa chỉ nhà
            if 'poi' in r and 'name' in r['poi']:
                name = r['poi']['name'] + ", " + r['address'].get('freeformAddress', '')
            else:
                name = r.get('address', {}).get('freeformAddress', address_text)
            
            # Cập nhật lại ranh giới bounding box (Nội Bài nằm tít ở Vĩ độ 21.22)
            if 20.8 <= coord[0] <= 21.3 and 105.7 <= coord[1] <= 106.0:
                return coord, name
                
        print("      [WARN] Không tìm thấy kết quả phù hợp trong khu vực Hà Nội.")
        return None, None
        
    except Exception as e:
        print(f"      [LOI] Lỗi API Tìm kiếm: {e}")
        return None, None


# ==========================================
# 3. XÂY DỰNG ĐỒ THỊ ĐẦY ĐỦ (Complete Graph)
# Chỉ có: Start, End, Trạm sạc — không có node trung gian
# Mỗi cặp node đều được nối trực tiếp qua ORS
# ==========================================

def haversine_distance(coord1, coord2):
    """Tính khoảng cách đường chim bay (km) cực nhanh không cần gọi API."""
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371 * 2 * math.asin(math.sqrt(a))

def build_sparse_graph(all_nodes: dict, max_radius_km: float = 15.0) -> nx.DiGraph:
    """Xây dựng đồ thị thưa: Chỉ nối các điểm gần nhau hoặc nối thẳng tới đích."""
    G = nx.DiGraph()
    nodes = list(all_nodes.keys())
    
    print(f"  [GRAPH] Đang xây dựng đồ thị thưa (Bán kính < {max_radius_km}km)...")
    
    for u in nodes:
        for v in nodes:
            if u == v:
                continue
            
            # 1. Bộ lọc Heuristic: Tính nhanh khoảng cách chim bay
            dist_est = haversine_distance(all_nodes[u]['coord'], all_nodes[v]['coord'])
            
            # 2. Điều kiện nối cạnh: Gần nhau HOẶC v là điểm đến (End)
            if dist_est <= max_radius_km or v == 'End':
                # Chỉ gọi API cho các cạnh hợp lệ
                seg = get_road_segment(all_nodes[u]['coord'], all_nodes[v]['coord'])
                if not seg:
                    continue
                    
                grade = get_elevation_grade(all_nodes[u]['coord'], all_nodes[v]['coord'], seg['dist'])
                
                G.add_edge(u, v,
                           dist=seg['dist'],
                           speed=seg['speed'],
                           grade=grade,
                           geometry=seg['geometry'],
                           delay_sec=seg.get('delay_sec', 0),
                           time=seg['dist'] / seg['speed'],
                           energy=compute_energy(seg['dist'], seg['speed'], grade, delay_sec=seg.get('delay_sec', None),
                           time_period="normal"
                          ))
    return G

def get_realtime_speed(G, u, v, all_nodes, step_count=0):
    """
    Lấy tốc độ thực tế từ TomTom Traffic Flow API.
    Có giả lập sự cố theo TRAFFIC_EVENTS để demo.
    """
    if step_count in TRAFFIC_EVENTS:
        eu, ev, espeed, edesc = TRAFFIC_EVENTS[step_count]
        if u == eu and v == ev:
            print(f"\n  [SU KIEN GIA LAP] {edesc}")
            print(f"  Toc độ {u}->{v}: {espeed} km/h")
            return espeed

    # Dùng tọa độ giữa đoạn đường để query traffic
    coord_u = all_nodes[u]['coord']
    coord_v = all_nodes[v]['coord']
    mid_coord = ((coord_u[0] + coord_v[0]) / 2,
                 (coord_u[1] + coord_v[1]) / 2)

    cache_key = f"{u}>{v}"
    now       = time.time()
    if cache_key in _traffic_cache:
        if now - _traffic_cache[cache_key]['timestamp'] < TRAFFIC_CACHE_TTL:
            return _traffic_cache[cache_key]['speed']

    # Gọi TomTom Traffic Flow API
    current_speed, free_flow = get_realtime_traffic_speed(mid_coord)

    if current_speed is not None:
        _traffic_cache[cache_key] = {'speed': current_speed, 'timestamp': now}
        return current_speed

    # Fallback: dùng tốc độ đã lưu trong graph
    return G[u][v]['speed'] if G.has_edge(u, v) else None


# ==========================================
# 4. TRAFFIC UPDATE
# ==========================================
def update_traffic(G, current_node, all_nodes, step_count):
    """
    Cập nhật tốc độ thực tế từ TomTom Traffic Flow API.
    - Cập nhật TẤT CẢ cạnh xuất phát từ current_node
    - Tính congestion ratio để hiển thị mức tắc đường
    - Cache 5 phút để không spam API
    """
    updated = []
    for u, v in list(G.out_edges(current_node)):
        new_speed = get_realtime_speed(G, u, v, all_nodes, step_count)
        if new_speed is None:
            continue
        old_speed = G[u][v]['speed']
        # Chỉ cập nhật nếu tốc độ thay đổi > 10%
        if abs(new_speed - old_speed) / max(old_speed, 1) > 0.10:
            update_edge_physics(G, u, v, new_speed)
            congestion = (1 - new_speed / max(old_speed, 1)) * 100
            level = ("TAC NANG" if congestion > 50
                     else "TAC VUA" if congestion > 20
                     else "THONG")
            updated.append((u, v, old_speed, new_speed, congestion, level))

    if updated:
        print(f"  [TRAFFIC UPDATE] {len(updated)} canh thay doi:")
        for u, v, old, new, cong, lvl in updated:
            arrow = "↓" if new < old else "↑"
            print(f"    {u:18s}->{v:18s}: "
                  f"{old:.0f}->{new:.0f}km/h {arrow} "
                  f"({cong:+.0f}% | {lvl})")


# ==========================================
# 5. ROLLING HORIZON MPC (Phiên bản hoàn thiện - Mức cao)
# ==========================================

# Ngưỡng SOC (sẽ được scale động theo xe trong set_vehicle)
SOC_CRITICAL = 0.0
SOC_WARNING  = 0.0
SOC_COMFORT  = 0.0


def soc_status(soc_kwh):
    """Trả về mức độ SOC"""
    pct = soc_kwh / SOC_MAX * 100
    if soc_kwh <= SOC_CRITICAL:
        return 'CRITICAL', '[!!!]', f'{pct:.1f}% — KHẨN CẤP, SẠC NGAY!'
    elif soc_kwh <= SOC_WARNING:
        return 'WARNING', '[!]', f'{pct:.1f}% — Cảnh báo thấp'
    elif soc_kwh <= SOC_COMFORT:
        return 'LOW', '[ ]', f'{pct:.1f}% — Khá thấp'
    else:
        return 'OK', '[OK]', f'{pct:.1f}% — Bình thường'


def get_charge_power_at_soc(soc_pct, max_power_kw):
    """
    [NEW] Đường cong sạc DC phi tuyến — giống thực tế EV.
    Pin Lithium-ion KHÔNG sạc tuyến tính: từ 0-50% sạc nhanh, sau 80% chậm hẳn (tapering).
    soc_pct: tỉ lệ SOC hiện tại (0.0–1.0)
    Trả về công suất sạc thực tế tại thời điểm đó (kW).
    """
    if soc_pct < 0.10:
        # Giai đoạn precondition (làm ấm pin) — giảm công suất
        return max_power_kw * 0.70
    elif soc_pct < 0.20:
        # Đang tăng dần đến peak
        return max_power_kw * 0.90
    elif soc_pct < 0.50:
        # Đỉnh sạc — full power
        return max_power_kw * 1.00
    elif soc_pct < 0.70:
        # Bắt đầu tapering nhẹ
        return max_power_kw * 0.80
    elif soc_pct < 0.80:
        # Tapering mạnh
        return max_power_kw * 0.60
    elif soc_pct < 0.90:
        # Tapering rất mạnh — bảo vệ pin
        return max_power_kw * 0.35
    else:
        # Sạc nhỏ giọt — tránh hỏng pin
        return max_power_kw * 0.18


def get_charge_time_min(station_key, soc_current, soc_target=None):
    """
    Tính thời gian sạc TÍCH PHÂN qua đường cong phi tuyến thay vì tuyến tính.
    Cách cũ: t = ΔSOC / P_max  → underestimate ~25-30% với DC fast.
    Cách mới: chia thành các bước nhỏ ΔSOC = 1%, dùng P(SOC) tại mỗi bước.
    """
    if soc_target is None:
        soc_target = SOC_MAX
    info = CHARGING_STATION_INFO.get(station_key, {})
    max_power_kw = info.get('power_kw', 50)
    energy_need = max(0, soc_target - soc_current)
    if energy_need < 0.01:
        return 0.0

    # Tích phân theo bước 1% SOC
    step_kwh = SOC_MAX * 0.01  # mỗi bước = 1% dung lượng pin của xe đang chọn
    total_hours = 0.0
    soc = soc_current
    while soc < soc_target:
        soc_pct = soc / SOC_MAX
        p_now = get_charge_power_at_soc(soc_pct, max_power_kw)
        # Trạm AC ≤ 22 kW không bị tapering nghiêm trọng → bỏ qua đường cong
        if max_power_kw <= 22:
            p_now = max_power_kw
        delta = min(step_kwh, soc_target - soc)
        total_hours += delta / max(p_now, 1.0)
        soc += delta

    return round(total_hours * 60, 1)


def find_best_charger(G, current, charging_stations, visited_cs, SOC):
    """Tìm trạm sạc. Có chế độ tuyệt vọng (Desperation Mode) khi pin quá kiệt."""
    reachable = []
    for s in charging_stations:
        if s in visited_cs or not nx.has_path(G, current, s):
            continue
        try:
            # Tìm đường tốn ÍT PIN NHẤT để đến trạm (thay vì đường nhanh nhất)
            p2s = nx.dijkstra_path(G, current, s, weight='energy')
            cost_energy = nx.path_weight(G, p2s, weight='energy')
            power = CHARGING_STATION_INFO.get(s, {}).get('power_kw', 50)
            
            # Kiểm tra xem pin hiện tại có đủ lết tới không (hạ margin cực nhỏ)
            safe, _ = is_path_feasible(G, p2s, SOC, margin=0.01)
            reachable.append((s, p2s, cost_energy, power, safe))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue

    if not reachable:
        return None, None

    # 1. Ưu tiên các trạm "An toàn" (chắc chắn đến được)
    safe_stations = [x for x in reachable if x[4]]
    if safe_stations:
        # Tối ưu: Chọn trạm cân bằng giữa Năng lượng cần đi và Công suất sạc
        best = min(safe_stations, key=lambda x: x[2] - 0.01 * x[3])
        return best[0], best[1]
    
    # 2. Không có trạm nào có thể tiếp cận an toàn.
    # Tuyệt đối không trả về một tuyến "lết tới" không khả thi, vì điều đó
    # khiến mô phỏng trừ SOC xuống âm rồi vẫn ghi nhận hành trình hoàn thành.
    print("  [INFEASIBLE] Không có trạm sạc nào nằm trong phạm vi pin hiện tại.")
    return None, None

def find_horizon_path(G, current, end_node, horizon, current_soc, 
                      charging_stations=None, visited_cs=None, 
                      priority="balanced", all_nodes=None):
    """
    Tìm đường tối ưu trong horizon bước tới bằng Rolling Horizon MPC.
    - Ưu tiên dùng A* với heuristic khoảng cách chim bay.
    - Áp dụng đầy đủ penalty trạm sạc.
    - Trả về horizon_path an toàn nhất có thể.
    """
    try:
        # Cập nhật trọng số (bao gồm penalty trạm sạc)
        update_weights(G, current_soc, charging_stations, visited_cs, priority=priority)

        # === TÌM ĐƯỜNG TỐI ƯU ===
        if all_nodes is not None:
            try:
                # A* với heuristic haversine (nhanh và hiệu quả)
                path = nx.astar_path(
                    G, current, end_node, weight='weight',
                    heuristic=lambda u, v: haversine_distance(
                        all_nodes[u]['coord'], all_nodes[v]['coord']
                    ) * 0.75
                )
            except (nx.NetworkXNoPath, nx.NodeNotFound, KeyError):
                # Fallback về Dijkstra nếu A* lỗi
                path = nx.dijkstra_path(G, current, end_node, weight='weight')
        else:
            path = nx.dijkstra_path(G, current, end_node, weight='weight')

        # Cắt theo horizon
        horizon_path = path[:horizon + 1] if len(path) > horizon + 1 else path

        # Kiểm tra tính khả thi pin trong horizon
        feasible, msg = is_path_feasible(G, horizon_path, current_soc, margin=0.12)

        if feasible:
            return horizon_path
        else:
            # Nếu không an toàn → rút ngắn horizon và thử lại
            print(f"  [HORIZON] Đường dự báo không an toàn: {msg}. Rút ngắn horizon.")
            short_path = path[:min(horizon//2 + 2, len(path))]
            return short_path if len(short_path) >= 2 else path[:2]

    except Exception as e:
        print(f"  [HORIZON ERROR] Không tìm được đường trong horizon: {e}")
        # Fallback cuối cùng: chỉ lấy 2 bước gần nhất
        try:
            return nx.dijkstra_path(G, current, end_node, weight='weight')[:2]
        except:
            return None


def remaining_energy_to_destination(G, current, end_node):
    """
    Tính đường còn lại tối thiểu theo năng lượng từ vị trí hiện tại tới đích.
    Dùng để quyết định có thật sự cần sạc hay chỉ cần cảnh báo SOC thấp.
    """
    try:
        path = nx.dijkstra_path(G, current, end_node, weight='energy')
        e_rem = nx.path_weight(G, path, weight='energy')
        d_rem = sum(G[path[i]][path[i+1]].get('dist', 0.0)
                    for i in range(len(path)-1))
        return path, e_rem, d_rem
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None, float('inf'), float('inf')


def should_charge_here(G, current, end_node, SOC, allow_charging=True):
    """
    Logic sạc mới: Warning/Low chỉ cảnh báo, không tự ép sạc.
    Chỉ sạc nếu đường còn lại không khả thi hoặc SOC dự báo tại đích thấp hơn
    reserve an toàn. Đặc biệt, với quãng còn lại <= 15 km và vẫn tới đích được,
    bỏ qua sạc để tránh lỗi tuyến ngắn bị dừng AC nhiều giờ.
    """
    if not allow_charging:
        return False, 'charging disabled by user'

    if SOC >= SOC_COMFORT:
        return False, 'SOC above Comfort threshold'

    rem_path, e_rem, d_rem = remaining_energy_to_destination(G, current, end_node)
    if rem_path is None:
        return True, 'no feasible path to destination without charging'

    # Kiểm tra feasibility theo năng lượng còn lại.
    feasible, msg = is_path_feasible(G, rem_path, SOC, margin=0.03)
    soc_end_pred = SOC - e_rem

    # Reserve để kết thúc hành trình: không dùng Warning=20% làm điều kiện ép sạc,
    # vì Warning chỉ là cảnh báo. Dùng mốc an toàn mềm ~10% hoặc Critical.
    reserve_kwh = max(SOC_CRITICAL, 0.10 * SOC_MAX, 0.20)

    # Nếu còn rất gần đích và vẫn không cạn pin thì không sạc, dù SOC đang LOW/WARNING.
    if d_rem <= 15.0 and soc_end_pred > SOC_CRITICAL:
        return False, (f'short remaining path {d_rem:.1f} km; '
                       f'predicted final SOC {soc_end_pred:.2f} kWh > Critical')

    if (not feasible) or soc_end_pred < reserve_kwh:
        return True, (f'predicted final SOC {soc_end_pred:.2f} kWh below reserve '
                      f'{reserve_kwh:.2f} kWh; {msg}')

    return False, (f'destination still feasible: {d_rem:.1f} km, '
                   f'E_rem={e_rem:.2f} kWh, final SOC={soc_end_pred:.2f} kWh')


def run_simulation(G, all_nodes, start_node, end_node, charging_stations, 
                   soc_init, priority="balanced", horizon=5, max_soc_pct=92, allow_charging=True):
    """
    Rolling Horizon MPC với tùy chọn mức sạc tối đa
    """
    """
    Rolling Horizon MPC hoàn thiện.
    [FIX] Trả về charge_times_sec để export_matlab/summary dùng.
    """
    current    = start_node
    visited_cs = set()
    charged_cs = set()    # [NEW] Tách riêng: chỉ chứa trạm THẬT SỰ sạc
    SOC        = soc_init
    path_taken = [current]
    soc_history      = [soc_init]
    speed_log        = []
    charge_times_sec = []   # [FIX] Danh sách thời gian sạc (giây) mỗi lần dừng
    steps = 0

    # Trạng thái kết thúc hành trình. Chỉ được đánh dấu hoàn thành khi
    # current == end_node; việc vòng lặp dừng do hết pin/không có đường
    # không được coi là hoàn thành.
    trip_completed = False
    failure_reason = ""
    failure_node = None

    print(f"\n=== ROLLING HORIZON MPC START ===")
    print(f"Horizon: {horizon} bước | Ưu tiên: {priority.upper()}")
    level, icon, desc = soc_status(SOC)
    print(f"SOC khởi đầu: {SOC:.2f} kWh {icon} {desc}\n")

    while current != end_node and steps < MAX_STEPS:
        steps += 1
        update_traffic(G, current, all_nodes, steps)
        update_weights(G, SOC, charging_stations, visited_cs, priority)

        # Rolling Horizon — [FIX] truyền all_nodes tường minh
        horizon_path = find_horizon_path(
            G, current, end_node, horizon, SOC, 
            charging_stations, visited_cs, priority,
            all_nodes=all_nodes
        )

        if horizon_path and len(horizon_path) >= 2:
            next_node = horizon_path[1]
        else:
            # Fallback Dijkstra
            try:
                best_path = nx.dijkstra_path(G, current, end_node, weight='weight')
                next_node = best_path[1]
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                failure_reason = "Không tìm thấy đường từ vị trí hiện tại tới điểm đến."
                failure_node = current
                print(f"  [INFEASIBLE] {failure_reason}")
                break

        # Kiểm tra an toàn pin TRƯỚC KHI di chuyển. Không cho phép trừ SOC
        # xuống âm rồi mới phát hiện hết pin.
        energy_step = G[current][next_node]['energy']
        delay_step = G[current][next_node].get('delay_sec', 0)
        p_aux_now = P_aux_dynamic(
            _vehicle_spec,
            _vehicle_spec.get('_ambient_temp', 28),
            _vehicle_spec.get('_ac_on', True),
            _vehicle_spec.get('_n_passengers', 1),
        )
        traffic_buffer = (p_aux_now * delay_step) / 3.6e6
        move_buffer = max(0.01, energy_step * 0.05) + traffic_buffer

        if SOC < energy_step + move_buffer:
            if allow_charging:
                station, path_to_cs = find_best_charger(
                    G, current, charging_stations, visited_cs, SOC
                )
                if station is not None and path_to_cs is not None and len(path_to_cs) >= 2:
                    next_node = path_to_cs[1]
                    energy_step = G[current][next_node]['energy']
                    delay_step = G[current][next_node].get('delay_sec', 0)
                    traffic_buffer = (p_aux_now * delay_step) / 3.6e6
                    move_buffer = max(0.01, energy_step * 0.05) + traffic_buffer
                    print(f"  [SAFETY] Chuyển hướng đến trạm sạc khả thi: {station}")
                else:
                    failure_reason = (
                        f"Pin còn {SOC:.3f} kWh, không đủ tới điểm tiếp theo "
                        f"và không có trạm sạc nào tiếp cận an toàn."
                    )
                    failure_node = current
                    print(f"  [INFEASIBLE] {failure_reason}")
                    break
            else:
                failure_reason = (
                    f"Pin còn {SOC:.3f} kWh, cần ít nhất "
                    f"{energy_step + move_buffer:.3f} kWh để đi tiếp; "
                    "người dùng đã tắt tùy chọn dừng sạc."
                )
                failure_node = current
                print(f"  [INFEASIBLE] {failure_reason}")
                break

        # Kiểm tra lần cuối sau khi có thể đã đổi hướng sang trạm sạc.
        if SOC < energy_step + move_buffer:
            failure_reason = (
                f"Không đủ pin để đi từ {current} tới {next_node}: "
                f"SOC={SOC:.3f} kWh, yêu cầu an toàn={energy_step + move_buffer:.3f} kWh."
            )
            failure_node = current
            print(f"  [INFEASIBLE] {failure_reason}")
            break

        # Di chuyển chỉ khi cạnh tiếp theo khả thi.
        speed_log.append(G[current][next_node]['speed'])
        SOC -= energy_step
        SOC = max(0.0, min(SOC, SOC_MAX))

        current = next_node
        path_taken.append(current)
        soc_history.append(SOC)

        level, icon, desc = soc_status(SOC)
        dist_step = G[path_taken[-2]][current]['dist']
        print(f"  Bước {steps:2d}: {path_taken[-2]:15s} → {current:15s} | "
              f"{dist_step:5.1f}km | -{energy_step:.3f}kWh | SOC = {SOC:.2f} {icon}")

        if SOC <= 0:
            failure_reason = "Pin đã cạn trước khi tới điểm đến."
            failure_node = current
            print(f"  [INFEASIBLE] {failure_reason}")
            break

        # ==================== SAC PIN TAI TRAM ====================
        if current in charging_stations and current not in visited_cs:
            do_charge, charge_reason = should_charge_here(
                G, current, end_node, SOC, allow_charging=allow_charging
            )

            if do_charge:
                info = CHARGING_STATION_INFO.get(current, {})
                
                # Sử dụng mức sạc tối đa từ web_app (mặc định 92%)
                soc_target_pct = max_soc_pct / 100.0
                SOC_TARGET = SOC_MAX * soc_target_pct
                
                t_min = get_charge_time_min(current, SOC, SOC_TARGET)
                
                print(f"\n  {'─'*55}")
                print(f"  [SẠC PIN] {info.get('brand','V-Green')} — {info.get('name', current)}")
                print(f"            Lý do     : {charge_reason}")
                print(f"            Công suất : {info.get('power_kw', '?')} kW")
                print(f"            SOC       : {SOC:.2f} kWh → {SOC_TARGET:.1f} kWh ({soc_target_pct*100:.0f}%)")
                print(f"            Thời gian : ~{t_min:.1f} phút")
                print(f"  {'─'*55}\n")
                
                SOC = SOC_TARGET
                soc_history[-1] = SOC
                visited_cs.add(current)
                charged_cs.add(current)    # [NEW] Đánh dấu trạm THẬT SỰ sạc
                charge_times_sec.append(int(t_min * 60))
                
            else:
                print(f"  [SKIP] Di qua {current} (SOC = {SOC/SOC_MAX*100:.0f}% — {charge_reason})")
                visited_cs.add(current)
    # Chỉ hoàn thành khi node hiện tại thật sự là End.
    trip_completed = (current == end_node and SOC > 0)
    if not trip_completed and not failure_reason:
        if steps >= MAX_STEPS:
            failure_reason = f"Vượt quá giới hạn {MAX_STEPS} bước trước khi tới điểm đến."
        else:
            failure_reason = "Hành trình dừng trước khi tới điểm đến."
        failure_node = current

    n_charged_print = len(charged_cs)
    if trip_completed:
        print("\n=== HOÀN THÀNH HÀNH TRÌNH ===")
    else:
        print("\n=== HÀNH TRÌNH KHÔNG HOÀN THÀNH ===")
        print(f"Lý do: {failure_reason}")
        print(f"Dừng tại: {failure_node or current} | SOC còn: {SOC:.3f} kWh")

    # Phân biệt rõ "đi qua" vs "thực sự sạc"
    if n_charged_print == 0:
        print(f"Lộ trình thực tế: {' → '.join(path_taken)}  (KHÔNG dừng sạc)")
    else:
        marked = [f"⚡{n}" if n in charged_cs else n for n in path_taken]
        print(f"Lộ trình thực tế: {' → '.join(marked)}")
    print(f"Số bước: {steps} | Sạc thực: {n_charged_print} lần | "
          f"Đi qua (không sạc): {len(visited_cs) - n_charged_print} trạm")

    trip_result = {
        "completed": trip_completed,
        "status": "completed" if trip_completed else "infeasible",
        "failure_reason": failure_reason,
        "stopped_at": current,
        "steps": steps,
    }

    return (path_taken, visited_cs, charged_cs, soc_history,
            speed_log, charge_times_sec, trip_result)


# ==========================================
# 6. XUất file MATLAB (Phiên bản hoàn thiện - Mức cao)
# ==========================================

def export_matlab(path_taken, soc_history, speed_log, G, charge_times_sec):
    import numpy as np
    time_vector, speed_vector, grade_vector, lat_vector, lon_vector = [0.0], [], [], [], []
    soc_vector = [soc_history[0]]
    charge_idx = 0 

    # ── [FIX] Thời gian giảm tốc mượt trước khi dừng sạc (giây) ──
    DECEL_RAMP_SEC = 15   # 15 giây giảm tốc từ v_cruise → 0

    for i, (u, v) in enumerate(zip(path_taken, path_taken[1:])):
        data     = G[u][v]
        dist_m   = data['dist'] * 1000
        speed_ms = data['speed'] / 3.6
        grade    = data.get('grade', 0.0)
        dur_sec  = max(1, int(dist_m / speed_ms if speed_ms > 0 else 0))
        
        soc_start = soc_vector[-1]
        soc_target = soc_history[i+1]
        
        # SỬA LOGIC: Kiểm tra sạc dựa trên soc khi TỚI TRẠM (soc_arrival)
        soc_arrival = max(0.1, soc_start - data['energy'])
        is_charging_at_v = ('VF-' in str(v)) and (soc_target > soc_arrival + 0.1)
        
        # 1.1 Nội suy Tọa độ
        geom_lats = [p[0] for p in data['geometry']]
        geom_lons = [p[1] for p in data['geometry']]
        orig_indices = np.linspace(0, 1, len(geom_lats))
        new_indices  = np.linspace(0, 1, dur_sec)
        
        lat_vector.extend(np.interp(new_indices, orig_indices, geom_lats).tolist())
        lon_vector.extend(np.interp(new_indices, orig_indices, geom_lons).tolist())

        # ── [FIX] Pha xe đang chạy — có ramp giảm tốc nếu sắp dừng sạc ──
        if is_charging_at_v and dur_sec > DECEL_RAMP_SEC:
            # Pha chạy ổn định (cruise)
            cruise_sec = dur_sec - DECEL_RAMP_SEC
            for _ in range(cruise_sec):
                speed_vector.append(data['speed'])
                grade_vector.append(grade)
                time_vector.append(time_vector[-1] + 1.0)
            # Pha giảm tốc mượt (cosine ramp: tự nhiên hơn linear)
            for k in range(DECEL_RAMP_SEC):
                ratio = 0.5 * (1 + np.cos(np.pi * k / DECEL_RAMP_SEC))  # 1 → 0
                speed_vector.append(max(0.0, data['speed'] * ratio))
                grade_vector.append(grade)
                time_vector.append(time_vector[-1] + 1.0)
        else:
            # Pha chạy bình thường (không sạc, hoặc đoạn quá ngắn)
            for _ in range(dur_sec):
                speed_vector.append(data['speed'])
                grade_vector.append(grade)
                time_vector.append(time_vector[-1] + 1.0)

        soc_vector.extend(np.linspace(soc_start, soc_arrival, dur_sec).tolist())

        # 1.3 Pha dừng sạc tại trạm
        if is_charging_at_v and charge_idx < len(charge_times_sec):
            actual_charge_sec = charge_times_sec[charge_idx]
            charge_idx += 1
            
            for _ in range(actual_charge_sec):
                speed_vector.append(0.0)
                grade_vector.append(0.0)
                time_vector.append(time_vector[-1] + 1.0)
                lat_vector.append(lat_vector[-1])
                lon_vector.append(lon_vector[-1])
            
            soc_vector.extend(np.linspace(soc_arrival, soc_target, actual_charge_sec).tolist())

    # ── [FIX] Clamp toàn bộ speed_vector ≥ 0 phòng lỗi số ──
    speed_vector = [max(0.0, s) for s in speed_vector]

    n = min(len(time_vector) - 1, len(speed_vector), len(grade_vector), len(soc_vector), len(lat_vector), len(lon_vector))

    # [NEW] Đóng gói spec xe cho MATLAB co-simulation (Cấp 3)
    spec = _vehicle_spec

    # ── [FIX] Điện áp pack lấy theo Digital Twin của từng xe ──
    # Không suy luận N_series chỉ từ dung lượng pin, vì dung lượng kWh phụ thuộc cả số cell song song.
    # Nếu xe chưa có thông số riêng thì fallback về kiến trúc 400V tham chiếu 96S.
    N_series = int(spec.get('N_series', 96))
    V_cell_full  = float(spec.get('V_cell_full', 4.18))
    V_cell_nom   = float(spec.get('V_cell_nom', 3.65))
    V_cell_empty = float(spec.get('V_cell_empty', 3.00))
    drive_layout = spec.get('drive_layout', 'unknown')

    vehicle_specs_for_mat = {
        'name':           spec.get('_vehicle_name', DEFAULT_VEHICLE),
        'mass_kg':        float(spec['mass_kg']),
        'Cd':             float(spec['Cd']),
        'A':              float(spec['A']),
        'Cr':             float(spec['Cr']),
        'eta':            float(spec['eta']),
        'eta_regen':      float(spec['eta_regen']),
        'P_aux_W':        float(spec.get('P_aux_W', 2500)),
        'motor_kw':       float(spec.get('motor_kw', 150)),
        'drive_layout':   drive_layout,
        'battery_chemistry': spec.get('battery_chemistry', 'NMC'),
        'torque_max_Nm':  float(spec.get('torque_max_Nm', 310)),
        'wheel_radius_m': float(spec.get('wheel_radius_m', 0.345)),
        'n_max_rpm':      float(spec.get('n_max_rpm', 15000)),
        'soc_max_kwh':    float(SOC_MAX),
        'soc_critical':   float(SOC_CRITICAL),
        'soc_warning':    float(SOC_WARNING),
        'soc_comfort':    float(SOC_COMFORT),
        # ── [NEW] Thông số pin cho MATLAB Thevenin model ──
        'N_series':       float(N_series),       # Số cell nối tiếp
        'V_cell_full':    V_cell_full,             # V/cell tại SOC=100%
        'V_cell_nom':     V_cell_nom,              # V/cell danh định
        'V_cell_empty':   V_cell_empty,            # V/cell tại SOC=0%
    }

    mat_data = {
        'drive_cycle': {
            'time':  np.array(time_vector[:n]), 'speed': np.array(speed_vector[:n]),
            'grade': np.array(grade_vector[:n]), 'soc':   np.array(soc_vector[:n]),
            'lat':   np.array(lat_vector[:n]), 'lon':   np.array(lon_vector[:n]),
            'route': np.array(path_taken, dtype=object),
        },
        'vehicle_specs': vehicle_specs_for_mat,
    }
    sio.savemat('results/DriveCycle_Data.mat', mat_data)
    safe_vehicle = str(vehicle_specs_for_mat['name']).replace(' ', '_').replace('/', '_')
    sio.savemat(f'results/DriveCycle_Data_{safe_vehicle}.mat', mat_data)
    print(f"[INFO] Đã xuất MATLAB file (xe: {vehicle_specs_for_mat['name']}, "
          f"pin {vehicle_specs_for_mat['soc_max_kwh']:.1f} kWh, "
          f"motor {vehicle_specs_for_mat['motor_kw']:.0f} kW, "
          f"pack {N_series}S × {vehicle_specs_for_mat['V_cell_nom']:.2f}Vnom / {vehicle_specs_for_mat['V_cell_full']:.2f}Vmax)")

def print_summary(path_taken, soc_history, visited_cs, G, charge_times_sec, trip_result=None):
    pairs        = list(zip(path_taken, path_taken[1:]))
    total_dist   = sum(G[u][v]['dist']   for u, v in pairs)
    total_energy = sum(G[u][v]['energy'] for u, v in pairs)
    total_time_h = sum(G[u][v]['time']   for u, v in pairs)
    avg_speed    = total_dist / total_time_h if total_time_h > 0 else 0
    efficiency   = total_energy / total_dist * 100 if total_dist > 0 else 0
    actual_stops = len(charge_times_sec)

    trip_result = trip_result or {"completed": path_taken[-1] == "End"}
    completed = bool(trip_result.get("completed", False))

    print("\n" + "=" * 58)
    print("  TOM TAT HANH TRINH" if completed else "  HANH TRINH KHONG HOAN THANH")
    print("=" * 58)
    print(f"  Trang thai      : {'DA TOI DICH' if completed else 'KHONG KHA THI'}")
    if not completed:
        print(f"  Ly do           : {trip_result.get('failure_reason', 'Khong ro')}")
        print(f"  Dung tai        : {trip_result.get('stopped_at', path_taken[-1])}")
    print(f"  Lo trinh       : {' -> '.join(path_taken)}")
    print(f"  Tong quang duong: {total_dist:.1f} km")
    print(f"  Tong thoi gian  : {total_time_h*60:.0f} phut ({total_time_h:.2f} gio)")
    print(f"  Hieu suat       : {efficiency:.2f} kWh/100km")
    print(f"  So lan sac      : {actual_stops}")
    if actual_stops > 0:
        print("  Chi tiet tram sac:")
        for i, s in enumerate(visited_cs):
            info  = CHARGING_STATION_INFO.get(s, {})
            actual_charge_min = charge_times_sec[i] / 60.0
            print(f"    - {info.get('name', s)}")
            print(f"      {info.get('brand','?')} | {info.get('power_kw','?')}kW | Sạc {actual_charge_min:.1f} phút")
    print("=" * 58)

def export_summary(path_taken, soc_history, visited_cs, G, start_info, end_info, charge_times_sec, trip_result=None):
    pairs = list(zip(path_taken, path_taken[1:]))
    total_dist   = sum(G[u][v]['dist']   for u, v in pairs)
    total_energy = sum(G[u][v]['energy'] for u, v in pairs)
    total_time_h = sum(G[u][v]['time']   for u, v in pairs)
    total_charge_min = sum(charge_times_sec) / 60.0 if charge_times_sec else 0.0

    # Tên xe hiện tại. _vehicle_spec là bản copy nên không dùng so sánh identity.
    current_vehicle = _vehicle_spec.get("_vehicle_name", DEFAULT_VEHICLE)
    trip_result = trip_result or {
        "completed": path_taken[-1] == "End",
        "status": "completed" if path_taken[-1] == "End" else "infeasible",
        "failure_reason": "",
        "stopped_at": path_taken[-1],
    }

    stopped_node = trip_result.get("stopped_at", path_taken[-1])
    if stopped_node == "Start":
        stopped_name = start_info["name"]
    elif stopped_node == "End":
        stopped_name = end_info["name"]
    else:
        stopped_name = CHARGING_STATION_INFO.get(stopped_node, {}).get("name", stopped_node)

    trip_completed = bool(trip_result.get("completed", False))
    status_message = (
        "Hành trình đã hoàn thành và xe đã tới điểm đến."
        if trip_completed
        else "Hành trình dừng trước khi tới điểm đến."
    )

    summary = {
        # Trạng thái hành trình — web app phải đọc trường này trước khi hiển thị thành công
        "trip_completed":     trip_completed,
        "trip_status":        trip_result.get("status", "infeasible"),
        "status_message":     status_message,
        "failure_reason":     trip_result.get("failure_reason", ""),
        "stopped_at":         stopped_node,
        "stopped_name":       stopped_name,
        # Thông tin hành trình
        "start_name":          start_info['name'],
        "end_name":            end_info['name'],
        "route":               path_taken,
        "total_dist_km":       round(total_dist, 2),
        "total_time_min":      round(total_time_h * 60, 1),
        "total_energy_kwh":    round(total_energy, 4),
        "efficiency_kwh100km": round(total_energy / max(total_dist, 0.1) * 100, 3),
        # Thông tin pin — [FIX] thêm để web_app tính % đúng theo xe
        "vehicle":             current_vehicle,
        "soc_max_kwh":         SOC_MAX,
        "soc_init_kwh":        round(soc_history[0], 3),
        "soc_final_kwh":       round(soc_history[-1], 3),
        "soc_final_pct":       round(soc_history[-1] / SOC_MAX * 100, 1),
        # [FIX] Thêm toàn bộ soc_history để web_app vẽ chart khi không có PNG
        "soc_history":         [round(s, 4) for s in soc_history],
        # Thông tin sạc
        "n_charging_stops":    len(charge_times_sec),
        "charging_stops":      list(visited_cs),
        "total_charge_min":    round(total_charge_min, 1),
        # Chi tiết từng đoạn
        "segments": [
            {
                "from":       u,
                "to":         v,
                "dist_km":    round(G[u][v]['dist'],   2),
                "speed_kmh":  round(G[u][v]['speed'],  1),
                "energy_kwh": round(G[u][v]['energy'], 4),
            }
            for u, v in pairs
        ]
    }
    with open("data/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("[INFO] Da xuat: summary.json")

# ==========================================
# 7. TRỰC QUAN HÓA
# ==========================================
def visualize(G, all_nodes, path_taken, visited_cs,
              charging_stations, soc_history, start_node, end_node,
              charged_cs=None):
    # Fallback nếu không truyền charged_cs (backward-compat)
    if charged_cs is None:
        charged_cs = visited_cs

    def positions_in_path(node):
        return [i+1 for i, n in enumerate(path_taken) if n == node]

    pos = {n: (loc['coord'][1], loc['coord'][0])
           for n, loc in all_nodes.items() if n in G.nodes}

    # ---- PNG ----
    fig, axes = plt.subplots(1, 2, figsize=(20, 9))
    ax = axes[0]
    ax.set_facecolor('#f0f4f8')
    fig.patch.set_facecolor('#f0f4f8')

    # Vẽ tất cả cạnh mờ
    nx.draw_networkx_edges(G, pos, edge_color='#d0d0d0', arrows=True,
                           arrowstyle='->', alpha=0.35, width=1.0, ax=ax,
                           connectionstyle='arc3,rad=0.08')

    # Màu node
    node_colors, node_sizes = [], []
    for node in G.nodes:
        if node == start_node:
            node_colors.append('#1565C0'); node_sizes.append(1400)
        elif node == end_node:
            node_colors.append('#B71C1C'); node_sizes.append(1400)
        elif node in visited_cs:
            node_colors.append('#E65100'); node_sizes.append(1200)
        elif node in charging_stations:
            info = CHARGING_STATION_INFO.get(node, {})
            node_colors.append('#6A1B9A' if info.get('power_kw', 0) >= 100
                               else '#F9A825')
            node_sizes.append(1200)
        else:
            node_colors.append('#546E7A'); node_sizes.append(1000)

    nx.draw_networkx_nodes(G, pos, node_color=node_colors,
                           node_size=node_sizes, ax=ax, alpha=0.92)

    # Label
    labels = {}
    for n in G.nodes:
        if n in CHARGING_STATION_INFO:
            info     = CHARGING_STATION_INFO[n]
            labels[n] = f"{info['brand']}\n{info['power_kw']}kW"
        else:
            labels[n] = n
    nx.draw_networkx_labels(G, pos, labels=labels,
                            font_size=6.5, font_color='white',
                            font_weight='bold', ax=ax)

    # Vẽ lộ trình thực tế (xanh đậm, nổi bật)
    path_edges = list(zip(path_taken, path_taken[1:]))
    nx.draw_networkx_edges(G, pos, edgelist=path_edges,
                           edge_color='#00C853', width=5, arrows=True,
                           ax=ax, connectionstyle='arc3,rad=0.08')

    # Số bước
    for i, (u, v) in enumerate(path_edges, 1):
        mx = (pos[u][0] + pos[v][0]) / 2
        my = (pos[u][1] + pos[v][1]) / 2
        d  = G[u][v]
        ax.annotate(f"B{i}\n{d['dist']}km\n{d['energy']:.2f}kWh",
                    (mx, my), fontsize=6.5, color='#1B5E20', fontweight='bold',
                    ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.3', fc='white',
                              alpha=0.85, ec='#00C853', lw=0.8))

    ax.legend(handles=[
        mpatches.Patch(color='#1565C0', label=f'Xuat phat ({start_node})'),
        mpatches.Patch(color='#B71C1C', label=f'Dich ({end_node})'),
        mpatches.Patch(color='#6A1B9A', label='Tram DC Fast (>=100kW)'),
        mpatches.Patch(color='#F9A825', label='Tram AC (22kW)'),
        mpatches.Patch(color='#E65100', label='Tram da sac'),
        mlines.Line2D([0], [0], color='#00C853', lw=3, label='Lo trinh MPC'),
    ], loc='upper left', fontsize=8, framealpha=0.92, edgecolor='#ccc')

    # Đếm trạm sạc thật (chỉ trạm thực sự sạc, không phải đi qua)
    n_charged_mpl = len(charged_cs)

    # Build label gọn: chỉ tên các trạm SẠC, các trạm khác hiển thị "..."
    if n_charged_mpl == 0:
        route_str = "Start → End (khong sac)"
    else:
        # Lấy ra các điểm quan trọng: start, trạm sạc, end
        key_nodes = [n for n in path_taken
                     if n == 'Start' or n == 'End' or n in charged_cs]
        # Bỏ trùng nhau (giữ thứ tự)
        seen = set()
        key_nodes = [x for x in key_nodes if not (x in seen or seen.add(x))]
        route_str = ' → '.join(key_nodes)

    ax.set_title(
        f"EV MPC Routing — Tram sac thuc te Ha Noi\n"
        f"Lo trinh: {route_str}",
        fontsize=10, fontweight='bold', pad=10
    )
    ax.axis('off')

    # ---- Biểu đồ SOC ----
    ax2 = axes[1]
    ax2.set_facecolor('#f0f4f8')
    xs  = list(range(len(soc_history)))

    # [FIX] Dùng ngưỡng SOC riêng của xe hiện tại (đã set trong set_vehicle())
    # thay cho 10/25 hardcode chỉ đúng tỉ lệ với VF8 (82 kWh).
    crit    = SOC_CRITICAL   # 5%  SOC_MAX
    warn    = SOC_WARNING    # 20% SOC_MAX
    top_lim = SOC_MAX + 5    # Trần trục Y = đúng dung lượng pin của xe + biên 5kWh

    # Vùng màu nền theo tỉ lệ % của xe đang chọn
    ax2.axhspan(0,    crit,    alpha=0.12, color='red')
    ax2.axhspan(crit, warn,    alpha=0.07, color='orange')
    ax2.axhspan(warn, top_lim, alpha=0.05, color='green')

    ax2.axhline(y=crit, color='red',    linestyle='--', lw=1.2, alpha=0.7,
                label=f'Nguong nguy hiem ({crit:.1f}kWh - 5%)')
    ax2.axhline(y=warn, color='orange', linestyle='--', lw=1.0, alpha=0.5,
                label=f'Nguong canh bao ({warn:.1f}kWh - 20%)')

    ax2.plot(xs, soc_history, 'o-', color='#1565C0', lw=2.5,
             ms=9, markerfacecolor='white', markeredgewidth=2.2, zorder=5)

    # Fill dưới đường SOC
    ax2.fill_between(xs, soc_history, alpha=0.12, color='#1565C0')

    # ... (Giữ nguyên vòng lặp dán nhãn trạm sạc và điểm nút của ông) ...

    ax2.set_xlabel('Buoc di chuyen', fontsize=10)
    ax2.set_ylabel('SOC (kWh)', fontsize=10)
    ax2.set_title('Trang thai pin (SOC) theo hanh trinh MPC',
                  fontsize=11, fontweight='bold')
                  
    # [FIX] Trục Y luôn hiển thị đúng dung lượng pin của xe đang chọn
    ax2.set_ylim(-2, top_lim)
    ax2.set_xticks(xs)
    ax2.set_xticklabels([f'B{i}' for i in xs], fontsize=8)
    ax2.legend(fontsize=8, loc='upper right')
    ax2.grid(True, alpha=0.25)

    plt.tight_layout(pad=2.0)
    plt.savefig('results/ev_routing_result.png', dpi=150, bbox_inches='tight')
    print("[INFO] Da luu: ev_routing_result.png")

    # ---- HTML Folium ----
    coords = [loc['coord'] for loc in all_nodes.values()]
    m = folium.Map(
        location=[sum(c[0] for c in coords)/len(coords),
                  sum(c[1] for c in coords)/len(coords)],
        zoom_start=13
    )

    def _safe_geometry(u, v, data=None):
        """Folium không chấp nhận locations rỗng; luôn trả về ít nhất 2 điểm."""
        data = data or {}
        geom = data.get('geometry')
        if geom and len(geom) >= 2:
            return geom
        return [all_nodes[u]['coord'], all_nodes[v]['coord']]

    # Tất cả cạnh (mờ)
    for u, v, data in G.edges(data=True):
        geom = _safe_geometry(u, v, data)
        folium.PolyLine(
            locations=geom, color='#90A4AE', weight=1.5, opacity=0.25,
            tooltip=f"{u}->{v} | {data['dist']}km | {data['energy']:.3f}kWh"
        ).add_to(m)

    # Lộ trình thực tế. Nếu xe chưa đi được cạnh nào thì không tạo PolyLine rỗng.
    route_geom = []
    for u, v in zip(path_taken, path_taken[1:]):
        segment = _safe_geometry(u, v, G[u][v])
        if route_geom and route_geom[-1] == segment[0]:
            route_geom.extend(segment[1:])
        else:
            route_geom.extend(segment)

    if len(route_geom) >= 2:
        folium.PolyLine(
            locations=route_geom, color='#00C853',
            weight=6, opacity=0.92, tooltip="Lo trinh MPC"
        ).add_to(m)
    elif path_taken:
        # Trường hợp pin quá thấp: xe dừng ngay tại Start hoặc tại node cuối đã tới.
        stopped_node = path_taken[-1]
        stopped_coord = all_nodes[stopped_node]['coord']
        folium.CircleMarker(
            location=stopped_coord,
            radius=10,
            color='#D32F2F',
            fill=True,
            fill_color='#D32F2F',
            fill_opacity=0.85,
            tooltip=f"Xe dừng tại {stopped_node} — chưa hoàn thành hành trình"
        ).add_to(m)

    # Số bước
    for i, (u, v) in enumerate(zip(path_taken, path_taken[1:]), 1):
        geom = _safe_geometry(u, v, G[u][v])
        mid  = geom[len(geom)//2]
        folium.Marker(location=mid, icon=folium.DivIcon(
            html=f'<div style="font-size:10px;font-weight:bold;color:#1B5E20;'
                 f'background:white;border-radius:50%;width:24px;height:24px;'
                 f'text-align:center;line-height:24px;border:2px solid #00C853;'
                 f'box-shadow:0 1px 4px rgba(0,0,0,0.3)">{i}</div>',
            icon_size=(24, 24), icon_anchor=(12, 12)
        )).add_to(m)

    # Markers
    for node, loc in all_nodes.items():
        if node not in G.nodes:
            continue

        if node in visited_cs:
            color, icon_name = 'orange', 'bolt'
            label = f"[Da sac] {node}"
        elif node in charging_stations:
            info      = CHARGING_STATION_INFO.get(node, {})
            color     = 'purple' if info.get('power_kw', 0) >= 100 else 'beige'
            icon_name = 'bolt'
            label     = f"[{info.get('brand','?')}] {info.get('power_kw','?')}kW"
        elif node == start_node:
            color, icon_name = 'blue',  'car'
            label = f"[START] {node}"
        elif node == end_node:
            color, icon_name = 'red',   'flag'
            label = f"[END] {node}"
        else:
            color, icon_name = 'gray',  'map-marker'
            label = node

        pos_str = ", ".join(str(p) for p in positions_in_path(node)) \
                  or "Khong trong lo trinh"

        if node in CHARGING_STATION_INFO:
            info   = CHARGING_STATION_INFO[node]
            t_min  = get_charge_time_min(node, 10) if node in visited_cs else "—"
            status = ("<span style='color:#E65100;font-weight:bold'>Da su dung</span>"
                      if node in visited_cs else
                      "<span style='color:#78909C'>Chua su dung</span>")
            pop = f"""
            <div style="font-family:Arial;min-width:250px;padding:6px">
                <h4 style="margin:0 0 4px;color:#4A148C">{node}</h4>
                <p style="margin:2px 0;font-size:12px;color:#555">{info['name']}</p>
                <hr style="margin:5px 0">
                <table style="font-size:12px;width:100%">
                    <tr><td><b>Hang:</b></td><td>{info['brand']}</td></tr>
                    <tr><td><b>Cong suat:</b></td>
                        <td><b style="color:#6A1B9A">{info['power_kw']} kW</b></td></tr>
                    <tr><td><b>Dau cap:</b></td><td>{info['connector']}</td></tr>
                    <tr><td><b>So coc:</b></td><td>{info['slots']}</td></tr>
                    <tr><td><b>Gio mo:</b></td>
                        <td>{'24/7' if info['open_24h'] else 'Gio HC'}</td></tr>
                    <tr><td><b>T.gian sac:</b></td><td>~{t_min} phut</td></tr>
                    <tr><td><b>Trang thai:</b></td><td>{status}</td></tr>
                </table>
                <p style="margin:5px 0;font-size:11px">
                    <b>Vi tri lo trinh:</b> Buoc {pos_str}
                </p>
            </div>"""
        else:
            # Node start/end
            edges_out = list(G.out_edges(node, data=True))
            rows = "".join(
                f"<tr><td style='padding:2px 5px'>{v2}</td>"
                f"<td style='padding:2px 5px'>{d['dist']}km</td>"
                f"<td style='padding:2px 5px'>{d['energy']:.3f}kWh</td></tr>"
                for _, v2, d in edges_out[:5]   # Giới hạn 5 hàng
            )
            pop = f"""
            <div style="font-family:Arial;min-width:220px;padding:4px">
                <h4 style="margin:0 0 4px">{node}</h4>
                <p style="margin:2px 0;color:#666;font-size:12px">{loc['name']}</p>
                <p style="font-size:12px"><b>Vi tri lo trinh:</b> Buoc {pos_str}</p>
                {"<b style='font-size:11px'>Canh di tu day (top 5):</b>"
                 "<table border='1' style='border-collapse:collapse;font-size:10px'>"
                 "<tr style='background:#eee'><th>Den</th><th>KM</th><th>NL</th></tr>"
                 + rows + "</table>" if rows else ""}
            </div>"""

        folium.Marker(
            location=loc['coord'],
            popup=folium.Popup(pop, max_width=280),
            tooltip=label,
            icon=folium.Icon(color=color, icon=icon_name, prefix='fa')
        ).add_to(m)

    # [FIX] Build legend hiển thị rõ trạm SẠC vs ĐI QUA (không sạc)
    # Dùng charged_cs (chỉ trạm thực sự sạc) thay vì visited_cs
    label_parts = []
    for node in path_taken:
        if node == 'Start' or node == 'End':
            label_parts.append(f'<b>{node}</b>')
        elif node in charged_cs:
            # Trạm đã thực sự sạc → tô đậm tím
            label_parts.append(f'<span style="color:#7B1FA2">⚡ {node}</span>')
        else:
            # Trạm chỉ đi qua → xám nhạt + ghi chú
            label_parts.append(f'<span style="color:#999;font-size:11px">{node} (đi qua)</span>')
    route_label = ' → '.join(label_parts)

    # Đếm số trạm thật sự sạc
    n_charged = len(charged_cs)
    sub_label = ('Không dừng sạc' if n_charged == 0
                 else f'{n_charged} lần dừng sạc')

    m.get_root().html.add_child(folium.Element(f"""
    <div style="position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
                background:white;padding:10px 22px;border-radius:10px;
                box-shadow:0 2px 10px rgba(0,0,0,0.25);font-family:Arial;
                z-index:1000;border-left:5px solid #00C853;
                max-width:850px;white-space:nowrap;font-size:13px">
        <b style="color:#1B5E20">Lộ trình MPC ({sub_label}):</b>
        <span style="color:#333"> {route_label}</span>
    </div>"""))

    m.save('results/ev_routing_map.html')
    print("[INFO] Da luu: ev_routing_map.html")


# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    print("=" * 62)
    print("  EV MPC Routing — TomTom API + Tram sac thuc te")
    print("=" * 62)

    if TOMTOM_API_KEY == "NHAP_KEY_CUA_BAN_VAO_DAY":
        print("\n[!!!] Chua co TomTom API Key!")
        exit(1)

    # ── Đọc params từ web_app nếu có, fallback sang input() ──
    if os.path.exists("data/ui_params.json"):
        with open("data/ui_params.json", encoding="utf-8") as f:
            p = json.load(f)
        start_input    = p.get("start_node", "").strip()
        end_input      = p.get("end_node",   "").strip()
        soc_init       = float(p.get("soc_init", 1.0))
        allow_charging = bool(p.get("allow_charging", True))
        priority       = p.get("priority", "balanced")
        max_soc_pct    = float(p.get("max_soc_pct", 92))
        vehicle_name   = p.get("vehicle", DEFAULT_VEHICLE)
        # [NEW] Tham số môi trường — mặc định Hà Nội mùa hè điển hình
        ambient_temp   = float(p.get("ambient_temp", 28))
        ac_on          = bool(p.get("ac_on", True))
        n_passengers   = int(p.get("n_passengers", 1))
        set_vehicle(vehicle_name, ambient_temp, ac_on, n_passengers)
        print(f"[UI] {start_input} -> {end_input} | SOC={soc_init}kWh | xe={vehicle_name} | charge={allow_charging} | maxSOC={max_soc_pct:.0f}%")
    else:
        set_vehicle(DEFAULT_VEHICLE)
        print(f"\n  Mang luoi: {len(CHARGING_STATION_INFO)} tram sac thuc te tai Ha Noi")
        print("\n--- NHAP THONG TIN HANH TRINH ---")
        start_input = input("1. Dia chi XUAT PHAT (Enter = Ho Hoan Kiem): ").strip()
        end_input   = input("2. Dia chi DICH DEN  (Enter = Hoang Mai):    ").strip()
        soc_input   = input("3. Muc pin (kWh)     (Enter = 1.0 kWh):      ").strip()
        soc_init    = float(soc_input) if soc_input else 1.0
        allow_charging = True
        max_soc_pct = 92
        priority = "balanced"

    # ── [SAFETY] SOC đầu vào là kWh tuyệt đối, nên phải nằm trong dung lượng xe hiện tại ──
    if soc_init > SOC_MAX:
        print(f"[WARN] SOC đầu vào {soc_init:.2f} kWh > dung lượng xe {SOC_MAX:.2f} kWh. Đã clamp về SOC_MAX.")
        soc_init = SOC_MAX
    if soc_init < 0:
        print("[WARN] SOC đầu vào âm. Đã clamp về 0 kWh.")
        soc_init = 0.0

    # --- Xử lý geocoding ---
    print("\n[1/4] Xu ly dia chi...")
    start_info = DEFAULT_START.copy()
    end_info   = DEFAULT_END.copy()
    start_node = 'Start'
    end_node   = 'End'

    if start_input:
        coord, name = geocode_address(start_input)
        if coord:
            start_info = {'name': name, 'coord': coord}
            print(f"      OK: {name}  ({coord[0]:.5f}, {coord[1]:.5f})")
        else:
            print(f"      Dung mac dinh: {start_info['name']}")

    if end_input:
        coord, name = geocode_address(end_input)
        if coord:
            end_info = {'name': name, 'coord': coord}
            print(f"      OK: {name}  ({coord[0]:.5f}, {coord[1]:.5f})")
        else:
            print(f"      Dung mac dinh: {end_info['name']}")

    # --- Tập hợp tất cả nodes ---
    # Đồ thị đầy đủ: Start + End + tất cả trạm sạc
    all_nodes = {start_node: start_info, end_node: end_info}
    for k, v in CHARGING_STATION_INFO.items():
        all_nodes[k] = {'name': v['name'], 'coord': v['coord']}

    charging_stations = list(CHARGING_STATION_INFO.keys())

    print(f"\n=> HANH TRINH: {start_info['name']} -> {end_info['name']}")
    print(f"   Pin: {soc_init} kWh | {len(all_nodes)} node | "
          f"{len(all_nodes)*(len(all_nodes)-1)} canh can tai")

    # --- Build graph ---
    print("\n[2/4] Xay dung độ thi tu TomTom API...")

    # [FIX] Tăng từ 7km → 15km để không bỏ sót trạm sạc dọc hành trình
    # Đồng thời luôn nối Start và End với tất cả trạm sạc (bất kể khoảng cách)
    G = build_sparse_graph(all_nodes, max_radius_km=15.0)

    print(f"      Hoan tat: {G.number_of_nodes()} node, {G.number_of_edges()} canh.")

    if not nx.has_path(G, start_node, end_node):
        print(f"\n[LOI] Khong co duong di. Thoat.")
        exit(1)

    # --- Simulation ---
    print("\n[3/4] Mo phong MPC...")
    (path_taken, visited_cs, charged_cs, soc_history, speed_log,
     charge_times_sec, trip_result) = run_simulation(
        G, all_nodes, start_node, end_node, charging_stations,
        soc_init,
        priority=priority,
        horizon=5,
        max_soc_pct=max_soc_pct,
        allow_charging=allow_charging
    )

    # --- Output ---
    print("\n[4/4] Xuat ket qua...")
    print_summary(path_taken, soc_history, visited_cs, G, charge_times_sec, trip_result)
    export_summary(
        path_taken, soc_history, visited_cs, G, start_info, end_info,
        charge_times_sec, trip_result
    )

    # Vẫn vẽ quãng đường thực tế đã đi để chẩn đoán, nhưng chỉ xuất DriveCycle
    # hoàn chỉnh khi xe thật sự tới đích.
    visualize(G, all_nodes, path_taken, visited_cs,
              charging_stations, soc_history, start_node, end_node,
              charged_cs=charged_cs)

    print("\n" + "=" * 62)
    if trip_result["completed"]:
        export_matlab(path_taken, soc_history, speed_log, G, charge_times_sec)
        print("  HOAN THANH HANH TRINH!")
        print("  - ev_routing_result.png")
        print("  - ev_routing_map.html")
        print("  - DriveCycle_Data.mat")
    else:
        print("  HANH TRINH KHONG KHA THI — KHONG XUAT DRIVE CYCLE HOAN CHINH")
        print(f"  Ly do: {trip_result['failure_reason']}")
        print("  - ev_routing_result.png (quang duong da di)")
        print("  - ev_routing_map.html (quang duong da di)")
        # Giữ exit code 0 để web app đọc summary.json và hiển thị lỗi nghiệp vụ,
        # thay vì coi đây là lỗi crash của Python.
    print("=" * 62)
