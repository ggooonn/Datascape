import math
import os
import random
import time
import cv2
from matplotlib.collections import LineCollection
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from scipy.interpolate import CubicSpline, interp1d

start_time = time.time()

# ==============================================================================
# [A] Canvas Configuration (8x6)
# ==============================================================================
PANEL_W, PANEL_H = 330.0, 330.0 
MIN_DRAW, MAX_DRAW = 0.0, 330.0 
GAP_X, GAP_Y = 20.0, 10.0  
COLS, ROWS = 8, 6  
TOTAL_W = PANEL_W * COLS + GAP_X * (COLS - 1)
TOTAL_H = PANEL_H * ROWS + GAP_Y * (ROWS - 1)

output_dir = "Taebaek_V203_MacroDEM_Gcode"
if not os.path.exists(output_dir): os.makedirs(output_dir)

gcode_dir = os.path.join(output_dir, "GCODES")
ink_gcode_dir = os.path.join(gcode_dir, "01_INK")
color_gcode_dir = os.path.join(gcode_dir, "02_COLOR")

for d in [gcode_dir, ink_gcode_dir, color_gcode_dir]:
    if not os.path.exists(d): os.makedirs(d)

panels = []
row_names = ['F', 'E', 'D', 'C', 'B', 'A']
for r_idx in range(ROWS):
    for c_idx in range(COLS):
        panels.append((f"{row_names[r_idx]}{c_idx+1}", c_idx * (PANEL_W + GAP_X), r_idx * (PANEL_H + GAP_Y)))

# ==============================================================================
# [B] Ink Stations & Hardware Mapping
# ==============================================================================
FEED_RATE_DRAW = 5000       # 드로잉 20% 가속
FEED_RATE_TRAVEL = 10000    # 트래블 속도 복원
FEED_RATE_WIPE = 5000       # 와이프 속도 복원
FEED_RATE_Z_FAST = 4000     # Z축 속도 복원

Z_HOVER, Z_SAFE, Z_TOUCH_INK, Z_TOUCH_COLOR = 0.0, 0.0, -2.0, -3.5       

ORDERED_LAYERS = [
    'ink_base', 'ac_navy', 'ac_brown', 'oc_ultra', 'mt_purple', 
    'oc_cobalt', 'ac_teal', 'ac_green', 'mt_red', 'mt_orange', 'mt_yellow'
]

STATIONS = {
    'mt_red':    {'x': -15.0, 'y': 20.0,  'limit': 1000.0,  'dip_z': -16.0, 'name': 'Red'},
    'mt_yellow': {'x': -15.0, 'y': 60.0,  'limit': 1000.0,  'dip_z': -16.0, 'name': 'Yellow'},
    'ink_base':  {'x': -15.0, 'y': 100.0, 'limit': 2000.0, 'dip_z': -15.0, 'name': 'Ink Base'},
    'mt_orange': {'x': -15.0, 'y': 150.0, 'limit': 1000.0,  'dip_z': -16.0, 'name': 'Orange'},
    'oc_cobalt': {'x': -15.0, 'y': 200.0, 'limit': 1000.0,  'dip_z': -16.0, 'name': 'Cobalt'},
    'mt_purple': {'x': -15.0, 'y': 240.0, 'limit': 1000.0,  'dip_z': -16.0, 'name': 'Purple'},
    'water':     {'x': -15.0, 'y': 280.0, 'limit': 0.0,    'dip_z': -13.0, 'name': 'Water'},
    'oc_ultra':  {'x': -15.0, 'y': 330.0, 'limit': 1000.0,  'dip_z': -16.0, 'name': 'Ultra'},
    'ac_brown':  {'x': -35.0, 'y': 20.0,  'limit': 1000.0,  'dip_z': -16.0, 'name': 'Brown'},
    'ac_green':  {'x': -35.0, 'y': 150.0, 'limit': 1000.0,  'dip_z': -16.0, 'name': 'Green'},
    'ac_teal':   {'x': -35.0, 'y': 200.0, 'limit': 1000.0,  'dip_z': -16.0, 'name': 'Teal'},
    'ac_navy':   {'x': -35.0, 'y': 330.0, 'limit': 1000.0,  'dip_z': -16.0, 'name': 'Navy'}
}

def get_wash_gcode():
    wx, wy, wz = STATIONS['water']['x'], STATIONS['water']['y'], STATIONS['water']['dip_z']
    return [
        "; --- AUTO WASH ---",
        f"G0 Z{Z_SAFE:.3f}", f"G0 X{wx:.3f} Y{wy:.3f} F{FEED_RATE_TRAVEL}",
        f"G1 Z{wz:.3f} F3000", "G4 P1.0",
        f"G1 Y{wy+10.0:.3f} F{FEED_RATE_WIPE}", f"G1 Y{wy-10.0:.3f} F{FEED_RATE_WIPE}",
        f"G1 Y{wy+10.0:.3f} F{FEED_RATE_WIPE}", f"G1 Y{wy-10.0:.3f} F{FEED_RATE_WIPE}",
        f"G1 Y{wy:.3f} F{FEED_RATE_WIPE}", f"G0 Z{Z_HOVER:.3f}"
    ]

def get_final_wash_gcode():
    wx, wy, wz = STATIONS['water']['x'], STATIONS['water']['y'], STATIONS['water']['dip_z']
    return [
        "; --- FINAL DEEP WASH ---",
        f"G0 Z{Z_SAFE:.3f}", f"G0 X{wx:.3f} Y{wy:.3f} F{FEED_RATE_TRAVEL}",
        f"G1 Z{wz:.3f} F3000", "G4 P5.0", 
        f"G1 Y{wy+10.0:.3f} F{FEED_RATE_WIPE}", f"G1 Y{wy-10.0:.3f} F{FEED_RATE_WIPE}",
        f"G1 Y{wy+10.0:.3f} F{FEED_RATE_WIPE}", f"G1 Y{wy-10.0:.3f} F{FEED_RATE_WIPE}",
        f"G1 Y{wy+10.0:.3f} F{FEED_RATE_WIPE}", f"G1 Y{wy-10.0:.3f} F{FEED_RATE_WIPE}", 
        "G4 P5.0", f"G1 Y{wy:.3f} F{FEED_RATE_WIPE}", f"G0 Z{Z_HOVER:.3f}"
    ]

def get_dip_gcode(ink_name):
    sx, sy, sz, sname = STATIONS[ink_name]['x'], STATIONS[ink_name]['y'], STATIONS[ink_name]['dip_z'], STATIONS[ink_name]['name']
    gcode = [
        f"; --- DIPPING: {sname} ---",
        f"G0 Z{Z_SAFE:.3f}", f"G0 X{sx:.3f} Y{sy:.3f} F{FEED_RATE_TRAVEL}",
        f"G1 Z{sz:.3f} F3000", "G4 P1.5",
        f"G1 Y{sy+10.0:.3f} F1000", f"G1 Y{sy-10.0:.3f} F1000", f"G1 Y{sy:.3f} F1000"
    ]
    if sx == -15.0:
        gcode.extend([
            f"G1 Z{sz + 4.0:.3f} F{FEED_RATE_Z_FAST}", 
            f"G1 X{sx+5.0:.3f} F{FEED_RATE_WIPE}", f"G1 X{sx-5.0:.3f} F{FEED_RATE_WIPE}", f"G1 X{sx:.3f} F{FEED_RATE_WIPE}"
        ])
    gcode.append(f"G0 Z{Z_HOVER:.3f}")
    return gcode

def generate_layer_gcode(paths, ink_name):
    if not paths: return []
    gcode = get_dip_gcode(ink_name)
    drawn_len = 0.0
    limit = STATIONS[ink_name]['limit']
    for pts in paths:
        if len(pts) < 2: continue
        sx, sy = np.clip(pts[0][0], MIN_DRAW, MAX_DRAW), np.clip(pts[0][1], MIN_DRAW, MAX_DRAW)
        gcode.extend([f"G0 Z{Z_HOVER:.3f}", f"G0 X{sx:.3f} Y{sy:.3f} F{FEED_RATE_TRAVEL}", f"G1 Z{pts[0][2]:.3f} F{FEED_RATE_Z_FAST}"]) 
        for i in range(1, len(pts)):
            px, py, pz = np.clip(pts[i][0], MIN_DRAW, MAX_DRAW), np.clip(pts[i][1], MIN_DRAW, MAX_DRAW), pts[i][2]
            gcode.append(f"G1 X{px:.3f} Y{py:.3f} Z{pz:.3f} F{FEED_RATE_DRAW}")
            drawn_len += math.hypot(px - sx, py - sy)
            sx, sy = px, py
        if drawn_len > limit:
            gcode.extend([f"G0 Z{Z_HOVER:.3f}"] + get_dip_gcode(ink_name))
            drawn_len = 0.0
    return gcode

# ==============================================================================
# [C] Spline Engine & Pressure Math (🌟 지형 밀집도 비례 필압 그라데이션)
# ==============================================================================
def smooth_spline_3d(path, res_factor=2):
    if len(path) < 4: return path
    pts = np.array(path)
    dists = np.sqrt(np.sum(np.diff(pts[:, :2], axis=0)**2, axis=1))
    valid_idx = np.where(dists > 0.1)[0]
    pts = pts[np.append(valid_idx, len(pts)-1)]
    if len(pts) < 4: return path
    t = np.linspace(0, 1, len(pts))
    t_new = np.linspace(0, 1, len(pts) * res_factor)
    try:
        cs_x, cs_y, cs_z = CubicSpline(t, pts[:, 0]), CubicSpline(t, pts[:, 1]), CubicSpline(t, pts[:, 2])
        return np.vstack([cs_x(t_new), cs_y(t_new), cs_z(t_new)]).T.tolist()
    except: return path

def get_z_pressure_ink(dem_val, slope_val, noise_val):
    # 고도(70%) + 경사도(30%)에 따른 밀집도(crowdedness) 계산
    crowdedness = np.clip(dem_val * 0.7 + slope_val * 0.3, 0.0, 1.0)
    # 성긴 저지대는 -10.0mm(굵은 선), 밀집된 산 정상은 -3.5mm(가는 선)
    base_z = -10.0 + (crowdedness * 6.5)  
    base_z += (noise_val - 0.5) * 1.5 
    if dem_val < 0.15 and slope_val < 0.15: 
        base_z = random.uniform(-4.0, -3.2) 
    return np.clip(base_z, -10.5, 0.0)

def get_z_pressure_color(dem_val, slope_val, noise_val):
    crowdedness = np.clip(dem_val * 0.7 + slope_val * 0.3, 0.0, 1.0)
    base_z = -6.0 + (crowdedness * 4.0) 
    base_z += (noise_val - 0.5) * 1.5
    if dem_val < 0.15 and slope_val < 0.15: 
        base_z = random.uniform(-3.5, -2.5) 
    return np.clip(base_z, -10.0, 0.0)

# ==============================================================================
# [D] Data Load & View Math + Macro DEM
# ==============================================================================
print("[Status] 1. Loading Taebaek Data & Generating Macro DEM...")
data_dir = r"F:\GIT\Datascape\TAEBAEK"
RES_W, RES_H = 2000, 1500 

def load_tiff(filename):
    try:
        with rasterio.open(os.path.join(data_dir, filename)) as src:
            arr = np.where(src.read(1) < 0, 0, src.read(1))
            return cv2.resize(arr, (RES_W, RES_H), interpolation=cv2.INTER_LINEAR)
    except: return np.zeros((RES_H, RES_W))

raw_dem = load_tiff('Taebaek_DEM.tif')
dem_norm = np.clip(raw_dem / (np.max(raw_dem) + 1e-5), 0, 1)
aspect_norm = np.clip(load_tiff('Taebaek_Aspect.tif') / 360.0, 0, 1) 
ndvi_norm = np.clip(load_tiff('Taebaek_NDVI.tif'), 0, 1)

H, W = dem_norm.shape
dy, dx = np.gradient(dem_norm)
slope = np.clip(np.sqrt(dx**2 + dy**2) * 5.0, 0, 1)

noise_map = cv2.resize(np.random.rand(50, 60), (W, H), interpolation=cv2.INTER_CUBIC)
sea_mask = (dem_norm < 0.02)
spiky_dem = np.where(sea_mask, 0.0, dem_norm ** 1.3)

macro_dem_raw = cv2.GaussianBlur(dem_norm, (251, 251), 0)
vmin, vmax = np.percentile(macro_dem_raw, 5), np.percentile(macro_dem_raw, 90)
macro_dem = np.clip((macro_dem_raw - vmin) / (vmax - vmin + 1e-5), 0.0, 1.0)

interp_z = interp1d([0.0, 0.5, 1.0], [200.0, 450.0, 550.0], kind='quadratic')
y_r_vec = np.linspace(0, 1.0, H)
y_pitches = interp1d([0.0, 0.5, 1.0], [0.5, 0.8, 1.2], kind='quadratic')(y_r_vec)

Y_PHYS = (np.cumsum(y_pitches) / np.sum(y_pitches)) * 1550.0 - 50.0 

visibility_mask = np.zeros((H, W), dtype=bool); horizon = np.full(W, -np.inf)
for y in range(H):
    if y == int(H * 0.3) or y == int(H * 0.7): horizon = horizon - 150.0 
    py_row = Y_PHYS[y] + (spiky_dem[y, :] * interp_z(y_r_vec[y])) - 30.0
    visibility_mask[y, :] = py_row >= horizon - 0.5
    horizon = np.where(visibility_mask[y, :], py_row, horizon)

coast_dist = np.zeros((H, W))
for y in range(H):
    last_land = -1
    for x in range(W):
        if not sea_mask[y,x]: last_land = x 
        else:
            if last_land != -1: coast_dist[y,x] = x - last_land 

def get_base_xy(x_idx, y_r, w_max, dem_val, shift_x=0.0):
    base_x = -400.0 + (x_idx / (w_max - 1)) * (TOTAL_W + 800.0)
    is_land = np.clip(dem_val * 10.0, 0.0, 1.0)
    sway = math.sin(y_r * math.pi * 3.0) * 80.0 * is_land
    stretch_factor = 1.0 + math.cos(y_r * math.pi * 2.0) * 0.2
    return (TOTAL_W / 2.0) + (base_x - TOTAL_W / 2.0) * stretch_factor + sway + shift_x

# ==============================================================================
# [E] Layer Generation
# ==============================================================================
print("[Status] 2. Generating Splines with Enhanced Density & Dynamic Pressures...")
global_layers = {k: [] for k in ORDERED_LAYERS}

def extract_splines(path, z_limit):
    segments, seg = [], []
    for pt in path:
        if pt[2] <= z_limit: seg.append(pt)
        else:
            if len(seg) > 2: segments.append(smooth_spline_3d(seg))
            seg = []
    if len(seg) > 2: segments.append(smooth_spline_3d(seg))
    return segments

# --- PASS 1: INK BASE (밀도 +50%) ---
curr_y = 0.0
while curr_y < H:
    y = int(curr_y); y_r = y_r_vec[y]
    terrain_roughness = np.clip((np.max(dem_norm[y,:]) - 0.1) / 0.8, 0, 1)
    gap = (np.interp(y_r, [0.0, 1.0], [15.0, 6.0]) - 8.0 * (terrain_roughness ** 1.5)) * 0.67
    z_s = interp_z(y_r)

    p_ink = []
    for x in range(0, W, 2): 
        px = get_base_xy(x, y_r, W, dem_norm[y,x], 0.0)  
        py = Y_PHYS[y] + (spiky_dem[y,x] * z_s) - 30.0
        if dem_norm[y,x] > 0.6: py += (dem_norm[y,x] ** 3.0) * 150.0 * math.sin(x * 0.05) 
        
        if visibility_mask[y,x]:
            if sea_mask[y,x]:
                py += math.sin(x * 0.02 + y_r * 15.0) * 2.5 
                c_dist = coast_dist[y,x]
                if c_dist > 0:
                    fade_prob = np.clip(c_dist / 600.0, 0.0, 1.0)
                    if random.random() < fade_prob: p_ink.append((px, py, 0.0))
                    else: p_ink.append((px, py, -3.5)) 
                else: p_ink.append((px, py, -3.5))
            else:
                p_ink.append((px, py, get_z_pressure_ink(dem_norm[y,x], slope[y,x], noise_map[y,x])))
        else: p_ink.append((px, py, 0.0)) 
        
    global_layers['ink_base'].extend(extract_splines(p_ink, -2.5)) 
    curr_y += max(1.0, gap)

# --- PASS 2: MACRO-DEM COLOR MULTIPLIER + GLITCH (밀도 +30% & 먹선 오프셋) ---
curr_y = 5.0
while curr_y < H:
    y = int(curr_y)
    y_r = y_r_vec[y]
    inverted_y_r = 1.0 - y_r
    
    terrain_roughness = np.clip((np.max(dem_norm[y,:]) - 0.1) / 0.8, 0, 1)
    gap = (np.interp(y_r, [0.0, 1.0], [15.0, 6.0]) - 8.0 * (terrain_roughness ** 1.5)) / 2.2 
    z_s = interp_z(y_r)

    # 1. 지형 지수(1.5승)
    row_macro = np.percentile(macro_dem[y, :], 60)
    macro_curved = (row_macro ** 1.5)
    
    # 2. [Y축 0.25 : 고도 0.75] 조합
    blend_factor = np.clip(((inverted_y_r * 0.25) + (macro_curved * 0.75)), 0.0, 1.0)
    
    # 3. 5대 메인 컬러 곡선
    w_n = np.interp(blend_factor, [0.00, 0.18, 0.35], [1.3, 1.0, 0.0])       # [최하단/골짜기] 남색 (Navy)
    w_u = np.interp(blend_factor, [0.15, 0.32, 0.50], [0.0, 1.0, 0.0])       # [하단] 울트라블루
    w_c = np.interp(blend_factor, [0.32, 0.48, 0.65], [0.0, 1.0, 0.0])       # [중간 지형] 코발트
    w_t = np.interp(blend_factor, [0.48, 0.65, 0.82], [0.0, 1.0, 0.0])       # [중상단 능선] 틸(청록)
    w_g = np.interp(blend_factor, [0.65, 0.82, 1.00], [0.0, 1.0, 1.3])       # [상단/산봉우리] 초록
    
    tot_main = w_n + w_u + w_c + w_t + w_g
    r_val = random.random()
    if r_val < w_n/tot_main: main_col = 'ac_navy'
    elif r_val < (w_n+w_u)/tot_main: main_col = 'oc_ultra'
    elif r_val < (w_n+w_u+w_c)/tot_main: main_col = 'oc_cobalt'
    elif r_val < (w_n+w_u+w_c+w_t)/tot_main: main_col = 'ac_teal'
    else: main_col = 'ac_green'

    # 4. 포인트 글리치 컬러
    is_point_row = random.random() < 0.4
    if is_point_row:
        w_purple = np.interp(blend_factor, [0.0, 0.35], [1.5, 0.05])
        w_yellow = np.interp(blend_factor, [0.45, 1.0], [0.05, 1.5])
        
        point_col = random.choices(
            ['mt_purple', 'mt_red', 'mt_orange', 'mt_yellow', 'ac_brown'], 
            weights=[w_purple, 0.25, 0.3, w_yellow, 0.2]
        )[0]

    shift_x = random.uniform(-2.5, 2.5)
    active_main_col = None
    seg_main = []
    active_point_col = None
    seg_point = []
    
    for x in range(0, W, 2):
        if sea_mask[y,x]: continue 
        
        dynamic_shift = shift_x + math.sin(x * 0.08 + y_r * 5.0) * 1.5
        y_offset_color = math.cos(x * 0.05 + y_r * 4.0) * 1.2
        
        px = get_base_xy(x, y_r, W, dem_norm[y,x], dynamic_shift) 
        py = Y_PHYS[y] + (spiky_dem[y,x] * z_s) - 30.0 + y_offset_color
        if dem_norm[y,x] > 0.6: py += (dem_norm[y,x] ** 3.0) * 150.0 * math.sin(x * 0.05)
        
        if visibility_mask[y,x]:
            z_val = get_z_pressure_color(dem_norm[y,x], slope[y,x], noise_map[y,x])
            
            if noise_map[y,x] > 0.2:
                if main_col != active_main_col:
                    if len(seg_main) > 2 and active_main_col:
                        global_layers[active_main_col].extend(extract_splines(seg_main, -2.5))
                    seg_main = [(px, py, z_val)]
                    active_main_col = main_col
                else: seg_main.append((px, py, z_val))
            else:
                if len(seg_main) > 2 and active_main_col:
                    global_layers[active_main_col].extend(extract_splines(seg_main, -2.5))
                seg_main = []
            
            if is_point_row and (noise_map[y,x] > 0.4 or slope[y,x] > 0.4):
                glitch_px = px + random.uniform(-2.5, 2.5)
                glitch_py = py + random.uniform(-2.5, 2.5)
                
                if point_col != active_point_col:
                    if len(seg_point) > 2 and active_point_col:
                        global_layers[active_point_col].extend(extract_splines(seg_point, -2.5))
                    seg_point = [(glitch_px, glitch_py, -5.0)]
                    active_point_col = point_col
                else: seg_point.append((glitch_px, glitch_py, -5.0))
            else:
                if len(seg_point) > 2 and active_point_col:
                    global_layers[active_point_col].extend(extract_splines(seg_point, -2.5))
                seg_point = []
        else:
            if len(seg_main) > 2 and active_main_col:
                global_layers[active_main_col].extend(extract_splines(seg_main, -2.5))
            seg_main = []
            if len(seg_point) > 2 and active_point_col:
                global_layers[active_point_col].extend(extract_splines(seg_point, -2.5))
            seg_point = []

    if len(seg_main) > 2 and active_main_col:
        global_layers[active_main_col].extend(extract_splines(seg_main, -2.5))
    if len(seg_point) > 2 and active_point_col:
        global_layers[active_point_col].extend(extract_splines(seg_point, -2.5))

    curr_y += max(0.8, gap)

# ==============================================================================
# [F] Slicing into Panels & G-Code Export (🌟 INK / COLOR 분할 출력)
# ==============================================================================
print("[Status] 3. Slicing into 48 Panels...")
def clip_segment_to_box(segment, min_x, max_x, min_y, max_y):
    clipped, curr = [], []
    for px, py, pz in segment:
        if min_x <= px <= max_x and min_y <= py <= max_y: curr.append((px, py, pz))
        else:
            if len(curr) > 1: clipped.append(curr)
            curr = []
    if len(curr) > 1: clipped.append(curr)
    return clipped

viz_data = {p[0]: {k: [] for k in ORDERED_LAYERS} for p in panels}

for layer_name in ORDERED_LAYERS:
    for path in global_layers[layer_name]:
        for p_name, x_off, y_off in panels:
            p_min_x, p_max_x = x_off + MIN_DRAW, x_off + MAX_DRAW
            p_min_y, p_max_y = y_off + MIN_DRAW, y_off + MAX_DRAW
            
            xs, ys = [pt[0] for pt in path], [pt[1] for pt in path]
            if min(xs) > p_max_x or max(xs) < p_min_x or min(ys) > p_max_y or max(ys) < p_min_y: continue
                
            clipped_segs = clip_segment_to_box(path, p_min_x, p_max_x, p_min_y, p_max_y)
            for c_seg in clipped_segs:
                viz_data[p_name][layer_name].append([(pt[0] - x_off, pt[1] - y_off, pt[2]) for pt in c_seg])

print("[Status] 4. Generating Separated G-Code Files (INK / COLOR)...")
for p_name, x_off, y_off in panels:
    # ----------------------------------------------------
    # 1) [먹 전용 G-code] -> GCODES/01_INK/
    # ----------------------------------------------------
    ink_paths = viz_data[p_name]['ink_base']
    if ink_paths:
        ink_gcode = [
            "G21", "G90", 
            f"; --- TAEBAEK PROJECT (V202) - INK ONLY ---",
            f"; --- PANEL: {p_name} ---",
            f"G0 Z{Z_SAFE:.3f}"
        ]
        ink_gcode.extend(generate_layer_gcode(ink_paths, 'ink_base'))
        ink_gcode.extend(get_final_wash_gcode())
        ink_gcode.extend(["G0 Z0.000", f"G0 X-15.000 Y0.000 F{FEED_RATE_TRAVEL}", "M30"])
        
        filepath_ink = os.path.join(ink_gcode_dir, f"{p_name}_V202_INK.gcode")
        with open(filepath_ink, 'w', encoding='utf-8') as f:
            f.write("\n".join(ink_gcode))

    # ----------------------------------------------------
    # 2) [채색 전용 G-code] -> GCODES/02_COLOR/
    # ----------------------------------------------------
    color_layers = [l for l in ORDERED_LAYERS if l != 'ink_base']
    has_color = any(len(viz_data[p_name][l]) > 0 for l in color_layers)
    
    if has_color:
        color_gcode = [
            "G21", "G90", 
            f"; --- TAEBAEK PROJECT (V202) - COLOR ONLY ---",
            f"; --- PANEL: {p_name} ---",
            f"G0 Z{Z_SAFE:.3f}"
        ]
        
        first_color_done = False
        for layer_name in color_layers:
            paths = viz_data[p_name][layer_name]
            if not paths: continue
            
            if first_color_done:
                color_gcode.extend(get_wash_gcode())
                
            color_gcode.extend(generate_layer_gcode(paths, layer_name))
            first_color_done = True
            
        color_gcode.extend(get_final_wash_gcode())
        color_gcode.extend(["G0 Z0.000", f"G0 X-15.000 Y0.000 F{FEED_RATE_TRAVEL}", "M30"])
        
        filepath_color = os.path.join(color_gcode_dir, f"{p_name}_V202_COLOR.gcode")
        with open(filepath_color, 'w', encoding='utf-8') as f:
            f.write("\n".join(color_gcode))

# ==============================================================================
# [G] Global Rendering
# ==============================================================================
print("[Status] 5. Rendering Final Visual Map...")
color_palette = {
    'ink_base':  ('#444444', 1.0, 1), 
    'ac_navy':   ('#0c2560', 1.2, 3), 
    'ac_brown':  ('#8B4513', 1.5, 4), 
    'oc_ultra':  ('#0000CD', 1.2, 2), 
    'mt_purple': ('#8A2BE2', 1.5, 4), 
    'oc_cobalt': ('#1E90FF', 1.2, 2), 
    'ac_teal':   ('#00CED1', 1.0, 2), 
    'ac_green':  ('#32CD32', 1.0, 2), 
    'mt_red':    ('#FF0055', 1.5, 4), 
    'mt_orange': ('#FF4500', 1.5, 4), 
    'mt_yellow': ('#FFD700', 1.5, 5)  
}

fig_global = plt.figure(figsize=(32, 22), dpi=200, facecolor='#f8f9fa')
ax_global = fig_global.add_subplot(111)
ax_global.set_title("Taebaek 8x6 - V202 MACRO-DEM G-CODE READY (SPLIT INK/COLOR)", fontsize=28, fontweight='bold', color='#333333', pad=30)
ax_global.set_xlim(-50, TOTAL_W + 50); ax_global.set_ylim(-50, TOTAL_H + 50); ax_global.set_aspect('equal')
ax_global.axis('off')

for p_name, x_o, y_o in panels:
    rect = plt.Rectangle((x_o, y_o), PANEL_W, PANEL_H, fill=False, color='#cccccc', lw=1.5, ls='-')
    ax_global.add_patch(rect)
    
    ax_global.text(x_o + 10, y_o + 300, p_name, fontsize=18, fontweight='bold', color='white', 
                   path_effects=[pe.withStroke(linewidth=4, foreground='black')], zorder=100)
    
    for layer_name in ORDERED_LAYERS:
        segs = viz_data[p_name][layer_name]
        if not segs: continue
        c_hex, lw_base, z_order = color_palette[layer_name]
        
        global_segs = [[(pt[0] + x_o, pt[1] + y_o) for pt in seg] for seg in segs]
        alpha_val = 0.5 if layer_name == 'ink_base' else (0.9 if 'mt_' in layer_name or 'brown' in layer_name else 0.75)
        ax_global.add_collection(LineCollection(global_segs, colors=c_hex, lw=lw_base * 0.8, alpha=alpha_val, zorder=z_order))

plt.tight_layout()
plt.savefig(os.path.join(output_dir, "V202_Final_Macro_DEM.png"), format='png', bbox_inches='tight')
plt.show()

print(f"[Success] All 48 Panels Split G-Codes (V202 INK / COLOR) & Visual Map created! Runtime: {time.time()-start_time:.2f}s")