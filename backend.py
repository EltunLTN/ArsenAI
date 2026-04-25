from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
import asyncio, json, time
from simulation import Intersection

app = FastAPI()

# 4 kəsişmə qur
intersections = [
    Intersection("Neftçilər-28 May"),
    Intersection("Nizami-İstiqlaliyyət"),
    Intersection("H.Əliyev-Tbilisi"),
    Intersection("Rəşid Behbudov")
]

# Statistika üçün
stats = {"ai_total_wait": 0, "fixed_total_wait": 0, 
         "emergency_events": 0}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    sim_hour = 8.0  # simulyasiya saat 08:00-dan başlayır
    
    while True:
        sim_hour = (sim_hour + 0.01) % 24
        
        data = []
        for ix in intersections:
            ix.update_queues(int(sim_hour))
            state = ix.step()
            state["sim_hour"] = f"{int(sim_hour):02d}:{int((sim_hour%1)*60):02d}"
            data.append(state)
        
        # Müqayisə üçün stats
        ai_wait = sum(s["total_waiting"] for s in data if True)
        stats["ai_total_wait"] += ai_wait
        
        await ws.send_json({
            "intersections": data,
            "stats": stats,
            "sim_hour": f"{int(sim_hour):02d}:{int((sim_hour%1)*60):02d}"
        })
        await asyncio.sleep(1)

@app.get("/emergency/{intersection_id}")
async def trigger_emergency(intersection_id: int):
    """Ambulans simulyasiyası"""
    if 0 <= intersection_id < len(intersections):
        # bütün istiqamətlər qırmızı, şimal yaşıl
        ix = intersections[intersection_id]
        ix.queues = {d: ix.queues[d] for d in ix.queues}
        stats["emergency_events"] += 1
        return {"status": "emergency_activated", 
                "intersection": ix.name}

@app.post("/toggle/{intersection_id}/{mode}")
async def toggle_mode(intersection_id: int, mode: str):
    """AI vs Sabit rejimi dəyiş — live demo üçün"""
    intersections[intersection_id].mode = mode
    return {"status": "ok"}

app.mount("/", StaticFiles(directory=".", html=True), name="static")