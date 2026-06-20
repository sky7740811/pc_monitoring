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
const logList = $('logList');
const logSummary = $('logSummary');
const btnExport = $('btnExport');

const N = 60;
const labels = Array(N).fill('');

let logBuffer = [];

/* Charts - skip if Chart.js not loaded */
const chartsOk = typeof Chart !== 'undefined';

function makeChart(ctx, color) {
  const c = ctx.getContext('2d');
  const grad = c.createLinearGradient(0, 0, 0, 42);
  grad.addColorStop(0, color + '35');
  grad.addColorStop(1, color + '00');
  return new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: [{ data: Array(N).fill(0), borderColor: color, backgroundColor: grad, borderWidth: 1.5, fill: true, tension: 0.3, pointRadius: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      scales: { x: { display: false }, y: { min: 0, max: 100, display: false } },
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: true,
          mode: 'nearest',
          intersect: false,
          callbacks: {
            label: ctx => ctx.parsed.y.toFixed(1) + '%'
          }
        }
      },
      interaction: { intersect: false, mode: 'nearest' },
    },
  });
}

let cpuChart, gpuChart, ramChart;
if (chartsOk) {
  cpuChart = makeChart($('cpuChart'), '#00d4ff');
  gpuChart = makeChart($('gpuChart'), '#ff6b35');
  ramChart = makeChart($('ramChart'), '#7c3aed');
}

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

  let ph = '';
  for (const p of procs) {
    const cw = Math.min(100, p.cpu_percent);
    const mw = Math.min(100, p.memory_mb / 512 * 100);
    const ms = p.memory_mb > 1024 ? (p.memory_mb / 1024).toFixed(1) + 'G' : p.memory_mb + 'M';
    ph += '<div class="proc-row">'
       + '<span class="proc-name" title="' + p.name + '">' + p.name + '</span>'
       + '<div style="display:flex;align-items:center;gap:4px"><div class="proc-bar-wr" style="flex:1"><div class="proc-bar cpu" style="width:' + cw + '%"></div></div><span class="proc-stat">' + p.cpu_percent + '%</span></div>'
       + '<div style="display:flex;align-items:center;gap:4px"><div class="proc-bar-wr" style="flex:1"><div class="proc-bar mem" style="width:' + mw + '%"></div></div><span class="proc-stat">' + ms + '</span></div>'
       + '</div>';
  }
  procList.innerHTML = ph;

  // Update log buffer
  if (d.log_buffer) {
    logBuffer = d.log_buffer;
  }
  if (d.log_summary) {
    renderSummary(d.log_summary);
  }
  renderLog();
}

/* Tab switching */
const tabBtns = document.querySelectorAll('.tab');
const panels = { dash: document.querySelector('.panel-dash'), log: document.querySelector('.panel-log') };
let curTab = 'dash';
if (panels.dash) panels.dash.style.display = '';
tabBtns.forEach(btn => {
  btn.onclick = () => {
    curTab = btn.dataset.tab;
    tabBtns.forEach(b => b.classList.toggle('tab-a', b === btn));
    Object.keys(panels).forEach(k => { panels[k].style.display = k === curTab ? '' : 'none'; });
    if (curTab === 'log') renderLog();
  };
});

/* Log filters */
let logFilter = 'all';
document.querySelectorAll('.lfil').forEach(btn => {
  btn.onclick = () => {
    logFilter = btn.dataset.f;
    document.querySelectorAll('.lfil').forEach(b => b.classList.toggle('lfil-a', b === btn));
    renderLog();
  };
});

function renderLog() {
  let html = '';
  const filtered = logFilter === 'all' ? logBuffer : logBuffer.filter(e => e.type === logFilter);
  if (filtered.length === 0) {
    html = '<div class="log-empty">\uB85C\uADF8\uAC00 \uC5C6\uC2B5\uB2C8\uB2E4</div>';
  } else {
    for (const e of filtered) {
      const cls = e.type === 'warning' ? 'l-warning' : e.type === 'danger' ? 'l-danger' : e.type === 'idle' ? 'l-idle' : e.type === 'info' ? 'l-info' : 'l-success';
      html += '<div class="log-row ' + cls + '">'
           + '<span class="log-time">' + e.time + '</span>'
           + '<span class="log-msg">' + e.icon + ' ' + e.msg + '</span></div>';
    }
  }
  logList.innerHTML = html;
}

function renderSummary(s) {
  logSummary.innerHTML = '<table>'
    + '<tr><td>\uC138\uC158</td><td>' + s.duration + '</td></tr>'
    + '<tr><td>CPU</td><td>\uD3C9\uADPC ' + s.cpu_avg + '% / \uCD5C\uACE0 ' + s.cpu_max + '%</td></tr>'
    + '<tr><td>GPU</td><td>\uD3C9\uADPC ' + s.gpu_avg + '% / \uCD5C\uACE0 ' + s.gpu_max + '%</td></tr>'
    + '<tr><td>GPU Temp</td><td>\uD3C9\uADPC ' + s.gpu_temp_avg + '\u00B0C / \uCD5C\uACE0 ' + s.gpu_temp_max + '\u00B0C</td></tr>'
    + '<tr><td>VRAM</td><td>\uCD5C\uACE0 ' + s.vram_max + '%</td></tr>'
    + '<tr><td>RAM</td><td>\uD3C9\uADPC ' + s.mem_avg + '%</td></tr>'
    + '<tr><td>\uACBD\uACE0</td><td>\u26A0\uFE0F ' + s.warnings + ' / \U0001F525 ' + s.dangers + '</td></tr>'
    + '</table>';
}

/* Export */
btnExport.onclick = () => {
  fetch('/stop', { method: 'POST' }).catch(() => {});
  btnExport.textContent = '저장 중...';
  btnExport.disabled = true;
};

stopBtn.onclick = () => {
  fetch('/stop', { method: 'POST' }).catch(() => {});
  stopBtn.textContent = '...';
  stopBtn.disabled = true;
};

// Auto-refresh log tab periodically
setInterval(() => { if (curTab === 'log') renderLog(); }, 3000);

connect();
