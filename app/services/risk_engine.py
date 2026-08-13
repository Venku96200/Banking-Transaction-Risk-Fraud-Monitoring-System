import json
from datetime import timedelta
import numpy as np
import joblib
from pathlib import Path
from sqlalchemy import select
from ..models import Transaction

def build_profile(db, tx):
    prior = db.scalars(select(Transaction).where(Transaction.customer_id == tx.customer_id, Transaction.timestamp < tx.timestamp).order_by(Transaction.timestamp.desc())).all()
    amounts = [item.amount for item in prior]
    avg = float(np.mean(amounts)) if amounts else tx.amount
    previous_minutes = (tx.timestamp-prior[0].timestamp).total_seconds()/60 if prior else 1440
    return {"avg": max(avg, 1), "known_devices": {x.device_id for x in prior}, "known_locations": {x.location for x in prior}, "normal_hours": {x.timestamp.hour for x in prior}, "velocity_10m": sum(x.timestamp >= tx.timestamp - timedelta(minutes=10) for x in prior) + 1, "velocity_24h": sum(x.timestamp >= tx.timestamp - timedelta(hours=24) for x in prior) + 1, "minutes_since_previous": max(previous_minutes,0), "prior_count": len(prior)}

def rule_risk(tx, p):
    score, reasons, signals = 0, [], 0
    if p['prior_count'] >= 3 and tx.amount > 5*p['avg']:
        score += 25; signals += 1; reasons.append(f"Amount is {tx.amount / p['avg']:.1f}x customer average")
    if p['prior_count'] >= 3 and tx.device_id not in p['known_devices']:
        score += 20; signals += 1; reasons.append('New device detected')
    if p['prior_count'] >= 3 and tx.location not in p['known_locations']:
        score += 20; signals += 1; reasons.append('New location detected')
    if p['prior_count'] >= 8 and tx.timestamp.hour not in p['normal_hours']:
        score += 10; signals += 1; reasons.append('Unusual transaction hour')
    if p['velocity_10m'] >= 5:
        score += 15; signals += 1; reasons.append('High transaction velocity (5+ in 10 minutes)')
    if signals >= 3: score += 10; reasons.append('High-risk combination of control signals')
    return min(score, 100), reasons

MODEL_PATH = Path(__file__).resolve().parents[2] / 'ml' / 'model.joblib'
_model = None
def model_available(): return MODEL_PATH.exists()
def _load_model():
    global _model
    if _model is None and model_available(): _model = joblib.load(MODEL_PATH)
    return _model

def ml_score(tx, p, account_age_days=365):
    model = _load_model()
    if model:
        values = [[tx.amount/p['avg'],p['velocity_10m'],p['velocity_24h'],p['minutes_since_previous'],int(tx.device_id not in p['known_devices']),int(tx.location not in p['known_locations']),account_age_days]]
        # decision_function: higher is more normal; map the observed synthetic range to 0-100 risk.
        return round(float(np.clip((-.25 - model.decision_function(values)[0])*200 + 50, 0, 100)), 2)
    amount = min(60, 12*np.log1p(tx.amount / p['avg']))
    velocity = min(25, max(0, p['velocity_10m']-1)*6)
    novelty = 15 if p['prior_count'] >= 3 and (tx.device_id not in p['known_devices'] or tx.location not in p['known_locations']) else 0
    return round(min(100, amount + velocity + novelty), 2)

def combined(rule, anomaly): return round(min(100, max(0, .60*rule + .40*anomaly)), 2)
def risk_level(score): return 'LOW' if score <= 30 else 'MEDIUM' if score <= 60 else 'HIGH' if score <= 80 else 'CRITICAL'
def reasons_json(reasons): return json.dumps(reasons)
