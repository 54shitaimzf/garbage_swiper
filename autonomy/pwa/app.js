(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const state = { maps: [], routes: [], status: null, mapId: null, routeId: null };
  const labels = { idle: '空闲', ready: '已就绪', running: '执行中', stopped: '已停止', succeeded: '已完成', error: '错误' };

  async function request(path, options = {}) {
    const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
    const payload = await response.json();
    if (!response.ok || payload.ok === false) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  function setError(message = '') {
    $('errorText').textContent = message;
    $('errorText').hidden = !message;
  }

  function renderMaps() {
    $('mapHint').textContent = `${state.maps.length} 个白名单地图`;
    $('mapList').innerHTML = state.maps.map((map) => {
      const selected = map.id === state.mapId ? ' selected' : '';
      const availability = map.available ? '文件已就绪' : '车端路径待检查';
      return `<button class="choice${selected}" data-map="${map.id}"><strong>${map.name}</strong><small>${map.description} · ${availability}</small></button>`;
    }).join('');
    document.querySelectorAll('[data-map]').forEach((button) => {
      button.addEventListener('click', async () => {
        try {
          const result = await request('/api/mission/map', { method: 'POST', body: JSON.stringify({ map_id: button.dataset.map }) });
          state.mapId = result.selected_map;
          render();
        } catch (error) { setError(error.message); }
      });
    });
  }

  function renderRoutes() {
    $('routeHint').textContent = `${state.routes.length} 条固定路线`;
    $('routeList').innerHTML = state.routes.map((route) => {
      const selected = route.id === state.routeId ? ' selected' : '';
      const disabled = route.enabled ? '' : ' disabled';
      return `<button class="choice${selected}${disabled}" data-route="${route.id}" ${route.enabled ? '' : 'disabled'}><strong>${route.name}</strong><small>${route.description} · ${route.waypoint_count} 个目标点</small></button>`;
    }).join('');
    document.querySelectorAll('[data-route]').forEach((button) => button.addEventListener('click', () => {
      state.routeId = button.dataset.route;
      render();
    }));
  }

  function renderStatus() {
    const current = state.status || {};
    const stateName = current.state || 'idle';
    const badge = $('stateBadge');
    badge.textContent = labels[stateName] || stateName;
    badge.className = `badge ${stateName === 'error' ? 'badge-danger' : stateName === 'running' ? 'badge-warn' : stateName === 'ready' || stateName === 'succeeded' ? 'badge-ok' : 'badge-neutral'}`;
    $('selectedMap').textContent = current.selected_map || state.mapId || '—';
    $('selectedRoute').textContent = current.selected_route || state.routeId || '—';
    $('adapterStatus').textContent = current.adapter ? `${current.adapter.mode} · ${current.adapter.available ? '可用' : '不可用'}` : '—';
    const active = stateName === 'ready' || stateName === 'running' || stateName === 'succeeded' || stateName === 'stopped';
    $('activateBtn').disabled = active;
    $('deactivateBtn').disabled = stateName === 'running';
    $('startBtn').disabled = stateName !== 'ready' || !state.routeId;
    $('stopBtn').disabled = stateName !== 'running';
    $('homeBtn').disabled = stateName !== 'ready';
    const mappingState = current.mapping?.state || 'idle';
    $('mappingStartBtn').disabled = mappingState === 'running' || stateName === 'running';
    $('mappingStopBtn').disabled = mappingState !== 'running';
    $('mappingSaveBtn').disabled = mappingState !== 'stopped';
    $('mappingStatus').textContent = mappingState === 'idle' ? '建图流程尚未启动' : `建图状态：${mappingState}`;
    const adapter = current.adapter || {};
    $('notice').textContent = adapter.mode === 'mock' ? '当前为模拟模式：所有按钮只验证 APP 与任务状态机，不会发送底盘指令。' : `ROS2 模式：${adapter.message || '请先检查传感器与导航状态。'}`;
    $('connectionBadge').textContent = '8082 已连接';
    $('connectionBadge').className = 'badge badge-ok';
  }

  function render() { renderMaps(); renderRoutes(); renderStatus(); }

  async function refresh() {
    try {
      const [maps, routes, status] = await Promise.all([request('/api/maps'), request('/api/routes'), request('/api/autonomy/status')]);
      state.maps = maps.maps || [];
      state.routes = routes.routes || [];
      state.status = status;
      state.mapId = status.selected_map || state.mapId;
      state.routeId = status.selected_route || state.routeId;
      setError(status.last_error || '');
      render();
    } catch (error) {
      $('connectionBadge').textContent = '连接失败';
      $('connectionBadge').className = 'badge badge-danger';
      setError(error.message);
    }
  }

  async function post(path, body = {}) {
    try { state.status = await request(path, { method: 'POST', body: JSON.stringify(body) }); setError(''); renderStatus(); }
    catch (error) { setError(error.message); await refresh(); }
  }

  $('activateBtn').addEventListener('click', () => post('/api/autonomy/activate'));
  $('deactivateBtn').addEventListener('click', () => post('/api/autonomy/deactivate'));
  $('startBtn').addEventListener('click', () => post('/api/mission/start', { route_id: state.routeId }));
  $('stopBtn').addEventListener('click', () => post('/api/mission/stop'));
  $('homeBtn').addEventListener('click', () => post('/api/mission/home'));
  $('mappingStartBtn').addEventListener('click', () => post('/api/mapping/start'));
  $('mappingStopBtn').addEventListener('click', () => post('/api/mapping/stop'));
  $('mappingSaveBtn').addEventListener('click', () => post('/api/mapping/save', { map_id: $('mappingName').value.trim() }));

  refresh();
  window.setInterval(refresh, 1500);
})();
