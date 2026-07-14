const host = document.querySelector('#host'), port = document.querySelector('#port'), state = document.querySelector('#state');
const speed = document.querySelector('#speed'), speedValue = document.querySelector('#speedValue'), joystick = document.querySelector('#joystick'), knob = document.querySelector('#knob');
let socket = null, pointerId = null;
host.value = location.hostname || '10.71.253.19';
speed.addEventListener('input', () => speedValue.value = speed.value);
function setState(text, ok) { state.textContent = text; state.className = `pill ${ok ? 'online' : 'offline'}`; }
function send(message) { if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message)); }
function connect() {
  if (socket) socket.close();
  const url = `ws://${host.value.trim()}:${Number(port.value || 8081)}/ws`;
  setState('连接中', false); socket = new WebSocket(url);
  socket.onopen = () => { setState('已连接', true); send({type:'speed', xy:Number(speed.value), z:Number(speed.value)}); };
  socket.onclose = () => { setState('已断开', false); stop(); };
  socket.onerror = () => setState('连接错误', false);
  socket.onmessage = event => { try { const m = JSON.parse(event.data); if (m.backend === false) setState('小车 TCP 未连接', false); else setState(m.state || '已连接', true); } catch (_) {} };
}
document.querySelector('#connect').onclick = connect; document.querySelector('#stop').onclick = stop;
document.querySelectorAll('[data-direction]').forEach(button => { const start = e => { e.preventDefault(); send({type:'direction', value:Number(button.dataset.direction)}); }; const end = e => { e.preventDefault(); stop(); }; button.addEventListener('pointerdown', start); button.addEventListener('pointerup', end); button.addEventListener('pointercancel', end); button.addEventListener('pointerleave', end); });
function stop() { send({type:'stop'}); resetKnob(); } function resetKnob() { knob.style.left = '37.5%'; knob.style.top = '37.5%'; }
function move(event) { const r = joystick.getBoundingClientRect(), cx = r.width/2, cy = r.height/2; let dx = event.clientX-r.left-cx, dy = event.clientY-r.top-cy; const max=r.width*.38, distance=Math.hypot(dx,dy); if(distance>max){dx*=max/distance;dy*=max/distance;} knob.style.left=`${(cx+dx-r.width*.125)/r.width*100}%`; knob.style.top=`${(cy+dy-r.height*.125)/r.height*100}%`; send({type:'joystick',x:Math.round(dx/max*100*Number(speed.value)/100),y:Math.round(-dy/max*100*Number(speed.value)/100)}); }
joystick.addEventListener('pointerdown', e => { pointerId=e.pointerId; joystick.setPointerCapture(pointerId); move(e); }); joystick.addEventListener('pointermove', e => { if(e.pointerId===pointerId) move(e); }); joystick.addEventListener('pointerup', e => { if(e.pointerId===pointerId){pointerId=null;stop();} }); joystick.addEventListener('pointercancel', () => { pointerId=null; stop(); });
async function refreshAi(){ document.querySelector('#aiImage').src=`/artifacts/yolo_result.jpg?t=${Date.now()}`; try{const response=await fetch(`/api/yolo/latest?t=${Date.now()}`);document.querySelector('#aiText').textContent=JSON.stringify(await response.json(),null,2);}catch(e){document.querySelector('#aiText').textContent='AI 结果暂不可用';} }
document.querySelector('#refreshAi').onclick=refreshAi; setInterval(() => send({type:'heartbeat'}), 5000);
