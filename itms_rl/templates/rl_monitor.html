<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RL Monitor ÔÇö AI-based Urban Traffic Management System</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Plus Jakarta Sans',sans-serif;min-height:100vh;background:#060b17;color:#e2e8f0}
nav{display:flex;justify-content:space-between;align-items:center;padding:12px 28px;background:#0d1321;border-bottom:1px solid #1a2744;position:sticky;top:0;z-index:100}
.brand{font-family:'Bebas Neue';font-size:1.35rem;color:#818cf8;letter-spacing:2px}
.nav-links a{color:#4b5563;text-decoration:none;margin-left:18px;font-weight:600;font-size:.8rem;transition:.2s}
.nav-links a:hover,.nav-links a.active{color:#e2e8f0}
main{max-width:1200px;margin:0 auto;padding:28px 24px 60px}
.pg-title{font-family:'Bebas Neue';font-size:2rem;letter-spacing:2px;margin-bottom:4px}
.pg-sub{color:#4b5563;font-size:.85rem;margin-bottom:26px}
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:24px}
.kpi{background:#0d1321;border:1px solid #1a2744;border-radius:12px;padding:18px 16px;text-align:center}
.kpi .v{font-family:'Bebas Neue';font-size:1.8rem;letter-spacing:1px;line-height:1.1}
.kpi .l{font-size:.7rem;color:#4b5563;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
.kpi.blue .v{color:#38bdf8}.kpi.green .v{color:#4ade80}.kpi.yellow .v{color:#fbbf24}
.kpi.red .v{color:#f87171}.kpi.purple .v{color:#a78bfa}.kpi.white .v{color:#e2e8f0}
/* Q-value bar chart (inline) */
.qbar-row{display:flex;gap:8px;margin-bottom:24px;background:#0d1321;border:1px solid #1a2744;border-radius:12px;padding:18px 20px;align-items:flex-end}
.qbar-wrap{flex:1;text-align:center}
.qbar-label{font-size:.72rem;color:#6b7280;margin-bottom:6px}
.qbar-outer{height:80px;display:flex;align-items:flex-end;justify-content:center;background:rgba(255,255,255,.03);border-radius:6px;padding:4px}
.qbar-inner{width:36px;border-radius:4px 4px 0 0;transition:height .4s, background .4s;min-height:4px}
.qbar-val{font-size:.7rem;font-weight:700;margin-top:5px;color:#94a3b8}
.qbar-title{font-size:.82rem;font-weight:700;color:#6b7280;margin-bottom:10px}
/* Chart grid */
.cgrid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:24px}
.cc{background:#0d1321;border:1px solid #1a2744;border-radius:12px;padding:20px}
.cc h3{font-size:.85rem;font-weight:700;color:#6b7280;margin-bottom:14px;letter-spacing:.3px;display:flex;justify-content:space-between;align-items:center}
.cc h3 span{font-size:.72rem;font-weight:400;color:#4b5563}
.cw{height:185px;position:relative}
.cc.full{grid-column:1/-1}.cc.full .cw{height:200px}
/* Info table */
.itbl{background:#0d1321;border:1px solid #1a2744;border-radius:12px;padding:20px;margin-bottom:18px}
.itbl h3{font-size:.85rem;font-weight:700;color:#6b7280;margin-bottom:14px}
table{width:100%;border-collapse:collapse}
th{color:#4b5563;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px;padding:9px 12px;text-align:left;border-bottom:1px solid #1a2744}
td{padding:10px 12px;border-bottom:1px solid rgba(26,39,68,.5);font-size:.84rem;color:#cbd5e1}
tr:last-child td{border:none}
.pill{padding:1px 7px;border-radius:7px;font-size:.7rem;font-weight:700}
.pg{background:rgba(74,222,128,.1);color:#4ade80}.pr{background:rgba(248,113,113,.1);color:#f87171}
@media(max-width:760px){.cgrid{grid-template-columns:1fr}}
</style>
</head>
<body>
<nav>
  <span class="brand">­ƒÜª AI-UTMS</span>
  <div class="nav-links">
    <a href="/home">Home</a><a href="/upload">Upload</a>
    <a href="/dashboard">Dashboard</a>
    <a href="/rl_monitor" class="active">RL Monitor</a>
    <a href="/analysis">Analysis</a><a href="/logout">Logout</a>
  </div>
</nav>
<main>
  <div class="pg-title">­ƒºá RL Agent Monitor</div>
  <p class="pg-sub">Live DQN training metrics ÔÇö all values from real agent, no hardcoding.</p>

  <!-- KPIs ÔÇö all from /rl_api -->
  <div class="kpi-row">
    <div class="kpi blue"><div class="v" id="kEps">ÔÇö</div><div class="l">Epsilon ╬Á</div></div>
    <div class="kpi green"><div class="v" id="kRew">ÔÇö</div><div class="l">Total Reward</div></div>
    <div class="kpi yellow"><div class="v" id="kSteps">ÔÇö</div><div class="l">Train Steps</div></div>
    <div class="kpi red"><div class="v" id="kLoss">ÔÇö</div><div class="l">Latest Loss</div></div>
    <div class="kpi purple"><div class="v" id="kMem">ÔÇö</div><div class="l">Memory</div></div>
    <div class="kpi white"><div class="v" id="kMode">ÔÇö</div><div class="l">Agent Mode</div></div>
    <div class="kpi green"><div class="v" id="kAvgR">ÔÇö</div><div class="l">Avg Reward</div></div>
    <div class="kpi yellow"><div class="v" id="kAvgW">ÔÇö</div><div class="l">Avg Wait</div></div>
  </div>

  <!-- Live Q-values for each lane -->
  <div class="qbar-row">
    <div style="display:flex;flex-direction:column;justify-content:center;padding-right:18px;border-right:1px solid #1a2744;margin-right:8px">
      <div class="qbar-title">Live Q-Values</div>
      <div style="font-size:.72rem;color:#4b5563;max-width:120px;line-height:1.5">Higher Q = agent prefers giving green to that lane</div>
    </div>
    <div class="qbar-wrap"><div class="qbar-label">Lane 1</div><div class="qbar-outer"><div class="qbar-inner" id="qb1" style="height:4px;background:#818cf8"></div></div><div class="qbar-val" id="qv1">ÔÇö</div></div>
    <div class="qbar-wrap"><div class="qbar-label">Lane 2</div><div class="qbar-outer"><div class="qbar-inner" id="qb2" style="height:4px;background:#38bdf8"></div></div><div class="qbar-val" id="qv2">ÔÇö</div></div>
    <div class="qbar-wrap"><div class="qbar-label">Lane 3</div><div class="qbar-outer"><div class="qbar-inner" id="qb3" style="height:4px;background:#4ade80"></div></div><div class="qbar-val" id="qv3">ÔÇö</div></div>
    <div class="qbar-wrap"><div class="qbar-label">Lane 4</div><div class="qbar-outer"><div class="qbar-inner" id="qb4" style="height:4px;background:#fbbf24"></div></div><div class="qbar-val" id="qv4">ÔÇö</div></div>
  </div>

  <!-- Charts ÔÇö all streaming from /rl_api -->
  <div class="cgrid">
    <div class="cc">
      <h3>­ƒôê Reward per Cycle <span id="ltRew"></span></h3>
      <div class="cw"><canvas id="chartReward"></canvas></div>
    </div>
    <div class="cc">
      <h3>­ƒôë Epsilon Decay <span id="ltEps"></span></h3>
      <div class="cw"><canvas id="chartEps"></canvas></div>
    </div>
    <div class="cc">
      <h3>ÔÜí Q-Network Loss <span id="ltLoss"></span></h3>
      <div class="cw"><canvas id="chartLoss"></canvas></div>
    </div>
    <div class="cc">
      <h3>ÔÅ▒ Total Wait Time <span id="ltWait"></span></h3>
      <div class="cw"><canvas id="chartWait"></canvas></div>
    </div>
  </div>

  <!-- Architecture -->
  <div class="itbl">
    <h3>DQN Architecture (18-dim state ÔåÆ 4 Q-values)</h3>
    <table>
      <thead><tr><th>Layer</th><th>Output</th><th>Activation</th><th>Note</th></tr></thead>
      <tbody>
        <tr><td>Input</td><td>18</td><td>ÔÇö</td><td>density(4)+wait(4)+ambulance(4)+pedestrian(4)+weather(1)+phase(1)</td></tr>
        <tr><td>Dense 1</td><td>256</td><td>ReLU</td><td>BatchNorm</td></tr>
        <tr><td>Dense 2</td><td>256</td><td>ReLU</td><td>Dropout 0.2</td></tr>
        <tr><td>Dense 3</td><td>128</td><td>ReLU</td><td>ÔÇö</td></tr>
        <tr><td>Output</td><td>4</td><td>Linear</td><td>Q(s,a) for each lane</td></tr>
      </tbody>
    </table>
  </div>
  <div class="itbl">
    <h3>Reward Function</h3>
    <table>
      <thead><tr><th>Event</th><th>Reward</th></tr></thead>
      <tbody>
        <tr><td>Wait time decreased</td><td><span class="pill pg">+2 ├ù ╬öwait</span></td></tr>
        <tr><td>Ambulance served</td><td><span class="pill pg">+20</span></td></tr>
        <tr><td>Pedestrian cleared</td><td><span class="pill pg">+5</span></td></tr>
        <tr><td>Starvation relief</td><td><span class="pill pg">+3</span></td></tr>
        <tr><td>Dense lane cost</td><td><span class="pill pr">ÔêÆ0.1 ├ù density</span></td></tr>
      </tbody>
    </table>
  </div>
</main>

<script>
const chartOpts = (yLabel) => ({
  responsive:true, maintainAspectRatio:false,
  animation:{duration:0},
  plugins:{legend:{display:false}},
  scales:{
    x:{display:false, grid:{color:'#1a2744'}},
    y:{grid:{color:'#1a2744'}, ticks:{color:'#4b5563',font:{size:10}},
       title:{display:!!yLabel,text:yLabel,color:'#4b5563',font:{size:10}}}
  }
});

function makeChart(id, color, fill, yLabel) {
  return new Chart(document.getElementById(id), {
    type:'line',
    data:{labels:[], datasets:[{
      data:[], borderColor:color,
      backgroundColor: fill ? color.replace('rgb','rgba').replace(')',',0.12)') : 'transparent',
      borderWidth:1.8, pointRadius:0, tension:0.35, fill
    }]},
    options: chartOpts(yLabel)
  });
}

const cReward = makeChart('chartReward','rgb(129,140,248)',true,'reward');
const cEps    = makeChart('chartEps',   'rgb(251,191,36)', true,'╬Á');
const cLoss   = makeChart('chartLoss',  'rgb(248,113,113)',true,'loss');
const cWait   = makeChart('chartWait',  'rgb(56,189,248)', true,'wait');

const MAX_PTS = 100;
function pushPt(chart, val, labelEl, unit) {
  if(val === null || val === undefined) return;
  chart.data.labels.push('');
  chart.data.datasets[0].data.push(val);
  if(chart.data.labels.length > MAX_PTS) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update('none');
  if(labelEl) document.getElementById(labelEl).textContent = val + (unit||'');
}

const QCOLORS = ['#818cf8','#38bdf8','#4ade80','#fbbf24'];
function updateQBars(qvals) {
  if(!qvals || qvals.length < 4) return;
  const minQ = Math.min(...qvals);
  const maxQ = Math.max(...qvals);
  const range = Math.max(maxQ - minQ, 0.001);
  for(let i=0;i<4;i++) {
    const pct = ((qvals[i] - minQ) / range) * 70 + 4; // 4-74px
    const bar = document.getElementById('qb'+(i+1));
    const val = document.getElementById('qv'+(i+1));
    if(bar) bar.style.height = pct+'px';
    if(val) val.textContent = qvals[i];
    // highlight max
    if(bar) bar.style.background = (i === qvals.indexOf(Math.max(...qvals))) ? '#22c55e' : QCOLORS[i];
  }
}

async function poll() {
  try {
    const d = await fetch('/rl_api').then(r => r.json());

    // KPIs
    document.getElementById('kEps').textContent   = d.epsilon   !== undefined ? d.epsilon   : 'ÔÇö';
    document.getElementById('kRew').textContent   = d.total_reward !== undefined ? d.total_reward : 'ÔÇö';
    document.getElementById('kSteps').textContent = d.step_count !== undefined ? d.step_count : 'ÔÇö';
    document.getElementById('kMem').textContent   = d.memory_size !== undefined ? d.memory_size : 'ÔÇö';
    document.getElementById('kMode').textContent  = d.mode || 'ÔÇö';
    document.getElementById('kAvgR').textContent  = d.avg_reward !== undefined ? d.avg_reward : 'ÔÇö';
    document.getElementById('kAvgW').textContent  = d.avg_wait   !== undefined ? d.avg_wait   : 'ÔÇö';

    // Loss ÔÇö only show latest real value, never 'ÔÇö' if array has data
    const losses = d.losses || [];
    const latestLoss = losses.length ? losses[losses.length-1] : null;
    document.getElementById('kLoss').textContent = latestLoss !== null ? latestLoss : 'ÔÇö';

    // Push to charts ÔÇö use latest value from each history array
    const rewards  = d.rewards  || [];
    const epsilons = d.epsilons || [];
    const waits    = d.waits    || [];

    if(rewards.length)  pushPt(cReward, rewards[rewards.length-1],   'ltRew');
    if(epsilons.length) pushPt(cEps,    epsilons[epsilons.length-1], 'ltEps');
    if(losses.length)   pushPt(cLoss,   losses[losses.length-1],     'ltLoss');
    if(waits.length)    pushPt(cWait,   waits[waits.length-1],       'ltWait');

    // Q-values
    updateQBars(d.q_values);

  } catch(e) { console.warn('rl_api error:', e); }
}

poll();
setInterval(poll, 1500);
</script>
</body>
</html>
