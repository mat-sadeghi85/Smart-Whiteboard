import cv2
import numpy as np
import mediapipe as mp

# ---------------------------------------------------------
# تنظیمات کلی
# ---------------------------------------------------------

CAM_INDEX = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
WINDOW_NAME = "Smart Whiteboard"
DISPLAY_HEIGHT_MARGIN = 90   
FALLBACK_MAX_DISPLAY_HEIGHT = 700  


def get_safe_max_display_height():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        screen_h = root.winfo_screenheight()
        root.destroy()
        return max(480, screen_h - DISPLAY_HEIGHT_MARGIN)
    except Exception:
        return FALLBACK_MAX_DISPLAY_HEIGHT

ERASE_RADIUS = 40

SMOOTHING_FACTOR = 0.5
MODE_STABILITY_FRAMES = 4
MAX_JUMP_DISTANCE = 120
COLOR_OPTIONS = [
    ("Black", (30, 30, 30)),
    ("White", (255, 255, 255)),
    ("Blue", (255, 0, 0)),
    ("Red", (0, 0, 255)),
]
SIDEBAR_WIDTH = 140
SWATCH_RADIUS = 26          
SWATCH_MARGIN = 22         

THICKNESS_OPTIONS = [
    ("Thin", 3),
    ("Medium", 6),
    ("Thick", 12),
]

PEN_ICON_LENGTH_RATIOS = [0.55, 0.72, 0.95]
THICKNESS_SWATCH_RADIUS = SWATCH_RADIUS 
SIDEBAR_SECTION_GAP = 34  

# ---- تنظیمات جمع‌شدن خودکار سایدبار وقتی صفحه کوچیکه ----
SIDEBAR_TOP_MARGIN = 20
SIDEBAR_BOTTOM_RESERVED = 35  
SIDEBAR_MIN_SCALE = 0.55       

# ---- تنظیمات تشخیص شکل ----
MIN_STROKE_POINTS = 10       
MIN_SHAPE_DIAGONAL = 60    
MIN_SHAPE_AREA = 1200       
CLOSURE_RATIO = 0.35        
APPROX_EPSILON_RATIO = 0.02  
CIRCULARITY_THRESHOLD = 0.75
SQUARE_ASPECT_TOLERANCE = 1.15


FINGER_TIPS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
FINGER_PIPS = {"thumb": 3, "index": 6, "middle": 10, "ring": 14, "pinky": 18}


def fingers_up(hand_landmarks, handedness_label):
    lm = hand_landmarks.landmark
    result = {}

    if handedness_label == "Right":
        result["thumb"] = lm[FINGER_TIPS["thumb"]].x < lm[FINGER_PIPS["thumb"]].x
    else:
        result["thumb"] = lm[FINGER_TIPS["thumb"]].x > lm[FINGER_PIPS["thumb"]].x

    for finger in ["index", "middle", "ring", "pinky"]:
        result[finger] = lm[FINGER_TIPS[finger]].y < lm[FINGER_PIPS[finger]].y

    return result


def detect_mode(finger_state):
    only_index = (
        finger_state["index"]
        and not finger_state["middle"]
        and not finger_state["ring"]
        and not finger_state["pinky"]
    )
    all_open = all(finger_state.values())

    if all_open:
        return "erase"
    if only_index:
        return "draw"
    return "idle"


# ---------------------------------------------------------
# سایدبار رنگ 
# ---------------------------------------------------------

def get_sidebar_layout(frame_w, frame_h):
    x1, x2 = 0, SIDEBAR_WIDTH
    center_x = x1 + SIDEBAR_WIDTH // 2

    n_colors = len(COLOR_OPTIONS)
    n_thick = len(THICKNESS_OPTIONS)

    nominal_color_h = n_colors * (SWATCH_RADIUS * 2) + (n_colors + 1) * SWATCH_MARGIN
    nominal_thick_h = n_thick * (THICKNESS_SWATCH_RADIUS * 2) + (n_thick + 1) * SWATCH_MARGIN
    nominal_total_h = nominal_color_h + SIDEBAR_SECTION_GAP + nominal_thick_h

    available_h = max(100, frame_h - SIDEBAR_TOP_MARGIN - SIDEBAR_BOTTOM_RESERVED)
    scale = min(1.0, available_h / nominal_total_h)
    scale = max(SIDEBAR_MIN_SCALE, scale)

    radius = max(14, int(SWATCH_RADIUS * scale))
    margin = max(8, int(SWATCH_MARGIN * scale))
    thick_radius = max(14, int(THICKNESS_SWATCH_RADIUS * scale))
    section_gap = max(14, int(SIDEBAR_SECTION_GAP * scale))

    total_height = (
        n_colors * (radius * 2) + (n_colors + 1) * margin
        + section_gap
        + n_thick * (thick_radius * 2) + (n_thick + 1) * margin
    )
    start_y = max(SIDEBAR_TOP_MARGIN, (frame_h - total_height) // 2)

    color_circles = []
    y = start_y
    for name, color in COLOR_OPTIONS:
        y += margin
        cy = y + radius
        color_circles.append((name, color, (center_x, cy, radius)))
        y = cy + radius
    y += margin + section_gap

    thickness_circles = []
    for name, thickness in THICKNESS_OPTIONS:
        y += margin
        cy = y + thick_radius
        thickness_circles.append((name, thickness, (center_x, cy, thick_radius)))
        y = cy + thick_radius

    return x1, x2, color_circles, thickness_circles


def draw_sidebar(image, x1, x2, color_circles, thickness_circles, current_color, current_thickness, frame_h):
    overlay = image.copy()
    cv2.rectangle(overlay, (x1, 0), (x2, frame_h), (40, 40, 40), -1)
    cv2.addWeighted(overlay, 0.55, image, 0.45, 0, image)

    # ---- بخش رنگ‌ها ----
    for name, color, (ccx, ccy, r) in color_circles:
        cv2.circle(image, (ccx, ccy), r, color, -1)
        cv2.circle(image, (ccx, ccy), r, (180, 180, 180), 1)

        if color == current_color:
            cv2.circle(image, (ccx, ccy), r + 5, (0, 255, 255), 2)

    # ---- بخش اندازه‌ی قلم ----
    for idx, (name, thickness, (ccx, ccy, r)) in enumerate(thickness_circles):
        icon_length = max(12, int(2 * r * PEN_ICON_LENGTH_RATIOS[idx]))
        draw_pen_icon(image, (ccx, ccy), thickness, icon_length)

        if thickness == current_thickness:
            cv2.circle(image, (ccx, ccy), r + 5, (0, 255, 255), 2)

    cv2.putText(
        image, "h: hide", (x1 + 25, frame_h - 20),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1
    )


def draw_pen_icon(image, center, thickness, length):
    cx, cy = center
    half = length // 2

    body_start = (cx + half, cy - half) 
    body_end = (cx - half, cy + half)   

    dx, dy = body_end[0] - body_start[0], body_end[1] - body_start[1]
    norm = max(1.0, np.hypot(dx, dy))
    ux, uy = dx / norm, dy / norm
    perp = (-uy, ux)

    tip_len = max(6, thickness * 1.6)
    tip_base = (int(body_end[0] - ux * tip_len), int(body_end[1] - uy * tip_len))
    half_w = max(2, thickness / 2)
    left = (int(tip_base[0] + perp[0] * half_w), int(tip_base[1] + perp[1] * half_w))
    right = (int(tip_base[0] - perp[0] * half_w), int(tip_base[1] - perp[1] * half_w))

    cv2.line(image, body_start, tip_base, (235, 235, 235), max(2, thickness), cv2.LINE_AA)
    cv2.circle(image, body_start, max(2, thickness // 2), (60, 170, 230), -1)


    tip_pts = np.array([left, right, body_end], dtype=np.int32)
    cv2.fillPoly(image, [tip_pts], (60, 60, 60))


def find_hovered_item(cx, cy, circles):
    for name, value, (ccx, ccy, r) in circles:
        dist = np.hypot(cx - ccx, cy - ccy)
        if dist <= r + 10:
            return value
    return None


# ---------------------------------------------------------
# تشخیص و تمیزکردن شکل
# ---------------------------------------------------------
def classify_shape(stroke_mask):
    contours, _ = cv2.findContours(stroke_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    if area < MIN_SHAPE_AREA:
        return None

    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return None

    approx = cv2.approxPolyDP(contour, APPROX_EPSILON_RATIO * perimeter, True)
    vertices = len(approx)
    circularity = 4 * np.pi * area / (perimeter ** 2)

    if vertices == 3:
        pts = approx.reshape(-1, 2)
        return ("triangle", pts)

    if vertices == 4:
        rect = cv2.minAreaRect(contour)
        (rw, rh) = rect[1]
        if rw == 0 or rh == 0:
            return None
        box = cv2.boxPoints(rect).astype(int)
        ratio = max(rw, rh) / min(rw, rh)
        shape_name = "square" if ratio < SQUARE_ASPECT_TOLERANCE else "rectangle"
        return (shape_name, box)

    if vertices > 4 and circularity > CIRCULARITY_THRESHOLD:
        (ccx, ccy), radius = cv2.minEnclosingCircle(contour)
        return ("circle", (int(ccx), int(ccy)), int(radius))

    return None


def draw_clean_shape(canvas, canvas_mask, shape, color, thickness):
    kind = shape[0]
    if kind == "circle":
        _, center, radius = shape
        cv2.circle(canvas, center, radius, color, thickness)
        cv2.circle(canvas_mask, center, radius, 255, thickness)
    elif kind == "triangle":
        pts = shape[1].reshape(-1, 1, 2)
        cv2.polylines(canvas, [pts], True, color, thickness)
        cv2.polylines(canvas_mask, [pts], True, 255, thickness)
    elif kind in ("square", "rectangle"):
        box = shape[1].reshape(-1, 1, 2)
        cv2.polylines(canvas, [box], True, color, thickness)
        cv2.polylines(canvas_mask, [box], True, 255, thickness)


def try_finalize_shape(canvas, canvas_mask, stroke_mask, stroke_points, color, thickness):
    if stroke_mask is None or len(stroke_points) < MIN_STROKE_POINTS:
        return False

    xs = [p[0] for p in stroke_points]
    ys = [p[1] for p in stroke_points]
    bbox_w = max(xs) - min(xs)
    bbox_h = max(ys) - min(ys)
    diagonal = np.hypot(bbox_w, bbox_h)
    if diagonal < MIN_SHAPE_DIAGONAL:
        return False

    start, end = stroke_points[0], stroke_points[-1]
    closure_dist = np.hypot(end[0] - start[0], end[1] - start[1])
    if closure_dist > CLOSURE_RATIO * diagonal:
        return False  

    shape = classify_shape(stroke_mask)
    if shape is None:
        return False

    canvas[stroke_mask > 0] = (0, 0, 0)
    canvas_mask[stroke_mask > 0] = 0

    draw_clean_shape(canvas, canvas_mask, shape, color, thickness)
    return True


def resize_for_display(image, max_height):
    h, w = image.shape[:2]
    if h <= max_height:
        return image
    scale = max_height / float(h)
    new_w = max(1, int(w * scale))
    return cv2.resize(image, (new_w, max_height), interpolation=cv2.INTER_AREA)


def main():
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(CAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    if not cap.isOpened():
        print("خطا: دوربین پیدا نشد یا قابل دسترسی نیست.")
        return

    max_display_h = get_safe_max_display_height()
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.moveWindow(WINDOW_NAME, 20, 10)

    canvas = None
    canvas_mask = None

    smoothed_point = None
    prev_point = None

    candidate_mode = "idle"
    candidate_count = 0
    stable_mode = "idle"

    current_color = COLOR_OPTIONS[3][1] 
    current_thickness = THICKNESS_OPTIONS[1][1] 
    sidebar_visible = True
    shape_snap_enabled = True
    blackboard_mode = False

    stroke_points = []
    stroke_mask = None

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.6,
    ) as hands:

        while True:
            success, frame = cap.read()
            if not success:
                print("خطا در خواندن فریم از دوربین.")
                break

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            if canvas is None:
                canvas = np.zeros_like(frame)
                canvas_mask = np.zeros((h, w), dtype=np.uint8)

            background = np.zeros_like(frame) if blackboard_mode else frame

            previous_stable_mode = stable_mode 

            sidebar_x1, sidebar_x2, color_circles, thickness_circles = get_sidebar_layout(w, h)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb_frame)

            raw_mode = "idle"
            cx, cy = None, None

            if results.multi_hand_landmarks and results.multi_handedness:
                hand_landmarks = results.multi_hand_landmarks[0]
                handedness_label = results.multi_handedness[0].classification[0].label

                mp_drawing.draw_landmarks(
                    frame, hand_landmarks, mp_hands.HAND_CONNECTIONS
                )

                state = fingers_up(hand_landmarks, handedness_label)
                raw_mode = detect_mode(state)

                index_tip = hand_landmarks.landmark[FINGER_TIPS["index"]]
                cx, cy = int(index_tip.x * w), int(index_tip.y * h)

            in_sidebar = sidebar_visible and cx is not None and cx <= sidebar_x2

            if in_sidebar:
                hovered_color = find_hovered_item(cx, cy, color_circles)
                if hovered_color is not None:
                    current_color = hovered_color

                hovered_thickness = find_hovered_item(cx, cy, thickness_circles)
                if hovered_thickness is not None:
                    current_thickness = hovered_thickness

                prev_point = None
                smoothed_point = None
                stable_mode = "select"
                candidate_mode = "idle"
                candidate_count = 0

            else:
                if raw_mode == candidate_mode:
                    candidate_count += 1
                else:
                    candidate_mode = raw_mode
                    candidate_count = 1

                if stable_mode == "draw" and raw_mode != "draw":
                    new_stable_mode = raw_mode
                    candidate_mode = raw_mode
                    candidate_count = MODE_STABILITY_FRAMES
                elif candidate_count >= MODE_STABILITY_FRAMES:
                    new_stable_mode = candidate_mode
                else:
                    new_stable_mode = stable_mode

                if new_stable_mode != stable_mode:
                    prev_point = None
                    smoothed_point = None

                stable_mode = new_stable_mode

                if cx is not None and stable_mode == "draw":
                    if smoothed_point is None:
                        smoothed_point = (cx, cy)
                    else:
                        sx = int(SMOOTHING_FACTOR * cx + (1 - SMOOTHING_FACTOR) * smoothed_point[0])
                        sy = int(SMOOTHING_FACTOR * cy + (1 - SMOOTHING_FACTOR) * smoothed_point[1])
                        smoothed_point = (sx, sy)

                    if prev_point is not None:
                        dist = np.hypot(
                            smoothed_point[0] - prev_point[0],
                            smoothed_point[1] - prev_point[1],
                        )
                        if dist <= MAX_JUMP_DISTANCE:
                            cv2.line(canvas, prev_point, smoothed_point, current_color, current_thickness)
                            cv2.line(canvas_mask, prev_point, smoothed_point, 255, current_thickness)
                            if stroke_mask is not None:
                                cv2.line(stroke_mask, prev_point, smoothed_point, 255, current_thickness)

                    stroke_points.append(smoothed_point)
                    prev_point = smoothed_point

                elif cx is not None and stable_mode == "erase":
                    cv2.circle(canvas, (cx, cy), ERASE_RADIUS, (0, 0, 0), -1)
                    cv2.circle(canvas_mask, (cx, cy), ERASE_RADIUS, 0, -1)
                    cv2.circle(background, (cx, cy), ERASE_RADIUS, (255, 255, 255), 2)
                    prev_point = None
                    smoothed_point = None

                else: 
                    prev_point = None
                    smoothed_point = None

            # ---- مدیریت شروع/پایان مسیر برای تشخیص شکل ----
            if stable_mode == "draw" and previous_stable_mode != "draw":
                stroke_points = []
                stroke_mask = np.zeros((h, w), dtype=np.uint8)

            if previous_stable_mode == "draw" and stable_mode != "draw":
                if shape_snap_enabled:
                    try_finalize_shape(canvas, canvas_mask, stroke_mask, stroke_points, current_color, current_thickness)
                stroke_points = []
                stroke_mask = None

            # ---- ترکیب Canvas با پس زمینه----
            mask_inv = cv2.bitwise_not(canvas_mask)
            frame_bg = cv2.bitwise_and(background, background, mask=mask_inv)
            canvas_fg = cv2.bitwise_and(canvas, canvas, mask=canvas_mask)
            combined = cv2.add(frame_bg, canvas_fg)

            # ---- نمایش وضعیت فعلی ----
            mode_text = {
                "draw": "Draw",
                "erase": "Erase",
                "idle": "Idle",
                "select": "Select Color",
            }[stable_mode]
            cv2.putText(
                combined, f"Mode: {mode_text}", (SIDEBAR_WIDTH + 20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
            )
            snap_text = f"Shape Snap: {'ON' if shape_snap_enabled else 'OFF'}"
            cv2.putText(
                combined, snap_text, (SIDEBAR_WIDTH + 20, 75),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2
            )
            if blackboard_mode:
                cv2.putText(
                    combined, "Blackboard: ON", (SIDEBAR_WIDTH + 20, 105),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
                )
            cv2.putText(
                combined, "q: exit | c: clear | h: colors | s: shape-snap | b: blackboard", (SIDEBAR_WIDTH + 20, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1
            )

            if sidebar_visible:
                draw_sidebar(
                    combined, sidebar_x1, sidebar_x2,
                    color_circles, thickness_circles,
                    current_color, current_thickness, h
                )
                if in_sidebar:
                    cv2.circle(combined, (cx, cy), 10, (0, 255, 255), -1)

            cv2.imshow(WINDOW_NAME, resize_for_display(combined, max_display_h))

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("c"):
                canvas = np.zeros_like(frame)
                canvas_mask = np.zeros((h, w), dtype=np.uint8)
                prev_point = None
                smoothed_point = None
                stroke_points = []
                stroke_mask = None
            elif key == ord("h"):
                sidebar_visible = not sidebar_visible
            elif key == ord("s"):
                shape_snap_enabled = not shape_snap_enabled
            elif key == ord("b"):
                blackboard_mode = not blackboard_mode

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
