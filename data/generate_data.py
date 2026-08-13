"""Create reproducible synthetic data only; never use customer data."""
from pathlib import Path
import numpy as np, pandas as pd
rng=np.random.default_rng(42); n=50_000; customers=rng.integers(1,1001,n); base=pd.Timestamp('2026-01-01')
df=pd.DataFrame({'transaction_id':[f'TX{i:06d}' for i in range(n)],'customer_id':[f'C{x:04d}' for x in customers],'timestamp':base+pd.to_timedelta(rng.integers(0,180*86400,n),unit='s'),'amount':rng.lognormal(7,.75,n).round(2),'merchant_category':rng.choice(['Grocery','Travel','Fuel','Shopping','Bills'],n),'location':rng.choice(['Mumbai','Delhi','Bengaluru','Pune'],n),'device_id':[f'D{x}' for x in rng.integers(1,2500,n)],'transaction_type':rng.choice(['Card','Transfer','UPI'],n),'account_age_days':rng.integers(30,2500,n)})
df.sort_values(['customer_id','timestamp'],inplace=True); avg=df.groupby('customer_id').amount.transform('mean'); anomaly=rng.random(n)<.07; df.loc[anomaly,'amount']*=rng.integers(5,14,anomaly.sum());df['amount_ratio']=df.amount/avg;df['velocity_10m']=rng.poisson(1.2,n)+anomaly*rng.integers(3,8,n);df['velocity_24h']=rng.poisson(4,n);df['minutes_since_previous']=rng.exponential(500,n);df['new_device']=anomaly.astype(int);df['new_location']=anomaly.astype(int);df['is_synthetic_anomaly']=anomaly.astype(int)
df.to_csv(Path(__file__).parent/'transactions.csv',index=False);print(f'Wrote {n:,} rows')
