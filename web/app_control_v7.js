(function () {
  'use strict';

  const host = document.getElementById('host');
  const port = document.getElementById('port');
  const connectButton = document.getElementById('connectButton');
  const connectionState = document.getElementById('connectionState');
  const backendState = document.getElementById('backendState');
  const camera = document.getElementById('liveCamera');
  const cameraState = document.getElementById('cameraState');
  const joystick = document.getElementById('joystick');
  const knob = document.getElementById('joystickKnob');
  const joystickCaption = document.getElementById('joystickCaption');
  const axisX = document.getElementById('axisX');
  const axisY = document.getElementById('axisY');
  const axisMode = document.getElementById('axisMode');
  const motionState = document.getElementById('motionState');
  const speed = document.getElementById('speed');
  const speedValue = document.getElementById('speedValue');
  const yoloState = document.getElementById('yoloState');
  const yoloResult = document.getElementById('yoloResult');

  host.value = new URLSearchParams(location.search).get('host') || location.hostname || '10.71.253.19';

  let ws = null;
  let reconnectTimer = null;
  let reconnectDelay = 1000;
  let manualClose = false;
  let active = false;
  let source = 'none';
  let lastButton = null;
  let rawX = 0;
  let rawY = 0;

  function speedNow() { return Number(speed.value) || 30; }
  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }
  function vibrate() { if (navigator.vibrate) navigator.vibrate(8); }
  function setConnection(text, online) {
    connectionState.textContent = text;
    connectionState.classList.toggle('online', !!online);
    connectionState.classList.toggle('offline', !online);
  }
  function setBackend(text, online) {
    backendState.textContent = text;
    backendState.classList.toggle('online', !!online);
    backendState.classList.toggle('offline', !online);
  }
  function setMotion(text) { motionState.textContent = text; }
  function updateAxes(x, y, mode) {
    axisX.textContent = 'X ' + (x > 0 ? '+' : '') + x;
    axisY.textContent = 'Y ' + (y > 0 ? '+' : '') + y;
    axisMode.textContent = mode;
  }
  function resetJoystick() {
    rawX = 0;
    rawY = 0;
    knob.style.transform = 'translate(-50%, -50%)';
    updateAxes(0, 0, '摇杆待机');
    joystickCaption.textContent = '拖动摇杆开始移动';
  }
  function stop() {
    active = false;
    source = 'none';
    lastButton = null;
    document.querySelectorAll('.drive-button.is-pressed').forEach(function (b) { b.classList.remove('is-pressed'); });
    resetJoystick();
    setMotion('已停车');
    send({ type: 'stop' });
  }

  function stickPacket() {
    const scale = speedNow() / 100;
    const x = Math.round(rawX * scale);
    const y = Math.round(rawY * scale);
    const threshold = 7;
    if (Math.abs(x) < threshold && Math.abs(y) < threshold) {
      updateAxes(x, y, '摇杆中心');
      return { type: 'joystick', x: 0, y: 0 };
    }
    // Cardinal joystick movement intentionally uses the same working button path.
    // This prevents the X/Y axis interpretation from diverging between controls.
    if (Math.abs(x) >= Math.abs(y)) {
      const action = x < 0 ? 'left' : 'right';
      updateAxes(x, y, action === 'left' ? '左移通道' : '右移通道');
      return { type: 'button', action: action, speed: Math.max(5, Math.abs(x)) };
    }
    const action = y > 0 ? 'forward' : 'back';
    updateAxes(x, y, action === 'forward' ? '前进通道' : '后退通道');
    return { type: 'button', action: action, speed: Math.max(5, Math.abs(y)) };
  }
  function sendStick() {
    const packet = stickPacket();
    send(packet);
    setMotion(packet.type === 'button' ? packet.action : '摇杆控制中');
  }
  function repeat() {
    if (!active) return;
    if (source === 'joystick') sendStick();
    if (source === 'button' && lastButton) {
      lastButton.speed = speedNow();
      send(lastButton);
      setMotion(lastButton.action);
    }
  }

  function scheduleReconnect() {
    if (manualClose || reconnectTimer) return;
    reconnectTimer = setTimeout(function () {
      reconnectTimer = null;
      connect();
    }, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 1.5, 5000);
  }
  function connect() {
    manualClose = false;
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
    if (ws) {
      ws.onclose = null;
      try { ws.close(); } catch (_) {}
    }
    setConnection('连接中', false);
    setBackend('等待控制端', false);
    ws = new WebSocket('ws://' + (host.value || location.hostname) + ':' + (port.value || '8081') + '/ws');
    ws.onopen = function () {
      reconnectDelay = 1000;
      setConnection('网页已连接', true);
      setBackend('网页控制服务已连接', true);
      send({ type: 'speed', xy: speedNow(), z: speedNow() });
    };
    ws.onmessage = function (event) {
      let message;
      try { message = JSON.parse(event.data); } catch (_) { return; }
      const linked = message.backend_connected === true || message.backend === true;
      const unlinked = message.backend_connected === false || message.backend === false;
      if (linked) setBackend('小车控制端已连接', true);
      else if (unlinked) setBackend('等待小车 TCP', false);
      if (message.state === 'backend_unavailable') setBackend('等待小车 TCP', false);
    };
    ws.onerror = function () {
      setConnection('连接异常', false);
      setBackend('正在重连…', false);
    };
    ws.onclose = function () {
      stop();
      setConnection('断线，自动重连中', false);
      setBackend('连接已断开，正在重连…', false);
      scheduleReconnect();
    };
  }

  function pressButton(button) {
    const action = button.dataset.action;
    vibrate();
    button.classList.add('is-pressed');
    if (action === 'stop') {
      stop();
      return;
    }
    active = true;
    source = 'button';
    lastButton = { type: 'button', action: action, speed: speedNow() };
    send(lastButton);
    setMotion(action);
  }
  function releaseButton(button) {
    button.classList.remove('is-pressed');
    if (source === 'button' && lastButton && lastButton.action === button.dataset.action) stop();
  }
  document.querySelectorAll('.drive-button').forEach(function (button) {
    button.addEventListener('pointerdown', function (event) {
      event.preventDefault();
      button.setPointerCapture(event.pointerId);
      pressButton(button);
    });
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(function (name) {
      button.addEventListener(name, function () { releaseButton(button); });
    });
  });

  function moveJoystick(event) {
    const rect = joystick.getBoundingClientRect();
    const outerRadius = Math.min(rect.width, rect.height) / 2;
    const knobRadius = outerRadius * .31 / 2;
    const travel = Math.max(20, outerRadius - knobRadius - 7);
    let dx = event.clientX - rect.left - rect.width / 2;
    let dy = event.clientY - rect.top - rect.height / 2;
    const distance = Math.hypot(dx, dy);
    if (distance > travel) { dx = dx * travel / distance; dy = dy * travel / distance; }
    rawX = Math.round(dx / travel * 100);
    rawY = Math.round(-dy / travel * 100);
    knob.style.transform = 'translate(calc(-50% + ' + dx + 'px), calc(-50% + ' + dy + 'px))';
    active = true;
    source = 'joystick';
    lastButton = null;
    joystickCaption.textContent = '横向移动已使用按钮同源通道';
    sendStick();
  }
  joystick.addEventListener('pointerdown', function (event) {
    event.preventDefault();
    vibrate();
    joystick.setPointerCapture(event.pointerId);
    moveJoystick(event);
  });
  joystick.addEventListener('pointermove', function (event) {
    if (joystick.hasPointerCapture(event.pointerId)) moveJoystick(event);
  });
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(function (name) {
    joystick.addEventListener(name, stop);
  });

  speed.addEventListener('input', function () {
    speedValue.textContent = speed.value;
    send({ type: 'speed', xy: speedNow(), z: speedNow() });
    repeat();
  });
  connectButton.addEventListener('click', connect);
  document.getElementById('refreshCamera').addEventListener('click', function () {
    camera.src = '/camera.mjpeg?t=' + Date.now();
    cameraState.textContent = '正在刷新视频流…';
  });
  camera.addEventListener('load', function () { cameraState.textContent = '视频流正常'; });
  camera.addEventListener('error', function () { cameraState.textContent = '视频流未连接'; });
  window.addEventListener('beforeunload', function () { manualClose = true; stop(); if (ws) ws.close(); });

  async function refreshYolo() {
    try {
      const response = await fetch('/api/yolo/latest?t=' + Date.now(), { cache: 'no-store' });
      const data = await response.json();
      const detections = data.detections || [];
      yoloState.textContent = detections.length ? detections.length + ' 个目标' : '暂无目标';
      yoloResult.textContent = JSON.stringify(data, null, 2);
    } catch (_) {
      yoloState.textContent = '等待识别接口';
    }
  }

  speedValue.textContent = speed.value;
  setInterval(repeat, 100);
  setInterval(function () { send({ type: 'heartbeat' }); }, 4000);
  setInterval(refreshYolo, 2500);
  refreshYolo();
  connect();
}());
