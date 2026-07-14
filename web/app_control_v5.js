(function () {
  'use strict';

  const hostInput = document.getElementById('host');
  const portInput = document.getElementById('port');
  const connectButton = document.getElementById('connectButton');
  const stateEl = document.getElementById('connectionState');
  const backendEl = document.getElementById('backendState');
  const speedInput = document.getElementById('speed');
  const speedValue = document.getElementById('speedValue');
  const joystick = document.getElementById('joystick');
  const knob = document.getElementById('joystickKnob');
  const camera = document.getElementById('liveCamera');

  hostInput.value = new URLSearchParams(location.search).get('host') || location.hostname || '10.71.253.19';

  let socket = null;
  let reconnectTimer = null;
  let reconnectDelay = 1000;
  let manualClose = false;
  let repeatTimer = null;
  let active = false;
  let lastCommand = null;
  let rawX = 0;
  let rawY = 0;

  function setState(text, connected) {
    stateEl.textContent = text;
    stateEl.classList.toggle('online', !!connected);
    stateEl.classList.toggle('offline', !connected);
  }
  function endpoint() {
    const host = (hostInput.value || location.hostname || '10.71.253.19').trim();
    const port = (portInput.value || '8081').trim();
    return 'ws://' + host + ':' + port + '/ws';
  }
  function send(message) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
      return true;
    }
    return false;
  }
  function currentSpeed() { return Number(speedInput.value) || 30; }
  function joystickMessage() {
    const scale = currentSpeed() / 100;
    return { type: 'joystick', x: Math.round(rawX * scale), y: Math.round(rawY * scale) };
  }
  function stop() {
    active = false;
    lastCommand = null;
    rawX = 0;
    rawY = 0;
    knob.style.transform = 'translate(-50%, -50%)';
    send({ type: 'stop' });
  }
  function holdButton(action) {
    if (action === 'stop') { stop(); return; }
    active = true;
    lastCommand = { type: 'button', action: action, speed: currentSpeed() };
    send(lastCommand);
  }
  function repeatCommand() {
    if (!active || !lastCommand) return;
    if (lastCommand.type === 'button') {
      lastCommand.speed = currentSpeed();
      send(lastCommand);
    } else if (lastCommand.type === 'joystick') {
      send(joystickMessage());
    }
  }
  function startRepeat() {
    if (!repeatTimer) repeatTimer = setInterval(repeatCommand, 100);
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
    if (socket) {
      socket.onclose = null;
      try { socket.close(); } catch (_) {}
    }
    setState('连接中', false);
    backendEl.textContent = '正在连接控制服务…';
    socket = new WebSocket(endpoint());
    socket.onopen = function () {
      reconnectDelay = 1000;
      setState('已连接', true);
      backendEl.textContent = '控制服务已连接';
      send({ type: 'speed', xy: currentSpeed(), z: currentSpeed() });
    };
    socket.onmessage = function (event) {
      let message;
      try { message = JSON.parse(event.data); } catch (_) { return; }
      if (message.backend_connected === false) backendEl.textContent = '网页已连接，但小车控制端未连接';
      if (message.backend_connected === true) backendEl.textContent = '小车控制端已连接';
      if (message.state) setState(message.state, message.state === '已连接');
    };
    socket.onerror = function () { setState('连接异常，准备重连', false); };
    socket.onclose = function () {
      stop();
      setState('断线，自动重连中', false);
      backendEl.textContent = '连接已断开，正在自动重连…';
      scheduleReconnect();
    };
  }

  function setJoystickFromEvent(event) {
    const rect = joystick.getBoundingClientRect();
    const radius = Math.min(rect.width, rect.height) / 2;
    let dx = event.clientX - (rect.left + rect.width / 2);
    let dy = event.clientY - (rect.top + rect.height / 2);
    const distance = Math.hypot(dx, dy);
    if (distance > radius) { dx = dx * radius / distance; dy = dy * radius / distance; }
    knob.style.transform = 'translate(calc(-50% + ' + dx + 'px), calc(-50% + ' + dy + 'px))';
    rawX = Math.round(dx / radius * 100);
    rawY = Math.round(-dy / radius * 100);
    active = true;
    lastCommand = { type: 'joystick' };
    send(joystickMessage());
  }
  joystick.addEventListener('pointerdown', function (event) {
    event.preventDefault();
    joystick.setPointerCapture(event.pointerId);
    setJoystickFromEvent(event);
  });
  joystick.addEventListener('pointermove', function (event) {
    if (joystick.hasPointerCapture(event.pointerId)) setJoystickFromEvent(event);
  });
  ['pointerup', 'pointercancel'].forEach(function (name) {
    joystick.addEventListener(name, function (event) {
      if (joystick.hasPointerCapture(event.pointerId)) joystick.releasePointerCapture(event.pointerId);
      stop();
    });
  });
  document.querySelectorAll('.drive-button').forEach(function (button) {
    button.addEventListener('pointerdown', function (event) {
      event.preventDefault();
      button.setPointerCapture(event.pointerId);
      holdButton(button.dataset.action);
    });
    ['pointerup', 'pointercancel'].forEach(function (name) { button.addEventListener(name, stop); });
  });
  speedInput.addEventListener('input', function () {
    speedValue.textContent = speedInput.value;
    send({ type: 'speed', xy: currentSpeed(), z: currentSpeed() });
    if (active && lastCommand && lastCommand.type === 'button') lastCommand.speed = currentSpeed();
    repeatCommand();
  });
  connectButton.addEventListener('click', connect);
  document.getElementById('refreshCamera').addEventListener('click', function () {
    camera.src = '/camera.mjpeg?t=' + Date.now();
  });
  window.addEventListener('beforeunload', function () {
    manualClose = true;
    stop();
    if (socket) socket.close();
  });

  speedValue.textContent = speedInput.value;
  startRepeat();
  connect();
}());
