(function () {
  'use strict';
  const $ = function (id) { return document.getElementById(id); };
  const host = $('host'), port = $('port'), connectButton = $('connectButton');
  const connectionState = $('connectionState'), backendState = $('backendState');
  const camera = $('liveCamera'), cameraState = $('cameraState');
  const joystick = $('joystick'), knob = $('joystickKnob'), joystickCaption = $('joystickCaption');
  const axisX = $('axisX'), axisY = $('axisY'), axisMode = $('axisMode'), motionState = $('motionState');
  const speed = $('speed'), speedValue = $('speedValue'), yoloState = $('yoloState'), yoloResult = $('yoloResult');
  host.value = new URLSearchParams(location.search).get('host') || location.hostname || '10.71.253.19';

  let ws = null, reconnectTimer = null, reconnectDelay = 1000, manualClose = false;
  let active = false, source = 'none', currentAction = '', rawX = 0, rawY = 0;

  function speedNow() { return Number(speed.value) || 30; }
  function send(message) { if (ws && ws.readyState === WebSocket.OPEN) { ws.send(JSON.stringify(message)); return true; } return false; }
  function setConnection(text, online) { connectionState.textContent = text; connectionState.classList.toggle('online', !!online); connectionState.classList.toggle('offline', !online); }
  function setBackend(text, online) { backendState.textContent = text; backendState.classList.toggle('online', !!online); backendState.classList.toggle('offline', !online); }
  function setMotion(text) { motionState.textContent = text; }
  function axes(x, y, mode) { axisX.textContent = 'X ' + (x > 0 ? '+' : '') + x; axisY.textContent = 'Y ' + (y > 0 ? '+' : '') + y; axisMode.textContent = mode; }
  function resetStick() { rawX = 0; rawY = 0; knob.style.transform = 'translate(-50%, -50%)'; axes(0, 0, '摇杆待机'); joystickCaption.textContent = '拖动摇杆开始移动'; }
  function stop() { active = false; source = 'none'; currentAction = ''; document.querySelectorAll('.drive-button.is-pressed').forEach(function (b) { b.classList.remove('is-pressed'); }); resetStick(); setMotion('已停车'); send({ type: 'stop' }); }

  // All four translations use one explicit TYPE=10 vector encoder.
  // Rotations remain on the official TYPE=15 direction interface.
  function translation(action, amount) {
    const n = Math.max(5, Math.min(100, Math.round(amount)));
    const vectors = { forward: [0, n], back: [0, -n], left: [-n, 0], right: [n, 0] };
    if (vectors[action]) return { type: 'joystick', x: vectors[action][0], y: vectors[action][1] };
    return { type: 'button', action: action, speed: n };
  }
  function stickPacket() {
    const k = speedNow() / 100, x = Math.round(rawX * k), y = Math.round(rawY * k), dead = 7;
    if (Math.abs(x) < dead && Math.abs(y) < dead) { axes(x, y, '摇杆中心'); return { type: 'joystick', x: 0, y: 0 }; }
    if (Math.abs(x) >= Math.abs(y)) {
      const action = x < 0 ? 'left' : 'right';
      axes(x, y, action === 'left' ? '左移通道' : '右移通道');
      joystickCaption.textContent = '横向已使用 TYPE=10 左右轴';
      return translation(action, Math.abs(x));
    }
    const action = y > 0 ? 'forward' : 'back';
    axes(x, y, action === 'forward' ? '前进通道' : '后退通道');
    joystickCaption.textContent = '纵向已使用 TYPE=10 前后轴';
    return translation(action, Math.abs(y));
  }
  function sendStick() { const packet = stickPacket(); send(packet); setMotion(packet.type === 'joystick' ? '摇杆控制中' : packet.action); }
  function repeat() {
    if (!active) return;
    if (source === 'joystick') sendStick();
    if (source === 'button' && currentAction) { send(translation(currentAction, speedNow())); setMotion(currentAction); }
  }

  function scheduleReconnect() {
    if (manualClose || reconnectTimer) return;
    reconnectTimer = setTimeout(function () { reconnectTimer = null; connect(); }, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 1.5, 5000);
  }
  function connect() {
    manualClose = false; clearTimeout(reconnectTimer); reconnectTimer = null;
    if (ws) { ws.onclose = null; try { ws.close(); } catch (_) {} }
    setConnection('连接中', false); setBackend('等待控制端', false);
    ws = new WebSocket('ws://' + (host.value || location.hostname) + ':' + (port.value || '8081') + '/ws');
    ws.onopen = function () { reconnectDelay = 1000; setConnection('网页已连接', true); setBackend('网页控制服务已连接', true); send({ type: 'speed', xy: speedNow(), z: speedNow() }); };
    ws.onmessage = function (event) { let m; try { m = JSON.parse(event.data); } catch (_) { return; } const linked = m.backend_connected === true || m.backend === true; const unlinked = m.backend_connected === false || m.backend === false; if (linked) setBackend('小车控制端已连接', true); else if (unlinked || m.state === 'backend_unavailable') setBackend('等待小车 TCP', false); };
    ws.onerror = function () { setConnection('连接异常', false); setBackend('正在重连…', false); };
    ws.onclose = function () { stop(); setConnection('断线，自动重连中', false); setBackend('连接已断开，正在重连…', false); scheduleReconnect(); };
  }

  function press(button) {
    const action = button.dataset.action;
    button.classList.add('is-pressed');
    if (navigator.vibrate) navigator.vibrate(8);
    if (action === 'stop') { stop(); return; }
    active = true; source = 'button'; currentAction = action; send(translation(action, speedNow())); setMotion(action);
  }
  function release(button) { button.classList.remove('is-pressed'); if (source === 'button' && currentAction === button.dataset.action) stop(); }
  document.querySelectorAll('.drive-button').forEach(function (button) {
    button.addEventListener('pointerdown', function (event) { event.preventDefault(); button.setPointerCapture(event.pointerId); press(button); });
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(function (name) { button.addEventListener(name, function () { release(button); }); });
  });

  function moveStick(event) {
    const rect = joystick.getBoundingClientRect(), outer = Math.min(rect.width, rect.height) / 2, knobRadius = outer * .31 / 2, travel = Math.max(20, outer - knobRadius - 7);
    let dx = event.clientX - rect.left - rect.width / 2, dy = event.clientY - rect.top - rect.height / 2, distance = Math.hypot(dx, dy);
    if (distance > travel) { dx *= travel / distance; dy *= travel / distance; }
    rawX = Math.round(dx / travel * 100); rawY = Math.round(-dy / travel * 100);
    knob.style.transform = 'translate(calc(-50% + ' + dx + 'px), calc(-50% + ' + dy + 'px))';
    active = true; source = 'joystick'; currentAction = ''; sendStick();
  }
  joystick.addEventListener('pointerdown', function (event) { event.preventDefault(); joystick.setPointerCapture(event.pointerId); moveStick(event); });
  joystick.addEventListener('pointermove', function (event) { if (joystick.hasPointerCapture(event.pointerId)) moveStick(event); });
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(function (name) { joystick.addEventListener(name, stop); });
  speed.addEventListener('input', function () { speedValue.textContent = speed.value; send({ type: 'speed', xy: speedNow(), z: speedNow() }); repeat(); });
  connectButton.addEventListener('click', connect);
  document.getElementById('refreshCamera').addEventListener('click', function () { camera.src = '/camera.mjpeg?t=' + Date.now(); cameraState.textContent = '正在刷新视频流…'; });
  camera.addEventListener('load', function () { cameraState.textContent = '视频流正常'; });
  camera.addEventListener('error', function () { cameraState.textContent = '视频流未连接'; });
  window.addEventListener('beforeunload', function () { manualClose = true; stop(); if (ws) ws.close(); });

  async function refreshYolo() { try { const response = await fetch('/api/yolo/latest?t=' + Date.now(), { cache: 'no-store' }); const data = await response.json(); const detections = data.detections || []; yoloState.textContent = detections.length ? detections.length + ' 个目标' : '暂无目标'; yoloResult.textContent = JSON.stringify(data, null, 2); } catch (_) { yoloState.textContent = '等待识别接口'; } }
  speedValue.textContent = speed.value;
  setInterval(repeat, 100); setInterval(function () { send({ type: 'heartbeat' }); }, 4000); setInterval(refreshYolo, 2500);
  refreshYolo(); connect();
}());
