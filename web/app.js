const host = document.querySelector('#host');
const port = document.querySelector('#port');
const state = document.querySelector('#state');
const speed = document.querySelector('#speed');
const speedValue = document.querySelector('#speedValue');
const joystick = document.querySelector('#joystick');
const knob = document.querySelector('#knob');
let socket = null, pointerId = null;
host.value = location.hostname || '10.71.253.19';
speed.addEventListener('input', () => speedValue.value = speed.value);
function setState(text, ok=false) { state.textContent = text; state.className = `pill ${ok ? 'online' : 'offline'}`; }
function send(message) { if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message)); }
function connect() {
  if (socket) socket.close();
  const url = `ws://${host.value.trim()}:${Number(port.value || 8080)}/ws`;
  setState('连接中'); socket = new WebSocket(url);
  socket.onopen = () => { setState('已连接', true); send({type:'speed', xy:Number(speed.value), z:Number(speed.value)}); };
  socket.onclose = () => { setState('已断开'); stop(); };
  socket.onerror = () => setState('连接错误');
  socket.onmessage = event => { try { const m = JSON.parse(event.data); if (m.state) setState(m.state, m.state === '已连接'); } catch (_) {} };
}
document.querySelector('#connect').onclick = connect;
document.querySelector('#stop').onclick = stop;
document.querySelectorAll('[data-direction]').forEach(button => {
  const start = event => { event.preventDefault(); send({type:'direction', value:Number(button.dataset.direction)}); };
  const end = event => { event.preventDefault(); stop(); };
  button.addEventListener('pointerdown', start); button.addEventListener('pointerup', end); button.addEventListener('pointercancel', end); button.addEventListener('pointerleave', end);
});
function stop() { send({type:'stop'}); resetKnob(); }
function resetKnob() { knob.style.left = '37.5%'; knob.style.top = '37.5%'; }
function move(event) {
  const r = joystick.getBoundingClientRect(), cx = r.width/2, cy = r.height/2;
  let dx = event.clientX - r.left - cx, dy = event.clientY - r.top - cy;
  const max = r.width * .38, distance = Math.hypot(dx,dy);
  if (distance > max) { dx *= max/distance; dy *= max/distance; }
  knob.style.left = `${(cx+dx-r.width*.125)/r.width*100}%`; knob.style.top = `${(cy+dy-r.height*.125)/r.height*100}%`;
  send({type:'joystick', x:Math.round(dx/max*100*Number(speed.value)/100), y:Math.round(-dy/max*100*Number(speed.value)/100)});
}
joystick.addEventListener('pointerdown', event => { pointerId = event.pointerId; joystick.setPointerCapture(pointerId); move(event); });
joystick.addEventListener('pointermove', event => { if (event.pointerId === pointerId) move(event); });
joystick.addEventListener('pointerup', event => { if (event.pointerId === pointerId) { pointerId=null; stop(); } });
joystick.addEventListener('pointercancel', () => { pointerId=null; stop(); });
async function refreshAi() {
  document.querySelector('#aiImage').src = `/artifacts/yolo_result.jpg?t=${Date.now()}`;
  try { const response = await fetch(`/api/yolo/latest?t=${Date.now()}`); document.querySelector('#aiText').textContent = JSON.stringify(await response.json(), null, 2); } catch (e) { document.querySelector('#aiText').textContent = 'AI 结果暂不可用'; }
}
document.querySelector('#refreshAi').onclick = refreshAi;
setInterval(() => send({type:'heartbeat'}), 5000);
