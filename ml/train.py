"""Train the optional Isolation Forest against the synthetic feature set."""
from pathlib import Path
import joblib,pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
root=Path(__file__).resolve().parent.parent; df=pd.read_csv(root/'data'/'transactions.csv'); features=['amount_ratio','velocity_10m','velocity_24h','minutes_since_previous','new_device','new_location','account_age_days']; model=Pipeline([('scaler',StandardScaler()),('iforest',IsolationForest(n_estimators=200,contamination=.05,random_state=42))]);model.fit(df[features]);joblib.dump(model,root/'ml'/'model.joblib');print('Saved ml/model.joblib')
