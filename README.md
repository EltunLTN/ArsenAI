# AI Arsen / BakıFlow

This is a demo project for AI-based traffic signal control and intersection simulation. The repository contains two separate experiences:

- Web dashboard and live data stream: `backend.py`, `index.html`, `dashboard.html`
- Matplotlib-based desktop simulation: `simulation.py`

## Features

- Live traffic state tracking for 4 intersections
- Real-time data streaming over WebSocket
- Emergency mode and signal regime switching
- AI-oriented signal timing logic
- Dashboard visualizations with Chart.js
- Standalone traffic simulation with Matplotlib

## Project Structure

- `backend.py`: FastAPI app, WebSocket stream, and static file serving
- `simulation.py`: Simulation with the intersection model and traffic behavior
- `index.html`: Main web interface
- `dashboard.html`: Detailed dashboard interface
- `simulation.html`: Alternate two-intersection UI demo
- `images/`: Camera images

## Requirements

- Python 3.10+ is recommended
- The following packages are required:
  - `fastapi`
  - `uvicorn`
  - `matplotlib`

No extra browser-side setup is needed; `chart.js` is loaded from a CDN.

## Setup

Create a virtual environment and install the dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn matplotlib
```

If your project needs additional packages, install them into the same environment.

## Running

### Web application

Start the FastAPI server:

```powershell
uvicorn backend:app --reload
```

Then open one of these URLs in your browser:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/index.html`
- `http://127.0.0.1:8000/dashboard.html`

### Matplotlib simulation

```powershell
python simulation.py
```

## Backend Endpoints

- `GET /ws`: WebSocket connection for live simulation data
- `GET /emergency/{intersection_id}`: Triggers emergency mode for the selected intersection
- `POST /toggle/{intersection_id}/{mode}`: Changes the intersection mode

## Notes

- The backend serves the project root as a static directory, so the HTML files can be opened directly.
- The images in the `images/` folder are used by the dashboard.
- The simulation code is kept in a single file for hackathon/demo purposes.
