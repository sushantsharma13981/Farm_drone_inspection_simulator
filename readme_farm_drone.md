# Farm Drone Inspection Simulator 🚁🌾

A complete client–server drone simulation system designed for **autonomous farm inspection**.

✔ Drone simulation in **PyBullet**  
✔ Interactive farm setup via **web UI**  
✔ Path planning + mission execution via **Flask API**  
✔ Robust PID drone control  

---

## 📂 Folder Structure

```
Farm_drone_inspection_simulator/
│
├── backend/
│   ├── app.py
│   ├── drone_sweeper.py
│   ├── BaseControl.py
│   ├── DSLPIDControl.py
│   ├── enums.py
│   ├── cf2p.urdf
│   └── ...
│
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js
```

---

## 📦 Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Install Dependencies

```bash
# Install all required packages
pip install flask pybullet numpy scipy
```

**Or create a requirements.txt and install from it:**

```bash
pip install -r requirements.txt
```

### Required Packages:

- **flask** - Web framework for API backend
- **pybullet** - Physics simulation engine
- **numpy** - Numerical computing library
- **scipy** - Scientific computing library (for PID control)

---

## 💻 How to Run

### ▶ Backend (Flask)

```bash
cd backend
python3 app.py
```

**Runs at:**  
`http://127.0.0.1:5000`

### 🌐 Frontend (UI)

```bash
cd frontend
python3 -m http.server 8000
```

**Open in browser:**  
`http://localhost:8000`

---

## 🔄 System Workflow

```
Client UI ➜ Flask API ➜ PyBullet Drone Simulator
```

**User draws field → API sends coordinates → Drone sweeps farm → Detection simulation**

---

## ✨ Features

- ✅ Draw & save farm regions
- ✅ Automatic sweep trajectory generation
- ✅ PID-based control (Position + Attitude)
- ✅ Field boundary visualization in PyBullet
- ✅ Fully interactive UI

---

## 🛠 Tech Stack

| Component        | Technology              |
|------------------|-------------------------|
| Simulation       | PyBullet                |
| API Backend      | Flask                   |
| Frontend UI      | HTML, CSS, JavaScript   |
| Control System   | DSL PID                 |

---

## 📸 Screenshots (To add)

Add later inside `/docs/images/`:
- `simulation_start.png`
- `mission_complete.png`

---

## 👨‍💻 Authors

**[Sushant Sharma](https://github.com/sushantsharma13981)** — IIT Mandi  
**[Author Name 2](https://github.com/username2)** — IIT Mandi  
**[Author Name 3](https://github.com/username3)** — IIT Mandi  

Drone-Field Automation Project 🌱🤖

---

⭐ **Star this repo if you like the project!**