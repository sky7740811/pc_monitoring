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
}

stopBtn.onclick = () => {
  fetch('/stop', { method: 'POST' }).catch(() => {});
  stopBtn.textContent = '...';
  stopBtn.disabled = true;
};

connect();
