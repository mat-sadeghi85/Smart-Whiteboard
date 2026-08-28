# Smart Whiteboard

A virtual whiteboard controlled entirely by hand gestures via webcam. Draw in the air with your index finger, erase with an open palm, and let the app auto-clean simple shapes (circles, squares, rectangles, triangles) into perfect geometry.

## Features

- Draw by tracking your index fingertip (MediaPipe Hands)
- Erase by opening all five fingers
- On-screen sidebar to pick pen color and thickness
- Automatic shape detection and cleanup (Shape Snap)
- Blackboard mode (draw on a black background instead of the live camera feed)
- Display auto-scales to fit your screen

## Requirements

- Python **3.9 – 3.12**
- A working webcam
- Windows, macOS, or Linux

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/USERNAME/smart-whiteboard.git
cd smart-whiteboard
```

### 2. Create a virtual environment

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

You'll see `(venv)` at the start of your terminal prompt once it's active.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
python main.py
```

(Use `python3` instead of `python` on macOS/Linux if needed.)

## Controls

| Key | Action |
|---|---|
| `q` | Quit |
| `c` | Clear the board |
| `h` | Toggle sidebar |
| `s` | Toggle shape snap |
| `b` | Toggle blackboard mode |

**Gestures:** only your index finger up → draw · all fingers up → erase · point at the sidebar to pick color/thickness.

## Troubleshooting

- **Camera not found:** close other apps using the webcam (Zoom, Teams, etc.) and check OS camera permissions.
- **mediapipe fails to install:** confirm you're on Python 3.9–3.12 (`python --version`).
- **Laggy video:** lower `FRAME_WIDTH` / `FRAME_HEIGHT` at the top of `main.py`.

## Deactivate the virtual environment

```bash
deactivate
```
