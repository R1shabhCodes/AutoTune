# report.py
# Generates a shareable Markdown report compiling optimization iterations and stats.
# This file is fixed and is NOT modified by the optimization agent.

import os
import sqlite3
import datetime
import json
import base64
import io
import config
import eval_harness

def generate_report(run_id: str = "current") -> str:
    """
    Pulls all iterations from SQLite database and formats a comprehensive,
    self-contained Markdown optimization report with inline encoded charts.
    """
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(engine_dir, "autotune.db")
    
    if not os.path.exists(db_path):
        return "# Error: AutoTune database (autotune.db) not found."
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT iteration_number, hypothesis, param, old_value, new_value, old_score, new_score, accepted, timestamp, motivated_by
        FROM iterations
        ORDER BY iteration_number ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return "# Error: No iterations found in the AutoTune database."
        
    iterations = [dict(r) for r in rows]
    baseline = iterations[0]
    
    # Identify the best score and its corresponding iteration config
    best_iteration = baseline
    for item in iterations:
        if item["accepted"] and item["new_score"] >= best_iteration["new_score"]:
            best_iteration = item
            
    starting_score = baseline["new_score"]
    final_score = best_iteration["new_score"]
    total_runs = len(iterations) - 1  # Excluding baseline (0)
    
    # Calculate current holdout score using the active best configuration
    holdout_score_val = 0.0
    try:
        res = eval_harness.evaluate_holdout(config.CONFIG)
        holdout_score_val = res["aggregate_score"]
    except Exception as e:
        print(f"Warning: Could not compute holdout score for report: {e}")
        
    # Generate progress chart
    chart_base64 = ""
    chart_ascii = ""
    try:
        import matplotlib
        matplotlib.use('Agg')  # Headless backend
        import matplotlib.pyplot as plt
        
        x = [item["iteration_number"] for item in iterations]
        y = [item["new_score"] for item in iterations]
        
        plt.figure(figsize=(9, 4.5))
        plt.style.use('dark_background')
        
        # Plot score curve
        plt.plot(x, y, color='#818cf8', marker='o', linewidth=2.5, markersize=4, label='Accuracy Progression')
        
        # Color-code accepted vs rejected markers
        accepted_x = [item["iteration_number"] for item in iterations if item["accepted"] and item["iteration_number"] > 0]
        accepted_y = [item["new_score"] for item in iterations if item["accepted"] and item["iteration_number"] > 0]
        plt.scatter(accepted_x, accepted_y, color='#10b981', s=70, zorder=5, label='Accepted Config')
        
        rejected_x = [item["iteration_number"] for item in iterations if not item["accepted"] and item["iteration_number"] > 0]
        rejected_y = [item["new_score"] for item in iterations if not item["accepted"] and item["iteration_number"] > 0]
        if rejected_x:
            plt.scatter(rejected_x, rejected_y, color='#ef4444', s=70, zorder=5, label='Rejected Config')
            
        plt.title('AutoTune Score Progression Trajectory', fontsize=12, pad=15, color='#e2e8f0', fontweight='bold')
        plt.xlabel('Iteration Number', color='#94a3b8', fontsize=9)
        plt.ylabel('Tuning Accuracy Score', color='#94a3b8', fontsize=9)
        plt.ylim(-0.05, 1.05)
        plt.grid(True, linestyle='--', alpha=0.15, color='#334155')
        plt.legend(frameon=True, facecolor='#1e293b', edgecolor='none', loc='lower right', fontsize=8)
        plt.tight_layout()
        
        # Convert chart to base64 Data URI
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        plt.close()
        buf.seek(0)
        chart_base64 = base64.b64encode(buf.read()).decode('utf-8')
    except Exception as e:
        print(f"Fallback to ASCII chart because matplotlib is missing: {e}")
        # Build text-based ASCII chart
        chart_ascii = "\n### Score Progression Chart (ASCII Fallback)\n```text\n"
        for item in iterations:
            bar_len = int(item["new_score"] * 25)
            bar = "█" * bar_len + "░" * (25 - bar_len)
            status = " [OK]" if item["accepted"] else " [REJECTED]"
            if item["iteration_number"] == 0:
                status = " [BASELINE]"
            chart_ascii += f"Iter #{item['iteration_number']:2d} ({item['new_score']:.4f}) | {bar} |{status}\n"
        chart_ascii += "```\n"

    # Assemble Markdown text
    md = f"""# 🎯 AutoTune Optimization Report

## 📋 Run Metadata
- **Generated On**: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **Total Optimization Loops**: {total_runs} iterations
- **Tuning Set Accuracy**: **{final_score * 100:.1f}%** (Starting: {starting_score * 100:.1f}%)
- **Holdout Set Accuracy**: **{holdout_score_val * 100:.1f}%**
- **Model Backend**: Dual Ollama + Gemini API (Auto-Detect Mode)

---

## 📈 Optimization Trajectory
"""
    if chart_base64:
        md += f"![Score Progression](data:image/png;base64,{chart_base64})\n\n"
    else:
        md += chart_ascii + "\n"

    md += """
## 🔄 Log of Accepted Tuning Changes
Below are the parameter modifications that were approved and committed by the optimizer:

| Iteration | Parameter | Modification | Score Trajectory | Targeted Failing Questions |
| :---: | :--- | :--- | :---: | :--- |
"""
    for item in iterations:
        if item["accepted"] and item["iteration_number"] > 0:
            failures = "N/A (Initial/Fallback)"
            if item.get("motivated_by"):
                # Clean motivated_by questions for display
                failures = item["motivated_by"].split(" | ")[0]
                if len(failures) > 85:
                    failures = failures[:82] + "..."
            md += f"| {item['iteration_number']} | `{item['param']}` | `{item['old_value']}` &rarr; `{item['new_value']}` | {item['old_score']:.3f} &rarr; {item['new_score']:.3f} | *\"{failures}\"* |\n"

    # Print hypotheses for all accepted configurations
    md += "\n### Accepted Hypotheses:\n"
    for item in iterations:
        if item["accepted"] and item["iteration_number"] > 0:
            md += f"- **Iteration #{item['iteration_number']} (`{item['param']}`):** *\"{item['hypothesis']}\"*\n"

    # Serialize final config
    final_config_str = json.dumps(config.CONFIG, indent=2)
    md += f"""
---

## ⚙️ Final Production Configuration (config.py)
This is the optimized configuration saved in production for the RAG-Finance application:

```json
{final_config_str}
```

---
*Report generated automatically by the AutoTune self-optimization loop.*
"""
    return md
