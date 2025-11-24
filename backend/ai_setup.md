# AI Disease Detection Setup Guide

This guide explains how to enable the optional AI-powered plant disease detection feature in the Farm Drone Inspection System.

## Overview

The system supports **optional** AI-based plant disease detection using:
- **YOLO (You Only Look Once)**: For leaf detection in camera frames
- **Graph Neural Network (GNN)**: For disease classification

**The system works perfectly without AI** - it will simply skip disease detection and show camera feed with basic status overlay.

## Prerequisites for AI Features

### 1. Hardware Requirements
- **GPU Recommended**: NVIDIA GPU with CUDA support
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: Additional 2GB for AI models

### 2. Software Requirements
- Python 3.8+
- CUDA Toolkit (for GPU acceleration)
- PyTorch with CUDA support

## Installation Steps

### Option 1: Install AI Dependencies

```bash
# Install PyTorch (with CUDA 11.8 - adjust for your system)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install YOLO
pip install ultralytics

# Verify installation
python3 -c "import torch; print(f'PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}')"
```

### Option 2: CPU-Only Installation (Slower)

```bash
# Install PyTorch (CPU only)
pip install torch torchvision torchaudio

# Install YOLO
pip install ultralytics
```

## Model Files Setup

### Required Files

Place these files in your `backend/` directory:

1. **best.pt** - YOLO model for leaf detection
2. **gnn_deep_final.pth** - GNN model for disease classification
3. **test/images/** - Directory with leaf texture images (optional)

### Directory Structure

```
backend/
├── app.py
├── best.pt              # YOLO model
├── gnn_deep_final.pth   # GNN model
├── test/
│   └── images/
│       ├── leaf1.jpg
│       ├── leaf2.jpg
│       └── ...
├── DSLPIDControl.py
├── BaseControl.py
├── enums.py
└── cf2p.urdf
```

### Creating Model Files

#### If you don't have model files:

**For YOLO Model:**
```python
# Train your own or use a pre-trained model
from ultralytics import YOLO

# Start with a pre-trained model
model = YOLO('yolov8n.pt')  # Download pre-trained

# Train on your dataset (optional)
model.train(data='your_dataset.yaml', epochs=100)

# Save
model.save('best.pt')
```

**For GNN Model:**
- You'll need to train the DeepLeafMPNN model on your disease dataset
- Or contact the repository maintainer for pre-trained weights

#### Quick Test Without Real Models:

The system will automatically disable AI if models are not found and continue with basic functionality.

## Configuration

### Update Paths (if needed)

Edit `backend/app.py`:

```python
# ================= CONFIGURATION =================
TEXTURE_DIR = "test/images"      # Path to texture images
YOLO_PATH = "best.pt"            # Path to YOLO model
GNN_PATH = "gnn_deep_final.pth"  # Path to GNN model
```

### Supported Disease Classes

The GNN model classifies leaves into these categories:

1. Early Blight
2. Healthy
3. Late Blight
4. Leaf Miner
5. Leaf Mold
6. Mosaic Virus
7. Septoria
8. Spider Mites
9. Yellow Leaf Curl
10. Bacterial Spot

## Running the System

### With AI Enabled

```bash
cd backend
python3 app.py
```

You should see:
```
✅ AI modules loaded successfully
✅ YOLO model loaded
✅ GNN model loaded
✅ AI Detection: ENABLED
🚁 Farm Drone Inspection Server Starting...
```

### Without AI (Graceful Degradation)

If AI dependencies or models are missing:

```
⚠️ AI modules not available. Running without disease detection.
🚁 Farm Drone Inspection Server Starting...
```

The system still works with:
- ✅ Full drone control
- ✅ Camera streaming
- ✅ Mission management
- ❌ Disease detection (disabled)

## Verifying AI Features

### 1. Check Server Logs

Look for these messages in terminal:
```
✅ AI modules loaded successfully
✅ Found 150 texture images
✅ YOLO model loaded
✅ GNN model loaded
```

### 2. Check UI

When AI is enabled, you'll see:
- **"AI Detection"** row in Simulator info panel
- Real-time disease classification on camera feed
- Confidence percentages

### 3. API Check

```bash
curl http://localhost:5000/api/drone/status
```

Response includes:
```json
{
  "status": {
    "ai_available": true,
    "ai_diagnosis": "HEALTHY",
    "ai_confidence": 95.3
  }
}
```

## Performance Considerations

### With GPU (CUDA)
- AI processing: ~10 FPS
- No impact on flight smoothness
- Recommended setup

### With CPU Only
- AI processing: ~2-3 FPS
- May cause slight lag
- Still usable for demos

### Without AI
- Camera: ~30 FPS
- No performance impact
- Recommended if AI not needed

## Troubleshooting

### "AI modules not available"

**Solution:**
```bash
pip install torch torchvision ultralytics
```

### "YOLO model not found"

**Solution:**
```bash
# Download a pre-trained model
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt -O best.pt
```

Or:
```python
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.save('best.pt')
```

### "GNN model not found"

**Solution:**
- The GNN model needs to be trained on your specific dataset
- Or run without AI (system still works)
- Contact project maintainer for pre-trained weights

### CUDA Out of Memory

**Solution:**
```python
# Edit app.py, reduce batch size or use CPU
DEVICE = "cpu"  # Force CPU usage
```

### Slow Performance

**Solutions:**
1. Reduce AI frame rate:
```python
# In app.py, change from % 5 to % 10
if camera_frame_counter % 10 == 0:  # Run AI every 10 frames instead of 5
```

2. Use smaller YOLO model:
```python
detector = YOLO('yolov8n.pt')  # nano (fastest)
# instead of
detector = YOLO('yolov8m.pt')  # medium
```

## Testing AI Features

### 1. Deploy Drone

- Add a farm
- Select it
- Click "DEPLOY DRONE"

### 2. Watch for AI Detection

In the UI, you should see:
- Camera feed with bounding boxes around detected leaves
- "AI Detection" showing classification (e.g., "HEALTHY", "LATE BLIGHT")
- Confidence percentage

### 3. Check Logs

Terminal will show:
```
✅ AI Detection: ENABLED
[AI] Detected: HEALTHY (95.3%)
[AI] Detected: LATE BLIGHT (87.1%)
```

## Disabling AI (Even if Installed)

Edit `backend/app.py`:

```python
# Force disable AI
AI_AVAILABLE = False
```

Or remove model files:
```bash
rm best.pt gnn_deep_final.pth
```

## Training Your Own Models

### YOLO Training

```python
from ultralytics import YOLO

# Prepare dataset in YOLO format
# dataset.yaml:
# train: /path/to/train/images
# val: /path/to/val/images
# names: ['leaf']

model = YOLO('yolov8n.pt')
model.train(
    data='dataset.yaml',
    epochs=100,
    imgsz=640,
    batch=16,
    name='leaf_detector'
)
```

### GNN Training

The GNN model requires:
- Leaf crop images
- Disease labels
- Geometric features (bounding box coordinates)
- Graph structure (adjacency matrix)

Contact the research team for training code and datasets.

## FAQ

**Q: Can I use the system without AI?**  
A: Yes! The system works perfectly without AI. You'll have full drone control and camera streaming, just no disease detection.

**Q: Do I need a GPU?**  
A: No, but recommended. CPU works but slower.

**Q: Can I use my own YOLO model?**  
A: Yes! Just name it `best.pt` or update `YOLO_PATH` in app.py.

**Q: What if textures are missing?**  
A: Plants will have solid green leaves instead of textured ones. Everything else works fine.

**Q: How accurate is the AI?**  
A: Depends on your trained models. With good training data, 85-95% accuracy is achievable.

**Q: Can I add more disease classes?**  
A: Yes, but you need to retrain the GNN model with your new classes and update `CLASS_NAMES` in app.py.

## Support

For AI-related issues:
1. Check this guide
2. Review terminal logs
3. Try running without AI first
4. Check PyTorch/CUDA installation

For general system issues, see main README.md

---

**Remember**: AI is optional. The core system provides full autonomous drone inspection with live camera streaming regardless of AI availability.