const $ = id => document.getElementById(id);
const statusEl = $('status');
const healthScore = $('healthScore');
const scoreBox = $('scoreBox');
const cpuPct = $('cpuPct'), cpuFill = $('cpuFill'), cpuFreq = $('cpuFreq'), cpuTemp = $('cpuTemp');
const gpuPct = $('gpuPct'), gpuFill = $('gpuFill'), gpuTemp = $('gpuTemp'), gpuVram = $('gpuVram');
const ramPct = $('ramPct'), ramFill = $('ramFill'), ramUsed = $('ramUsed'), ramTotal = $('ramTotal');
const netDown = $('netDown'), netUp = $('netUp'), netFill = $('netFill');
const diskRead = $('diskRead'), diskWrite = $('diskWrite');
const diagList = $('diagList');
const procList = $('procList');
const stopBtn = $('stopBtn');

const N = 60;

const chartsOk = typeof Chart !== 'undefined';
const logEvents = [];
let sortCol = 'cpu', sortAsc = false;
let procData = [];
function makeChart(ctx, color) {
  if (!chartsOk) return null;
  const c = ctx.getContext('2d');
  const grad = c.createLinearGradient(0, 0, 0, 42);
  grad.addColorStop(0, color + '35');
  grad.addColorStop(1, color + '00');
  return new Chart(ctx, {
    type: 'line',
    data: { labels: Array(N).fill(''), datasets: [{ data: Array(N).fill(0), borderColor: color, backgroundColor: grad, borderWidth: 1.5, fill: true, tension: 0.3, pointRadius: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      scales: { x: { display: false }, y: { min: 0, max: 100, display: false } },
      plugins: { legend: { display: false }, tooltip: { enabled: true, mode: 'nearest', intersect: false, callbacks: { label: ctx => ctx.parsed.y.toFixed(1) + '%' } } },
      interaction: { intersect: false, mode: 'nearest' },
    },
  });
}

const cpuChart = makeChart($('cpuChart'), '#00d4ff');
const gpuChart = makeChart($('gpuChart'), '#ff6b35');
const ramChart = makeChart($('ramChart'), '#7c3aed');

function pushChart(chart, val) {
  if (!chart) return;
  chart.data.datasets[0].data.push(Math.min(100, Math.max(0, val)));
  chart.data.datasets[0].data.shift();
  chart.update('none');
}

function setBar(el, pct) {
  el.style.width = Math.min(100, Math.max(0, pct)) + '%';
}

let pingTimer = null;

function connect() {
  const ws = new WebSocket('ws://' + location.host + '/ws');
  ws.onopen = () => {
    statusEl.className = 'hdr-status connected';
    if (pingTimer) clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping');
    }, 30000);
  };
  ws.onmessage = e => {
    try { update(JSON.parse(e.data)); } catch (_) {}
  };
  ws.onclose = () => {
    statusEl.className = 'hdr-status';
    setTimeout(connect, 2000);
  };
  ws.onerror = () => ws.close();
}

function update(d) {
  const cpu = d.cpu, gpu = d.gpu, mem = d.memory, net = d.network, disk = d.disk, diag = d.diagnostic, procs = d.processes;

  cpuPct.textContent = Math.round(cpu.percent) + '%';
  setBar(cpuFill, cpu.percent);
  cpuFreq.textContent = cpu.freq ? cpu.freq + ' GHz' : '-- GHz';
  cpuTemp.textContent = cpu.temp !== undefined ? cpu.temp + '\u00B0C' : '-- \u00B0C';

  gpuPct.textContent = Math.round(gpu.percent) + '%';
  setBar(gpuFill, gpu.percent);
  gpuTemp.textContent = gpu.temp ? gpu.temp + '\u00B0C' : '-- \u00B0C';
  gpuVram.textContent = gpu.vram_used ? gpu.vram_used + ' MB' : '-- MB';

  ramPct.textContent = Math.round(mem.percent) + '%';
  setBar(ramFill, mem.percent);
  ramUsed.textContent = mem.used_gb + ' GB';
  ramTotal.textContent = mem.total_gb;

  netDown.textContent = '\u2193 ' + net.download_speed.toFixed(2);
  netUp.textContent = net.upload_speed.toFixed(2);
  setBar(netFill, Math.min(100, net.download_speed * 20));
  diskRead.textContent = disk.read_speed.toFixed(1);
  diskWrite.textContent = disk.write_speed.toFixed(1);

  pushChart(cpuChart, cpu.percent);
  pushChart(gpuChart, gpu.percent);
  pushChart(ramChart, mem.percent);

  healthScore.textContent = diag.health_score;
  scoreBox.style.borderColor = diag.health_score >= 80 ? 'rgba(16,185,129,.4)' : diag.health_score >= 50 ? 'rgba(245,158,11,.4)' : 'rgba(239,68,68,.4)';
  healthScore.style.color = diag.health_score >= 80 ? '#10b981' : diag.health_score >= 50 ? '#f59e0b' : '#ef4444';

  let dh = '';
  for (const a of diag.alerts) {
    dh += '<div class="alert ' + a.type + '">'
       + '<span class="icon">' + (a.icon || '\u2139\uFE0F') + '</span>'
       + '<div class="body"><div class="title">' + a.title + '</div>'
       + '<div class="msg">' + a.message + '</div></div></div>';
  }
  if (d.log_events) {
    for (const e of d.log_events) {
      if (e.type === 'idle') {
        dh += '<div class="alert idle"><span class="icon">' + e.icon + '</span>'
           + '<div class="body"><div class="title">\uC720\uD759 \uD504\uB85C\uC138\uC2A4</div>'
           + '<div class="msg">' + e.msg + '</div></div></div>';
      }
    }
  }
  diagList.innerHTML = dh;

  procData = procs;
  renderProcs();

   // Log - accumulate abnormal events
   if (d.log_buffer) {
     const WARN = {'warning':1,'danger':1,'idle':1};
     for (const e of d.log_buffer) {
       if (!WARN[e.type]) continue;
       const key = e.time + e.msg;
       if (!logEvents.some(x => x.key === key)) {
         logEvents.push({key: key, time: e.time, icon: e.icon, msg: e.msg, type: e.type});
       }
     }
     let lh = '';
     for (const e of logEvents) {
       const cls = e.type === 'warning' ? 'l-warning' : e.type === 'danger' ? 'l-danger' : 'l-idle';
       lh += '<div class="log-row ' + cls + '">'
          + '<span class="log-time">' + e.time + '</span>'
          + '<span class="log-msg">' + e.icon + ' ' + e.msg + '</span></div>';
     }
     $('logList').innerHTML = lh || '<div style="text-align:center;padding:16px 0;font-size:.65rem;opacity:.25">\uBAA8\uB450 \uC815\uC0C1</div>';
   }
}

function renderProcs() {
  const sorted = [...procData].sort((a, b) => {
    let va, vb;
    if (sortCol === 'cpu') { va = a.cpu_percent; vb = b.cpu_percent; }
    else if (sortCol === 'ram') { va = a.memory_mb; vb = b.memory_mb; }
    else { va = Number(a.gpu_sm) || 0; vb = Number(b.gpu_sm) || 0; }
    return sortAsc ? va - vb : vb - va;
  });
  let ph = '';
  for (const p of sorted) {
    const cw = Math.min(100, p.cpu_percent);
    const mw = Math.min(100, p.memory_mb / 512 * 100);
    const ms = p.memory_mb > 1024 ? (p.memory_mb / 1024).toFixed(1) + 'G' : p.memory_mb + 'M';
    const gw = Number(p.gpu_sm) || 0;
    ph += '<div class="proc-row" style="grid-template-columns:1fr 55px 55px 50px">'
       + '<span class="proc-name" title="' + p.name + '">' + p.name + '</span>'
       + '<div style="display:flex;align-items:center;gap:4px"><div class="proc-bar-wr" style="flex:1"><div class="proc-bar cpu" style="width:' + cw + '%"></div></div><span class="proc-stat">' + p.cpu_percent + '%</span></div>'
       + '<div style="display:flex;align-items:center;gap:4px"><div class="proc-bar-wr" style="flex:1"><div class="proc-bar mem" style="width:' + mw + '%"></div></div><span class="proc-stat">' + ms + '</span></div>'
       + '<div style="display:flex;align-items:center;gap:4px"><div class="proc-bar-wr" style="flex:1"><div class="proc-bar" style="background:#ff6b35;width:' + gw + '%"></div></div><span class="proc-stat">' + gw + '%</span></div>'
       + '</div>';
  }
  procList.innerHTML = ph;
  updateSortIcons();
}

function updateSortIcons() {
  const colors = { cpu: '#00d4ff', ram: '#7c3aed', gpu: '#ff6b35' };
  document.querySelectorAll('.sort-hdr').forEach(h => {
    const col = h.dataset.sort;
    const ico = h.querySelector('.sort-ico');
    if (col === sortCol) {
      h.style.color = colors[col] || '#e8ecf4';
      ico.textContent = sortAsc ? ' \u25B2' : ' \u25BC';
    } else {
      h.style.color = '';
      ico.textContent = '';
    }
  });
}

document.querySelectorAll('.sort-hdr').forEach(el => {
  el.onclick = () => {
    const col = el.dataset.sort;
    if (sortCol === col) sortAsc = !sortAsc;
    else { sortCol = col; sortAsc = false; }
    renderProcs();
  };
});

stopBtn.onclick = () => {
  fetch('/stop', { method: 'POST' }).catch(() => {});
  stopBtn.textContent = '...';
  stopBtn.disabled = true;
};

connect();
