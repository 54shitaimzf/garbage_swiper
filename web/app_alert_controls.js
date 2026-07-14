(function () {
  'use strict';
  const speedPanel = document.querySelector('.speed-panel');
  if (!speedPanel || document.getElementById('manualAlert')) return;

  const panel = document.createElement('section');
  panel.className = 'alert-panel';
  panel.innerHTML = '<div class="alert-panel-head"><div><h3>声音告警</h3><p id="alertHint" class="hint">正在读取告警配置…</p></div><span id="alertState" class="telemetry-chip alert-state">就绪</span></div>' +
    '<button id="manualAlert" class="alert-button" type="button"><span class="alert-icon" aria-hidden="true">♬</span><span>手动鸣笛测试</span></button>';
  speedPanel.parentNode.appendChild(panel);

  const button = document.getElementById('manualAlert');
  const state = document.getElementById('alertState');
  const hint = document.getElementById('alertHint');
  let resetTimer = null;

  function setState(text, kind) {
    state.textContent = text;
    state.classList.remove('is-ok', 'is-error', 'is-busy');
    if (kind) state.classList.add(kind);
  }

  async function refreshAlertStatus() {
    try {
      const response = await fetch('/api/alert/status?t=' + Date.now(), { cache: 'no-store' });
      const data = await response.json();
      if (!data.enabled || !data.player) {
        hint.textContent = '自动告警未启用或未检测到扬声器';
        setState('不可用', 'is-error');
        return;
      }
      const threshold = Number(data.default_confidence || 0.8).toFixed(2);
      hint.textContent = '自动告警：置信度 ≥ ' + threshold + ' · 连续 ' + (data.confirm_frames || 2) + ' 帧';
      setState('扬声器就绪', 'is-ok');
    } catch (_) {
      hint.textContent = '告警配置暂不可读取，可直接尝试测试';
      setState('待测试');
    }
  }

  async function testAlert() {
    if (button.disabled) return;
    button.disabled = true;
    button.classList.add('is-playing');
    setState('播放中', 'is-busy');
    hint.textContent = '正在发送短音到小车扬声器…';
    try {
      const response = await fetch('/api/alert/test?class=drink_green&t=' + Date.now(), { cache: 'no-store' });
      const data = await response.json();
      if (data.ok) {
        setState('已发送', 'is-ok');
        hint.textContent = '测试音已发送，可按需再次测试';
      } else {
        setState('失败', 'is-error');
        hint.textContent = '未找到可用扬声器';
      }
    } catch (_) {
      setState('失败', 'is-error');
      hint.textContent = '告警接口未连接，请先保持小车在线';
    } finally {
      clearTimeout(resetTimer);
      resetTimer = setTimeout(function () {
        button.disabled = false;
        button.classList.remove('is-playing');
      }, 1200);
    }
  }

  button.addEventListener('click', testAlert);
  refreshAlertStatus();
}());
