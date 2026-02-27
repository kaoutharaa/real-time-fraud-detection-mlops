"""
FraudShield — FastAPI Backend
Exposes real-time data from PostgreSQL, Redis, and Kafka for the dashboard frontend.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import asyncio
import json
import logging
import os
from typing import Optional

import psycopg2
import psycopg2.extras
import redis as redis_lib

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
POSTGRES_DSN = "dbname=frauddb user=frauduser password=fraudpass host=localhost port=5432"
REDIS_HOST   = "localhost"
REDIS_PORT   = 6379

# ── DB helpers ────────────────────────────────────────────────────────────────
def get_pg():
    return psycopg2.connect(POSTGRES_DSN)

def get_redis():
    return redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# ── WebSocket manager ─────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()

# ── Background task: push live fraud alerts via WebSocket ─────────────────────
async def fraud_alert_broadcaster():
    r = get_redis()
    seen: set[str] = set()
    while True:
        try:
            keys = r.keys("fraud_alert:*")
            new_keys = [k for k in keys if k not in seen]
            for key in new_keys:
                raw = r.get(key)
                if raw:
                    alert = json.loads(raw)
                    await manager.broadcast({"type": "fraud_alert", "data": alert})
                    seen.add(key)
            seen &= set(keys)
        except Exception as e:
            logger.error(f"Broadcaster error: {e}")
        await asyncio.sleep(2)

# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(fraud_alert_broadcaster())
    yield
    task.cancel()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="FraudShield API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══════════════════════════════════════════════════════════════════════════════
# ROOT — serve the dashboard HTML directly (no CORS issues)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    """Serve fraud-dashboard.html so browser has no CORS issues."""
    # Look for the HTML file next to api.py
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fraud-dashboard.html")
    if not os.path.exists(html_path):
        return HTMLResponse("<h2>fraud-dashboard.html not found next to api.py</h2>", status_code=404)
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Patch BASE_URL so the frontend talks to the same origin
    content = content.replace(
        'const BASE_URL = "http://localhost:8000";',
        'const BASE_URL = "";'
    ).replace(
        'const WS_URL   = "ws://localhost:8000/ws/fraud-alerts";',
        'const WS_URL   = `ws://${location.host}/ws/fraud-alerts`;'
    )
    return HTMLResponse(content)


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTIONS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/transactions/recent")
def get_recent_transactions(limit: int = 20):
    try:
        conn = get_pg()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                t.transaction_id,
                t.user_id,
                t.amount,
                t.currency,
                t.merchant,
                t.transaction_time,
                t.country,
                t.transaction_type,
                COALESCE(fa.fraud_score, 0)      AS fraud_score,
                COALESCE(fa.is_fraud, FALSE)     AS is_fraud,
                COALESCE(fa.alert_status, 'n/a') AS alert_status
            FROM transactions t
            LEFT JOIN fraud_alerts fa ON t.transaction_id = fa.transaction_id
            ORDER BY t.created_at DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"transactions": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"/transactions/recent error: {e}")
        return {"transactions": [], "error": str(e)}


@app.get("/api/transactions/stats")
def get_transaction_stats():
    try:
        conn = get_pg()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT COUNT(*) AS c FROM transactions WHERE created_at >= NOW() - INTERVAL '1 minute'")
        tpm = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM transactions WHERE DATE(created_at) = CURRENT_DATE")
        today = cur.fetchone()["c"]

        cur.execute("SELECT COALESCE(AVG(amount),0) AS c FROM transactions WHERE created_at >= NOW() - INTERVAL '1 hour'")
        avg = cur.fetchone()["c"]

        cur.close(); conn.close()
        return {
            "transactions_per_minute": tpm,
            "transactions_today": today,
            "avg_amount_1h": round(float(avg), 2)
        }
    except Exception as e:
        logger.error(f"/transactions/stats error: {e}")
        return {"transactions_per_minute": 0, "transactions_today": 0, "avg_amount_1h": 0, "error": str(e)}


@app.get("/api/transactions/volume-history")
def get_volume_history(minutes: int = 60):
    try:
        conn = get_pg()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"""
            SELECT
                date_trunc('minute', t.created_at)   AS minute,
                COUNT(DISTINCT t.transaction_id)      AS tx_count,
                COUNT(DISTINCT fa.transaction_id)     AS fraud_count
            FROM transactions t
            LEFT JOIN fraud_alerts fa
                ON t.transaction_id = fa.transaction_id AND fa.is_fraud = TRUE
            WHERE t.created_at >= NOW() - INTERVAL '{minutes} minutes'
            GROUP BY 1
            ORDER BY 1 ASC
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"history": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"/transactions/volume-history error: {e}")
        return {"history": [], "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# FRAUD ALERTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/fraud/alerts")
def get_fraud_alerts(limit: int = 20, status: Optional[str] = None):
    try:
        conn = get_pg()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where  = "WHERE is_fraud = TRUE"
        params = []
        if status:
            where += " AND alert_status = %s"
            params.append(status)
        params.append(limit)
        cur.execute(f"""
            SELECT transaction_id, user_id, amount, merchant,
                   fraud_score, is_fraud, model_version,
                   detection_time, transaction_time, alert_status
            FROM fraud_alerts
            {where}
            ORDER BY detection_time DESC
            LIMIT %s
        """, params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"alerts": [dict(r) for r in rows], "count": len(rows)}
    except Exception as e:
        logger.error(f"/fraud/alerts error: {e}")
        return {"alerts": [], "count": 0, "error": str(e)}


@app.get("/api/fraud/stats")
def get_fraud_stats():
    try:
        conn = get_pg()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT COUNT(*) AS c FROM fraud_alerts WHERE detection_time >= NOW() - INTERVAL '1 hour' AND is_fraud = TRUE")
        frauds_1h = cur.fetchone()["c"]

        cur.execute("""
            WITH r AS (
                SELECT COUNT(DISTINCT t.transaction_id)::float  AS total,
                       COUNT(DISTINCT fa.transaction_id)::float AS fraud
                FROM transactions t
                LEFT JOIN fraud_alerts fa ON t.transaction_id = fa.transaction_id AND fa.is_fraud = TRUE
                WHERE t.created_at >= NOW() - INTERVAL '1 hour'
            )
            SELECT CASE WHEN total > 0 THEN fraud/total ELSE 0 END AS rate FROM r
        """)
        fraud_rate = cur.fetchone()["rate"] or 0

        cur.execute("SELECT COALESCE(AVG(fraud_score),0) AS c FROM fraud_alerts WHERE detection_time >= NOW() - INTERVAL '1 hour'")
        avg_score = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM fraud_alerts WHERE alert_status = 'pending'")
        pending = cur.fetchone()["c"]

        cur.execute("""
            SELECT t.country, COUNT(fa.id) AS fraud_count
            FROM fraud_alerts fa
            JOIN transactions t ON t.transaction_id = fa.transaction_id
            WHERE fa.is_fraud = TRUE AND fa.detection_time >= NOW() - INTERVAL '24 hours'
            GROUP BY t.country ORDER BY fraud_count DESC LIMIT 10
        """)
        by_country = [dict(r) for r in cur.fetchall()]

        cur.close(); conn.close()
        return {
            "frauds_detected_1h": frauds_1h,
            "fraud_rate": round(float(fraud_rate), 4),
            "avg_fraud_score": round(float(avg_score), 4),
            "pending_alerts": pending,
            "by_country": by_country
        }
    except Exception as e:
        logger.error(f"/fraud/stats error: {e}")
        return {"frauds_detected_1h": 0, "fraud_rate": 0, "avg_fraud_score": 0,
                "pending_alerts": 0, "by_country": [], "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# ML MODEL METRICS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/model/performance")
def get_model_performance():
    try:
        conn = get_pg()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT model_version, accuracy, precision_score, recall, f1_score,
                   training_date, dataset_size, feature_importance, hyperparameters,
                   is_active, created_at
            FROM model_performance WHERE is_active = TRUE
            ORDER BY created_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"model": dict(row) if row else None}
    except Exception as e:
        logger.error(f"/model/performance error: {e}")
        return {"model": None, "error": str(e)}


@app.get("/api/model/history")
def get_model_history():
    try:
        conn = get_pg()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT model_version, accuracy, precision_score, recall,
                   f1_score, training_date, is_active
            FROM model_performance ORDER BY created_at DESC LIMIT 10
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"versions": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"/model/history error: {e}")
        return {"versions": [], "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM HEALTH
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def get_system_health():
    import time
    status = {
        "postgres": {"healthy": False, "latency_ms": None},
        "redis":    {"healthy": False, "latency_ms": None, "cache_keys": 0},
    }
    try:
        t0 = time.monotonic()
        conn = get_pg(); cur = conn.cursor(); cur.execute("SELECT 1")
        status["postgres"]["healthy"]    = True
        status["postgres"]["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
        cur.close(); conn.close()
    except Exception as e:
        status["postgres"]["error"] = str(e)

    try:
        t0 = time.monotonic()
        r = get_redis(); r.ping()
        status["redis"]["healthy"]    = True
        status["redis"]["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
        status["redis"]["cache_keys"] = r.dbsize()
    except Exception as e:
        status["redis"]["error"] = str(e)

    try:
        r   = get_redis()
        raw = r.get("latest_metrics")
        if raw:
            status["cached_metrics"] = json.loads(raw)
    except Exception:
        pass

    return status


@app.get("/api/health/alerts-log")
def get_recent_system_alerts(limit: int = 10):
    try:
        conn = get_pg()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT event_type, event_description, metadata, created_at
            FROM audit_log WHERE event_type LIKE 'ALERT_%%'
            ORDER BY created_at DESC LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"logs": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"/health/alerts-log error: {e}")
        return {"logs": [], "error": str(e)}


@app.get("/api/metrics/latest")
def get_latest_metrics():
    try:
        r   = get_redis()
        raw = r.get("latest_metrics")
        if raw:
            return {"metrics": json.loads(raw), "source": "redis_cache"}
        conn = get_pg()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT DISTINCT ON (metric_name) metric_name, metric_value, metric_unit, timestamp
            FROM monitoring_metrics ORDER BY metric_name, timestamp DESC
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"metrics": {r["metric_name"]: r["metric_value"] for r in rows}, "source": "postgres"}
    except Exception as e:
        logger.error(f"/metrics/latest error: {e}")
        return {"metrics": {}, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET
# ══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/fraud-alerts")
async def ws_fraud_alerts(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)