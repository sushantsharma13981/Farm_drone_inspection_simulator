# 🚀 Quick Start Guide

## 5-Minute Setup (Basic System)

```bash
# 1. Install dependencies
cd backend
pip install flask flask-cors pybullet numpy scipy opencv-python

# 2. Start server
python3 app.py

# 3. Open browser
# Navigate to: http://localhost:5000
```

**Done!** You now have a working farm drone inspection system with camera streaming.

---

## 10-Minute Setup (With AI)

```bash
# 1. Install all dependencies
cd backend
pip install flask flask-cors pybullet numpy scipy opencv-python
pip install torch torchvision ultralytics

# 2. Add AI models
# Download or copy these files to backend/:
# - best.pt (YOLO model)
# - gnn_deep_final.pth (GNN model)

# 3. Start server
python3 app.py

# Look for: "✅ AI Detection: ENABLED"

# 4. Open browser
# Navigate to: http://localhost:5000
```

**Done!** You have the full system with AI disease detection.

---

## First Mission

### 1. Add a Farm
- Enter name: "Test Farm"
- Enter location: "Field 1"
- Set boundaries: X[-2, 2], Y[-2, 2]
- Click **DRAW** to visualize
- Click **SAVE**

### 2. Deploy Drone
- Select "Test Farm" from list
- Click **DEPLOY DRONE**
- PyBullet window opens
- Watch drone fly autonomously

### 3. Monitor Mission
- **Live Camera**: See drone's view
- **AI Detection**: See disease diagnosis (if enabled)
- **Position**: Track X, Y, Z coordinates
- **Waypoints**: Monitor progress

### 4. Control Options
- **STALL**: Pause mission (click again to resume)
- **ABORT**: Emergency return to home

---

## File Checklist

### Required Files
```
backend/
├── app.py                ✅ Flask server
├── DSLPIDControl.py      ✅ PID controller
├── BaseControl.py        ✅ Base control
├── enums.py              ✅ Enumerations
└── cf2p.urdf             ✅ Drone model

frontend/
├── index.html            ✅ UI interface
├── style.css             ✅ Styling
└── script.js             ✅ Logic
```

### Optional Files (For AI)
```
backend/
├── best.pt               ⭕ YOLO model
├── gnn_deep_final.pth    ⭕ GNN model
└── test/images/          ⭕ Textures
    ├── leaf1.jpg
    ├── leaf2.jpg
    └── ...
```

---

## Verification Commands

```bash
# Check Python version
python3 --version  # Should be 3.8+

# Check dependencies
python3 -c "import flask, pybullet, cv2; print('✅ Core deps OK')"

# Check AI dependencies (optional)
python3 -c "import torch, ultralytics; print('✅ AI deps OK')"

# Test server
curl http://localhost:5000/api/drone/status

# Expected: {"success": true, "status": {...}}
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Port 5000 in use** | Edit `app.py`: change port to 5001 |
| **PyBullet GUI not opening** | Install: `sudo apt-get install xvfb` |
| **Camera shows black** | Check: `glxinfo \| grep OpenGL` |
| **AI not working** | Run without AI, it's optional |
| **Connection refused** | Check if server is running |

---

## Quick Commands

```bash
# Start server
cd backend && python3 app.py

# Stop server
Ctrl+C

# Restart server
Ctrl+C then python3 app.py

# View logs
# Just look at terminal

# Check if running
ps aux | grep "python3 app.py"

# Kill if stuck
pkill -f "python3 app.py"
```

---

## Default Settings

| Parameter | Value | Location |
|-----------|-------|----------|
| Server Port | 5000 | app.py |
| Hover Altitude | 1.4m | app.py |
| Sweep Step | 0.8m | app.py |
| Cruise Speed | 0.5 m/s | app.py |
| Camera Resolution | 640x480 | app.py |
| AI Frame Rate | 10 FPS | app.py |

---

## Keyboard Shortcuts (Browser)

| Key | Action |
|-----|--------|
| F12 | Open developer console |
| Ctrl+R | Refresh page |
| Ctrl+Shift+R | Hard refresh (clear cache) |
| Ctrl+- | Zoom out |
| Ctrl++ | Zoom in |

---

## Common Tasks

### Change Field Size
1. Edit boundaries in "Add Farm" section
2. Click DRAW to preview
3. Click SAVE

### Change Flight Height
Edit `app.py`:
```python
HOVER_ALTITUDE = plant_height + 0.6  # Change 0.6 to desired height
```

### Change Sweep Spacing
Edit `app.py`:
```python
SWEEP_STEP = 0.8  # Change to 0.5 for tighter, 1.0 for wider
```

### Disable AI
Edit `app.py`:
```python
AI_AVAILABLE = False  # Force disable
```

---

## URLs

| Resource | URL |
|----------|-----|
| **Main UI** | http://localhost:5000 |
| **Drone Status** | http://localhost:5000/api/drone/status |
| **Farms List** | http://localhost:5000/api/farms |
| **Camera Stream** | http://localhost:5000/api/camera/stream |

---

## Getting Help

1. **Check Logs**: Look at terminal where server runs
2. **Check Browser Console**: Press F12 → Console tab
3. **Read Documentation**:
   - README.md - Full guide
   - AI_SETUP.md - AI features
   - INTEGRATION_SUMMARY.md - Technical details

---

## Next Steps

✅ Basic setup complete → Try first mission  
✅ First mission successful → Add more farms  
✅ Multiple missions working → Enable AI features  
✅ AI working → Customize parameters  
✅ System mastered → Deploy to production  

**Happy Flying!** 🚁