# main.py
# FastAPI application backend that serves the API, WebSocket stream, and dashboard static files.
# This file is fixed and is NOT modified by the optimization agent.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import agent_loop
import config

# Run database setup and migrations on boot
agent_loop.init_db()

app = FastAPI(title="AutoTune RAG Optimizer", description="Dashboard & API for the self-improving RAG pipeline")

# Enable CORS for React local development (typically on port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global run state
is_running = False
engine_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(engine_dir, "autotune.db")

class RunPayload(BaseModel):
    iterations: int = 15

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send initial status
        await websocket.send_json({
            "type": "status",
            "data": "running" if is_running else "idle"
        })

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep the socket open and listen for heartbeat/messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def run_optimization_wrapper(iterations: int):
    """Wrapper to execute the optimization loop in the background and update status."""
    global is_running
    try:
        async def ws_callback(data: dict):
            # Send iteration result via websocket
            await manager.broadcast({
                "type": "iteration",
                "data": data
            })
            
        # Run optimization
        await agent_loop.run_optimization(iterations, on_iteration_callback=ws_callback)
    except Exception as e:
        print(f"Error in background optimization task: {e}")
    finally:
        is_running = False
        await manager.broadcast({
            "type": "status",
            "data": "idle"
        })

@app.post("/run")
async def run_optimization_endpoint(payload: RunPayload, background_tasks: BackgroundTasks):
    """Kicks off the optimization loop as a background task."""
    global is_running
    if is_running:
        return {"status": "error", "message": "An optimization run is already in progress."}
        
    is_running = True
    background_tasks.add_task(run_optimization_wrapper, payload.iterations)
    
    # Broadcast status change to running
    await manager.broadcast({"type": "status", "data": "running"})
    
    return {"status": "started", "message": f"Started optimization run of {payload.iterations} iterations."}

@app.get("/iterations")
def get_iterations_endpoint():
    """Returns the full log of optimization iterations from the database."""
    if not os.path.exists(DB_PATH):
        return []
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT iteration_number, hypothesis, param, old_value, new_value, old_score, new_score, accepted, timestamp, motivated_by
        FROM iterations
        ORDER BY iteration_number DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/best")
def get_best_config_endpoint():
    """Returns the current best configuration and its evaluation score."""
    # Ensure config is loaded fresh from file
    import importlib
    importlib.reload(config)
    
    best_score = 0.0
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Find the maximum score achieved in any accepted iteration
        cursor.execute("SELECT MAX(new_score) FROM iterations WHERE accepted = 1")
        val = cursor.fetchone()[0]
        if val is not None:
            best_score = val
        conn.close()
        
    return {
        "score": best_score,
        "config": config.CONFIG
    }

@app.get("/holdout_score")
def get_holdout_score_endpoint():
    """Runs the current best configuration against the holdout evaluation set and returns the score."""
    import importlib
    importlib.reload(config)
    import eval_harness
    
    res = eval_harness.evaluate_holdout(config.CONFIG)
    return {
        "score": res["aggregate_score"],
        "results": res["results"]
    }

@app.get("/report/{run_id}")
def get_report_endpoint(run_id: str):
    """Generates the Markdown optimization report and returns it as a file download."""
    import report
    import datetime
    from fastapi.responses import Response
    report_md = report.generate_report(run_id)
    filename = f"autotune_report_{run_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    return Response(
        content=report_md,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

# Mount the static React build files if they exist (dashboard/dist)
dist_path = os.path.join(os.path.dirname(engine_dir), "dashboard", "dist")
if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")
else:
    print(f"Warning: Static files path '{dist_path}' not found. Build the frontend to serve from FastAPI.")
