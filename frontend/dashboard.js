let distChart, trendChart;
const money = new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0});
async function api(path){const r=await fetch(path);if(!r.ok)throw new Error(await r.text());return r.json()}
async function loadDashboard(){
 const [s,t]=await Promise.all([api('/dashboard/summary'),api('/dashboard/trends')]);
 document.querySelector('#total').textContent=s.total_transactions;document.querySelector('#open').textContent=s.open_alerts;document.querySelector('#high').textContent=s.high_risk_alerts;document.querySelector('#critical').textContent=s.critical_alerts;
 if(distChart)distChart.destroy();distChart=new Chart(document.querySelector('#distribution'),{type:'doughnut',data:{labels:Object.keys(s.risk_distribution),datasets:[{data:Object.values(s.risk_distribution),backgroundColor:['#22c55e','#38bdf8','#f59e0b','#fb7185']}]},options:{plugins:{legend:{labels:{color:'#eaf2f8'}}}}});
 if(trendChart)trendChart.destroy();trendChart=new Chart(document.querySelector('#trends'),{type:'line',data:{labels:t.map(x=>x.date),datasets:[{data:t.map(x=>x.alerts),borderColor:'#38bdf8',tension:.25}]},options:{scales:{x:{ticks:{color:'#91a4b5'}},y:{ticks:{color:'#91a4b5'},beginAtZero:true}},plugins:{legend:{display:false}}}});loadAlerts();
}
async function loadAlerts(){const status=document.querySelector('#status').value;const data=await api('/alerts'+(status?'?status='+status:''));document.querySelector('#alerts').innerHTML=data.length?data.map(a=>`<tr><td>#${a.alert_id}<br>${a.transaction_id}</td><td>${a.customer_id}</td><td>${money.format(a.amount)}</td><td><span class="tag ${a.risk_level}">${a.risk_level} ${a.risk_score}</span></td><td>${a.status}</td><td>${a.reasons.join('<br>')}</td><td>${a.status==='OPEN'?`<button onclick="review(${a.alert_id},'REVIEWED')">Review</button> <button onclick="review(${a.alert_id},'ESCALATED')">Escalate</button>`:'-'}</td></tr>`).join(''):'<tr><td colspan="7">No matching alerts.</td></tr>'}
async function review(id,outcome){await fetch(`/alerts/${id}/review`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({outcome,notes:`Marked ${outcome.toLowerCase()} in dashboard`})});loadDashboard()}
loadDashboard();
