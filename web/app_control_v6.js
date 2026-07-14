(function () {
  'use strict';
  const host = document.getElementById('host'), port = document.getElementById('port');
  const connectButton = document.getElementById('connectButton'), state = document.getElementById('connectionState');
  const backend = document.getElementById('backendState'), speed = document.getElementById('speed'), speedValue = document.getElementById('speedValue');
  const joystick = document.getElementById('joystick'), knob = document.getElementById('joystickKnob'), camera = document.getElementById('liveCamera');
  host.value = new URLSearchParams(location.search).get('host') || location.hostname || '10.71.253.19';
  let ws = null, reconnectTimer = null, reconnectDelay = 1000, manual = false, repeatTimer = null, heartbeatTimer = null;
  let active = false, command = null, rawX = 0, rawY = 0;

  function setState(text, connected) { state.textContent = text; state.classList.toggle('online', !!connected); state.classList.toggle('offline', !connected); }
  function send(data) { if (ws && ws.readyState === WebSocket.OPEN) { ws.send(JSON.stringify(data)); return true; } return false; }
  function speedValueNow() { return Number(speed.value) || 30; }
  function joystickCommand() { const k = speedValueNow() / 100; return { type: 'joystick', x: Math.round(rawX * k), y: Math.round(rawY * k) }; }
  function stop() { active = false; command = null; rawX = 0; rawY = 0; knob.style.transform = 'translate(-50%, -50%)'; send({ type: 'stop' }); }
  function hold(action) { if (action === 'stop') { stop(); return; } active = true; command = { type: 'button', action: action, speed: speedValueNow() }; send(command); }
  function repeat() { if (!active || !command) return; if (command.type === 'button') { command.speed = speedValueNow(); send(command); } else send(joystickCommand()); }
  function scheduleReconnect() { if (manual || reconnectTimer) return; reconnectTimer = setTimeout(function () { reconnectTimer = null; connect(); }, reconnectDelay); reconnectDelay = Math.min(reconnectDelay * 1.5, 5000); }
  function connect() {
    manual = false; clearTimeout(reconnectTimer); reconnectTimer = null;
    if (ws) { ws.onclose = null; try { ws.close(); } catch (_) {} }
    setState('连接中', false); backend.textContent = '正在连接控制服务…';
    ws = new WebSocket('ws://' + (host.value || location.hostname) + ':' + (port.value || '8081') + '/ws');
    ws.onopen = function () { reconnectDelay = 1000; setState('已连接', true); backend.textContent = '控制服务已连接'; send({ type: 'speed', xy: speedValueNow(), z: speedValueNow() }); };
    ws.onmessage = function (event) {
      let m; try { m = JSON.parse(event.data); } catch (_) { return; }
      const linked = (m.backend_connected === true || m.backend === true);
      if (m.backend_connected === false || m.backend === false) backend.textContent = '网页已连接，但小车控制端未连接';
      else if (linked) backend.textContent = '小车控制端已连接';
      if (m.state === 'connected') setState('已连接', true);
      if (m.state === 'backend_unavailable') setState('小车 TCP 未连接', false);
    };
    ws.onerror = function () { setState('连接异常，准备重连', false); };
    ws.onclose = function () { stop(); setState('断线，自动重连中', false); backend.textContent = '连接已断开，正在自动重连…'; scheduleReconnect(); };
  }
  function move(event) {
    const r = joystick.getBoundingClientRect(), radius = Math.min(r.width, r.height) / 2;
    let dx = event.clientX - r.left - r.width / 2, dy = event.clientY - r.top - r.height / 2, d = Math.hypot(dx, dy);
    if (d > radius) { dx *= radius / d; dy *= radius / d; }
    knob.style.transform = 'translate(calc(-50% + ' + dx + 'px), calc(-50% + ' + dy + 'px))';
    rawX = Math.round(dx / radius * 100); rawY = Math.round(-dy / radius * 100); active = true; command = { type: 'joystick' }; send(joystickCommand());
  }
  joystick.addEventListener('pointerdown', function (e) { e.preventDefault(); joystick.setPointerCapture(e.pointerId); move(e); });
  joystick.addEventListener('pointermove', function (e) { if (joystick.hasPointerCapture(e.pointerId)) move(e); });
  ['pointerup', 'pointercancel'].forEach(function (n) { joystick.addEventListener(n, function (e) { if (joystick.hasPointerCapture(e.pointerId)) joystick.releasePointerCapture(e.pointerId); stop(); }); });
  document.querySelectorAll('.drive-button').forEach(function (b) {
    b.addEventListener('pointerdown', function (e) { e.preventDefault(); b.setPointerCapture(e.pointerId); hold(b.dataset.action); });
    ['pointerup', 'pointercancel'].forEach(function (n) { b.addEventListener(n, stop); });
  });
  speed.addEventListener('input', function () { speedValue.textContent = speed.value; send({ type: 'speed', xy: speedValueNow(), z: speedValueNow() }); if (command && command.type === 'button') command.speed = speedValueNow(); repeat(); });
  connectButton.addEventListener('click', connect);
  document.getElementById('refreshCamera').addEventListener('click', function () { camera.src = '/camera.mjpeg?t=' + Date.now(); });
  window.addEventListener('beforeunload', function () { manual = true; stop(); if (ws) ws.close(); });
  speedValue.textContent = speed.value;
  repeatTimer = setInterval(repeat, 100);
  heartbeatTimer = setInterval(function () { send({ type: 'heartbeat' }); }, 4000);
  connect();
}());
