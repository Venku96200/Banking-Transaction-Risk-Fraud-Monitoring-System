import csv, io, json
from collections import Counter
from datetime import datetime
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import Alert, Customer, Review, Transaction
from .schemas import ReviewCreate, TransactionCreate
from .services.risk_engine import build_profile, combined, ml_score, model_available, reasons_json, risk_level, rule_risk

app = FastAPI(title='Banking Risk Monitoring', version='1.0.0')
ROOT = Path(__file__).resolve().parent.parent
app.mount('/static', StaticFiles(directory=ROOT / 'frontend'), name='static')

@app.on_event('startup')
def startup(): Base.metadata.create_all(bind=engine)

@app.get('/', include_in_schema=False)
def dashboard(): return FileResponse(ROOT / 'frontend' / 'index.html')

@app.get('/health')
def health(db: Session = Depends(get_db)):
    db.execute(select(func.count(Customer.customer_id)))
    return {'status': 'ok', 'database': 'connected', 'model_loaded': model_available(), 'model_note': 'heuristic fallback until ml/train.py is run' if not model_available() else 'Isolation Forest loaded'}

def assess(payload: TransactionCreate, db: Session):
    if db.get(Transaction, payload.transaction_id): raise HTTPException(409, 'transaction_id already exists')
    customer = db.get(Customer, payload.customer_id)
    if not customer:
        customer = Customer(customer_id=payload.customer_id, account_age_days=payload.account_age_days)
        db.add(customer); db.flush()
    tx = Transaction(**payload.model_dump(exclude={'account_age_days'})); p = build_profile(db, tx)
    rule, reasons = rule_risk(tx, p); anomaly = ml_score(tx, p, customer.account_age_days if customer else payload.account_age_days); score = combined(rule, anomaly); level = risk_level(score)
    tx.rule_score, tx.ml_score, tx.risk_score, tx.risk_level, tx.reasons = rule, anomaly, score, level, reasons_json(reasons)
    db.add(tx); db.flush(); alert = None
    if level in ('HIGH','CRITICAL'):
        alert = Alert(transaction_id=tx.transaction_id, risk_score=score, risk_level=level, reasons=tx.reasons); db.add(alert); db.flush()
    db.commit()
    return {'transaction_id': tx.transaction_id, 'risk_score': score, 'risk_level': level, 'rule_score': rule, 'ml_score': anomaly, 'reasons': reasons, 'alert_id': alert.alert_id if alert else None}

@app.post('/transactions', status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)): return assess(payload, db)

@app.post('/transactions/bulk')
async def bulk_transactions(file: UploadFile, db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith('.csv'): raise HTTPException(400, 'Upload a CSV file')
    rows = csv.DictReader(io.StringIO((await file.read()).decode('utf-8-sig'))); results, errors = [], []
    for row_no, row in enumerate(rows, 2):
        try: results.append(assess(TransactionCreate(**row), db))
        except Exception as exc: db.rollback(); errors.append({'row':row_no, 'error':str(exc)})
    return {'processed':len(results), 'rejected':len(errors), 'results':results, 'errors':errors[:20]}

@app.get('/transactions/{transaction_id}')
def transaction_detail(transaction_id: str, db: Session = Depends(get_db)):
    t = db.get(Transaction, transaction_id)
    if not t: raise HTTPException(404, 'Transaction not found')
    return {'transaction_id':t.transaction_id,'customer_id':t.customer_id,'timestamp':t.timestamp,'amount':t.amount,'location':t.location,'device_id':t.device_id,'risk_score':t.risk_score,'risk_level':t.risk_level,'rule_score':t.rule_score,'ml_score':t.ml_score,'reasons':json.loads(t.reasons)}

@app.get('/alerts')
def alerts(level: str|None=None, status: str|None=None, db: Session=Depends(get_db)):
    stmt = select(Alert,Transaction).join(Transaction,Alert.transaction_id==Transaction.transaction_id).order_by(Alert.created_at.desc())
    if level: stmt = stmt.where(Alert.risk_level==level.upper())
    if status: stmt = stmt.where(Alert.status==status.upper())
    return [{'alert_id':a.alert_id,'transaction_id':a.transaction_id,'customer_id':t.customer_id,'amount':t.amount,'risk_score':a.risk_score,'risk_level':a.risk_level,'status':a.status,'created_at':a.created_at,'reasons':json.loads(a.reasons)} for a,t in db.execute(stmt.limit(200)).all()]

@app.patch('/alerts/{alert_id}/review')
def review_alert(alert_id: int, payload: ReviewCreate, db: Session=Depends(get_db)):
    alert=db.get(Alert,alert_id)
    if not alert: raise HTTPException(404,'Alert not found')
    alert.status,alert.notes,alert.reviewed_at=payload.outcome,payload.notes,datetime.utcnow(); db.add(Review(alert_id=alert_id,outcome=payload.outcome,notes=payload.notes)); db.commit()
    return {'alert_id':alert_id,'status':alert.status}

@app.patch('/alerts/{alert_id}/escalate')
def escalate_alert(alert_id: int, db: Session=Depends(get_db)): return review_alert(alert_id, ReviewCreate(outcome='ESCALATED',notes='Escalated by analyst'), db)

@app.get('/dashboard/summary')
def summary(db: Session=Depends(get_db)):
    txs=db.scalars(select(Transaction)).all(); alerts=db.scalars(select(Alert)).all(); levels=Counter(t.risk_level for t in txs)
    return {'total_transactions':len(txs),'open_alerts':sum(a.status=='OPEN' for a in alerts),'high_risk_alerts':sum(a.risk_level=='HIGH' for a in alerts),'critical_alerts':sum(a.risk_level=='CRITICAL' for a in alerts),'risk_distribution':{x:levels.get(x,0) for x in ['LOW','MEDIUM','HIGH','CRITICAL']}}

@app.get('/dashboard/trends')
def trends(db: Session=Depends(get_db)):
    rows=db.execute(select(func.date(Transaction.timestamp),func.count(Transaction.transaction_id)).where(Transaction.risk_level.in_(['HIGH','CRITICAL'])).group_by(func.date(Transaction.timestamp)).order_by(func.date(Transaction.timestamp))).all()
    return [{'date':str(day),'alerts':count} for day,count in rows]
