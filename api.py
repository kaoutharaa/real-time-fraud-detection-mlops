
"""
FraudShield — FastAPI Backend v2
Single WebSocket /ws/live pushes transactions, stats, and fraud alerts in real-time.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import asyncio, json, logging, os, time
from typing import Optional

import psycopg2, psycopg2.extras
import redis as redis_lib

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

POSTGRES_DSN = "dbname=frauddb user=frauduser password=fraudpass host=localhost port=5432"
REDIS_HOST, REDIS_PORT = "localhost", 6379

def get_pg():   return psycopg2.connect(POSTGRES_DSN)
def get_redis(): return redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# ── WebSocket manager ─────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self): self.active: list[WebSocket] = []
    async def connect(self, ws):
        await ws.accept(); self.active.append(ws)
    def disconnect(self, ws):
        if ws in self.active: self.active.remove(ws)
    async def broadcast(self, data):
        dead = []
        for ws in self.active:
            try: await ws.send_json(data)
            except: dead.append(ws)
        for ws in dead: self.disconnect(ws)

manager = ConnectionManager()

# ── Live broadcaster: DB every 1s, stats every 5s, Redis every 1s ─────────────
async def live_broadcaster():
    last_tx_id    = None
    seen_alerts   : set[str] = set()
    stats_ticker  = 0

    while True:
        try:
            conn = get_pg()
            cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Anchor on first run
            if last_tx_id is None:
                cur.execute("SELECT transaction_id FROM transactions ORDER BY transaction_time DESC LIMIT 1")
                row = cur.fetchone()
                if row: last_tx_id = row["transaction_id"]
            else:
                cur.execute("""
                    SELECT t.transaction_id, t.user_id, t.amount, t.currency,
                           t.merchant, t.transaction_time, t.country, t.transaction_type,
                           COALESCE(fa.fraud_score,0) AS fraud_score,
                           COALESCE(fa.is_fraud,FALSE) AS is_fraud,
                           COALESCE(fa.alert_status,'n/a') AS alert_status
                    FROM transactions t
                    LEFT JOIN fraud_alerts fa ON t.transaction_id = fa.transaction_id
                    WHERE t.transaction_time > (
                        SELECT transaction_time FROM transactions WHERE transaction_id = %s
                    )
                    ORDER BY t.transaction_time ASC LIMIT 20
                """, (last_tx_id,))
                for row in cur.fetchall():
                    tx = dict(row)
                    tx["transaction_time"] = str(tx["transaction_time"])
                    tx["amount"]           = float(tx["amount"])
                    tx["fraud_score"]      = float(tx["fraud_score"])
                    tx["is_fraud"]         = bool(tx["is_fraud"])
                    await manager.broadcast({"type": "transaction", "data": tx})
                    last_tx_id = tx["transaction_id"]

            # Stats every 5s
            stats_ticker += 1
            if stats_ticker >= 5:
                stats_ticker = 0
                cur.execute("SELECT COUNT(*) AS c FROM transactions WHERE transaction_time >= NOW() - INTERVAL '24 hours'")
                total = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM transactions WHERE transaction_time >= NOW() - INTERVAL '1 minute'")
                tpm = cur.fetchone()["c"]
                cur.execute("SELECT COALESCE(AVG(amount),0) AS c FROM transactions WHERE transaction_time >= NOW() - INTERVAL '24 hours'")
                avg_amt = float(cur.fetchone()["c"])
                cur.execute("SELECT COUNT(*) AS c FROM fraud_alerts WHERE detection_time >= NOW() - INTERVAL '24 hours' AND is_fraud=TRUE")
                frauds = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM fraud_alerts WHERE alert_status='pending'")
                pending = cur.fetchone()["c"]
                cur.execute("""
                    WITH r AS (SELECT COUNT(DISTINCT t.transaction_id)::float AS total,
                                      COUNT(DISTINCT fa.transaction_id)::float AS fraud
                               FROM transactions t
                               LEFT JOIN fraud_alerts fa ON t.transaction_id=fa.transaction_id AND fa.is_fraud=TRUE
                               WHERE t.transaction_time >= NOW() - INTERVAL '24 hours')
                    SELECT CASE WHEN total>0 THEN fraud/total ELSE 0 END AS rate FROM r
                """)
                fraud_rate = float(cur.fetchone()["rate"] or 0)
                cur.execute("SELECT COALESCE(AVG(fraud_score),0) AS c FROM fraud_alerts WHERE detection_time >= NOW() - INTERVAL '24 hours'")
                avg_score = float(cur.fetchone()["c"])
                await manager.broadcast({"type": "stats", "data": {
                    "transactions_per_minute": tpm, "transactions_today": total,
                    "avg_amount": round(avg_amt,2), "frauds_detected": frauds,
                    "pending_alerts": pending, "fraud_rate": round(fraud_rate,4),
                    "avg_fraud_score": round(avg_score,4),
                }})

            cur.close(); conn.close()

            # Redis fraud alerts
            try:
                r = get_redis()
                for key in r.keys("fraud_alert:*"):
                    if key not in seen_alerts:
                        raw = r.get(key)
                        if raw:
                            await manager.broadcast({"type": "fraud_alert", "data": json.loads(raw)})
                            seen_alerts.add(key)
                seen_alerts &= set(r.keys("fraud_alert:*"))
            except Exception as e:
                logger.error(f"Redis: {e}")

        except Exception as e:
            logger.error(f"Broadcaster: {e}")

        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(live_broadcaster())
    yield
    task.cancel()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="FraudShield API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# ── Serve dashboard ───────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fraud-dashboard.html")
    if not os.path.exists(html_path):
        return HTMLResponse("<h2>fraud-dashboard.html not found</h2>", status_code=404)
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace('const BASE_URL = "http://localhost:8000";', 'const BASE_URL = "";')
    content = content.replace('const WS_URL   = "ws://localhost:8000/ws/live";',
                               'const WS_URL   = `ws://${location.host}/ws/live`;')
    return HTMLResponse(content)

# ── REST endpoints ────────────────────────────────────────────────────────────
@app.get("/api/transactions/recent")
def get_recent_transactions(limit: int = 20):
    try:
        conn=get_pg(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT t.transaction_id,t.user_id,t.amount,t.currency,t.merchant,
                   t.transaction_time,t.country,t.transaction_type,
                   COALESCE(fa.fraud_score,0) AS fraud_score,
                   COALESCE(fa.is_fraud,FALSE) AS is_fraud,
                   COALESCE(fa.alert_status,'n/a') AS alert_status
            FROM transactions t
            LEFT JOIN fraud_alerts fa ON t.transaction_id=fa.transaction_id
            ORDER BY t.transaction_time DESC LIMIT %s
        """, (limit,))
        rows=cur.fetchall(); cur.close(); conn.close()
        return {"transactions": [dict(r) for r in rows]}
    except Exception as e: return {"transactions":[],"error":str(e)}

@app.get("/api/transactions/stats")
def get_transaction_stats():
    try:
        conn=get_pg(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COUNT(*) AS c FROM transactions WHERE transaction_time >= NOW() - INTERVAL '1 minute'")
        tpm=cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM transactions WHERE transaction_time >= NOW() - INTERVAL '24 hours'")
        today=cur.fetchone()["c"]
        cur.execute("SELECT COALESCE(AVG(amount),0) AS c FROM transactions WHERE transaction_time >= NOW() - INTERVAL '24 hours'")
        avg=float(cur.fetchone()["c"]); cur.close(); conn.close()
        return {"transactions_per_minute":tpm,"transactions_today":today,"avg_amount_1h":round(avg,2)}
    except Exception as e: return {"transactions_per_minute":0,"transactions_today":0,"avg_amount_1h":0,"error":str(e)}

@app.get("/api/transactions/volume-history")
def get_volume_history(minutes: int = 1440):
    try:
        conn=get_pg(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"""
            SELECT date_trunc('minute',t.transaction_time) AS minute,
                   COUNT(DISTINCT t.transaction_id) AS tx_count,
                   COUNT(DISTINCT fa.transaction_id) AS fraud_count
            FROM transactions t
            LEFT JOIN fraud_alerts fa ON t.transaction_id=fa.transaction_id AND fa.is_fraud=TRUE
            WHERE t.transaction_time >= NOW() - INTERVAL '{minutes} minutes'
            GROUP BY 1 ORDER BY 1 ASC
        """)
        rows=cur.fetchall(); cur.close(); conn.close()
        return {"history":[dict(r) for r in rows]}
    except Exception as e: return {"history":[],"error":str(e)}

@app.get("/api/fraud/alerts")
def get_fraud_alerts(limit: int=20, status: Optional[str]=None):
    try:
        conn=get_pg(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where="WHERE is_fraud=TRUE"; params=[]
        if status: where+=" AND alert_status=%s"; params.append(status)
        params.append(limit)
        cur.execute(f"""
            SELECT transaction_id,user_id,amount,merchant,fraud_score,is_fraud,
                   model_version,detection_time,transaction_time,alert_status
            FROM fraud_alerts {where} ORDER BY detection_time DESC LIMIT %s
        """, params)
        rows=cur.fetchall(); cur.close(); conn.close()
        return {"alerts":[dict(r) for r in rows],"count":len(rows)}
    except Exception as e: return {"alerts":[],"count":0,"error":str(e)}

@app.get("/api/fraud/stats")
def get_fraud_stats():
    try:
        conn=get_pg(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COUNT(*) AS c FROM fraud_alerts WHERE detection_time >= NOW() - INTERVAL '24 hours' AND is_fraud=TRUE")
        frauds=cur.fetchone()["c"]
        cur.execute("""
            WITH r AS (SELECT COUNT(DISTINCT t.transaction_id)::float AS total,
                              COUNT(DISTINCT fa.transaction_id)::float AS fraud
                       FROM transactions t LEFT JOIN fraud_alerts fa
                       ON t.transaction_id=fa.transaction_id AND fa.is_fraud=TRUE
                       WHERE t.transaction_time >= NOW() - INTERVAL '24 hours')
            SELECT CASE WHEN total>0 THEN fraud/total ELSE 0 END AS rate FROM r
        """)
        rate=float(cur.fetchone()["rate"] or 0)
        cur.execute("SELECT COALESCE(AVG(fraud_score),0) AS c FROM fraud_alerts WHERE detection_time >= NOW() - INTERVAL '24 hours'")
        avg=float(cur.fetchone()["c"])
        cur.execute("SELECT COUNT(*) AS c FROM fraud_alerts WHERE alert_status='pending'")
        pending=cur.fetchone()["c"]
        cur.execute("""
            SELECT t.country, COUNT(fa.id) AS fraud_count FROM fraud_alerts fa
            JOIN transactions t ON t.transaction_id=fa.transaction_id
            WHERE fa.is_fraud=TRUE AND fa.detection_time >= NOW() - INTERVAL '24 hours'
            GROUP BY t.country ORDER BY fraud_count DESC LIMIT 10
        """)
        by_country=[dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        return {"frauds_detected_1h":frauds,"fraud_rate":round(rate,4),
                "avg_fraud_score":round(avg,4),"pending_alerts":pending,"by_country":by_country}
    except Exception as e:
        return {"frauds_detected_1h":0,"fraud_rate":0,"avg_fraud_score":0,"pending_alerts":0,"by_country":[],"error":str(e)}

@app.get("/api/model/performance")
def get_model_performance():
    try:
        conn=get_pg(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT model_version,accuracy,precision_score,recall,f1_score,training_date,dataset_size,is_active,created_at FROM model_performance WHERE is_active=TRUE ORDER BY created_at DESC LIMIT 1")
        row=cur.fetchone(); cur.close(); conn.close()
        return {"model":dict(row) if row else None}
    except Exception as e: return {"model":None,"error":str(e)}

@app.get("/api/health")
def get_system_health():
    status={"postgres":{"healthy":False},"redis":{"healthy":False,"cache_keys":0}}
    try:
        t0=time.monotonic(); conn=get_pg(); cur=conn.cursor(); cur.execute("SELECT 1")
        status["postgres"]={"healthy":True,"latency_ms":round((time.monotonic()-t0)*1000,1)}
        cur.close(); conn.close()
    except Exception as e: status["postgres"]["error"]=str(e)
    try:
        t0=time.monotonic(); r=get_redis(); r.ping()
        status["redis"]={"healthy":True,"latency_ms":round((time.monotonic()-t0)*1000,1),"cache_keys":r.dbsize()}
    except Exception as e: status["redis"]["error"]=str(e)
    return status

# ── SINGLE WebSocket — all live events ───────────────────────────────────────
@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()          # Accept FIRST, before anything else
    manager.active.append(websocket)
    logger.info(f"WS connected. Total: {len(manager.active)}")

    # Send last 20 transactions immediately on connect
    try:
        conn=get_pg(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT t.transaction_id,t.user_id,t.amount,t.currency,t.merchant,
                   t.transaction_time,t.country,t.transaction_type,
                   COALESCE(fa.fraud_score,0) AS fraud_score,
                   COALESCE(fa.is_fraud,FALSE) AS is_fraud,
                   COALESCE(fa.alert_status,'n/a') AS alert_status
            FROM transactions t
            LEFT JOIN fraud_alerts fa ON t.transaction_id=fa.transaction_id
            ORDER BY t.transaction_time DESC LIMIT 20
        """)
        rows=cur.fetchall(); cur.close(); conn.close()
        for row in reversed(rows):
            row=dict(row)
            row["transaction_time"]=str(row["transaction_time"])
            row["amount"]=float(row["amount"])
            row["fraud_score"]=float(row["fraud_score"])
            row["is_fraud"]=bool(row["is_fraud"])
            await websocket.send_json({"type":"transaction","data":row})
    except Exception as e:
        logger.error(f"Initial load error: {e}")

    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type":"ping"})
    except (WebSocketDisconnect, Exception):
        manager.disconnect(websocket)
        logger.info(f"WS disconnected. Total: {len(manager.active)}")
