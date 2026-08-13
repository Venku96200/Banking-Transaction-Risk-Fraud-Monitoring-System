from datetime import datetime, timedelta
from app.services.risk_engine import combined, risk_level, rule_risk

class Tx:
    def __init__(self, amount=100, device_id='D1', location='Mumbai', hour=12):
        self.amount=amount; self.device_id=device_id; self.location=location; self.timestamp=datetime(2026,1,1,hour)

def profile(): return {'avg':100,'known_devices':{'D1'},'known_locations':{'Mumbai'},'normal_hours':{12},'velocity_10m':1,'velocity_24h':2,'prior_count':10}
def test_amount_rule_and_reason():
    score,reasons=rule_risk(Tx(amount=501),profile()); assert score==25; assert 'customer average' in reasons[0]
def test_score_is_bounded(): assert 0 <= combined(120,110) <= 100
def test_risk_boundaries(): assert [risk_level(x) for x in (30,31,60,61,80,81)] == ['LOW','MEDIUM','MEDIUM','HIGH','HIGH','CRITICAL']
