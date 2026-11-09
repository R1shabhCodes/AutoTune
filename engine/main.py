# main.py
# FastAPI application backend that serves the API, WebSocket stream, and dashboard static files.
# Preserves all existing endpoints while supporting AutoTune 2.0 experiment state.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import asyncio
from typing import Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import agent_loop
import config
import db

# Run database setup and migrations on boot
db.apply_migrations()

app = FastAPI(title="AutoTune RAG Optimizer", description="Universal RAG Evaluation, Observability and Optimization Platform")

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
    experiment_id: Optional[str] = None
    project_id: str = "default"

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
            # Keep socket open and listen for heartbeat
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def run_optimization_wrapper(iterations: int, experiment_id: Optional[str] = None, project_id: str = "default"):
    """Wrapper to execute the optimization loop in the background and stream updates."""
    global is_running
    try:
        async def ws_callback(data: dict):
            await manager.broadcast({
                "type": "iteration",
                "data": data
            })
            
        await agent_loop.run_optimization(
            num_iterations=iterations,
            on_iteration_callback=ws_callback,
            experiment_id=experiment_id,
            project_id=project_id
        )
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
    background_tasks.add_task(
        run_optimization_wrapper,
        payload.iterations,
        payload.experiment_id,
        payload.project_id
    )
    
    await manager.broadcast({"type": "status", "data": "running"})
    
    return {
        "status": "started",
        "message": f"Started optimization run of {payload.iterations} iterations.",
        "experiment_id": payload.experiment_id
    }

@app.get("/iterations")
def get_iterations_endpoint(experiment_id: Optional[str] = Query(None)):
    """Returns the full log of optimization iterations from the database."""
    if not os.path.exists(DB_PATH):
        return []
        
    return db.get_experiment_trials(experiment_id=experiment_id)

@app.get("/trials/{trial_id}/evaluations")
def get_trial_evaluations_endpoint(trial_id: str):
    """Returns question-level granular evaluation telemetry for a trial."""
    if not os.path.exists(DB_PATH):
        return []
    return db.get_question_evaluations_for_trial(trial_id)

@app.get("/best")
def get_best_config_endpoint(experiment_id: Optional[str] = Query(None)):
    """Returns the current best configuration and its evaluation score/metrics."""
    import importlib
    importlib.reload(config)
    
    best_trial = db.get_experiment_best(experiment_id=experiment_id)
    
    if best_trial:
        return {
            "score": best_trial["new_score"],
            "composite_score": best_trial["composite_score"] if best_trial["composite_score"] is not None else best_trial["new_score"],
            "avg_latency_ms": best_trial["avg_latency_ms"] if best_trial["avg_latency_ms"] is not None else 0.0,
            "total_tokens": best_trial["total_tokens"] if best_trial["total_tokens"] is not None else 0,
            "config": config.CONFIG,
            "experiment_id": best_trial.get("experiment_id"),
            "iteration_number": best_trial.get("iteration_number")
        }

    return {
        "score": 0.0,
        "composite_score": 0.0,
        "avg_latency_ms": 0.0,
        "total_tokens": 0,
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
