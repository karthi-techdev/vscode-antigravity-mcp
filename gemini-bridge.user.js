// ==UserScript==
// @name         Gemini IDE Remote Bridge
// @namespace    https://vscode-antigravity-mcp.vercel.app/
// @version      1.0.0
// @description  Enables gemini.google.com to execute local IDE actions, read/edit workspace files, and run commands.
// @author       Universal IDE Bridge
// @match        https://gemini.google.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      vscode-antigravity-mcp.vercel.app
// @connect      localhost
// @run-at       document-end
// ==/UserScript==

(function () {
  'use strict';

  const config = {
    gatewayUrl: 'https://vscode-antigravity-mcp.vercel.app',
    apiKey: 'D4_PROJECT_MCP_SERVER',
    autoRun: true,
    activeProject: null,
    connected: false
  };

  const executedHashes = new Set();
  let badgeEl, panelEl;

  // Add styles
  const style = document.createElement('style');
  style.textContent = `
    #gemini-ide-badge {
      position: fixed; bottom: 24px; right: 24px; z-index: 999999;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 13px; display: flex; align-items: center; gap: 8px;
      padding: 8px 14px; background: rgba(18, 19, 22, 0.88);
      backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 9999px; color: #e3e3e3; box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      cursor: pointer; user-select: none;
    }
    .gemini-ide-dot { width: 9px; height: 9px; border-radius: 50%; background: #34a853; box-shadow: 0 0 10px #34a853; }
    .gemini-ide-dot.offline { background: #ea4335; box-shadow: 0 0 10px #ea4335; }
    .gemini-ide-dot.executing { background: #fbbc05; box-shadow: 0 0 10px #fbbc05; }
    .gemini-action-card {
      margin: 8px 0; padding: 10px 14px; background: rgba(30, 31, 36, 0.9);
      border: 1px solid rgba(66, 133, 244, 0.4); border-radius: 10px; font-size: 12px;
      display: flex; align-items: center; justify-content: space-between;
    }
    .gemini-action-card.completed { border-color: rgba(52, 168, 83, 0.5); }
  `;
  document.head.appendChild(style);

  function initUI() {
    if (document.getElementById('gemini-ide-badge')) return;
    badgeEl = document.createElement('div');
    badgeEl.id = 'gemini-ide-badge';
    badgeEl.innerHTML = `
      <div class="gemini-ide-dot" id="gemini-dot"></div>
      <span id="gemini-badge-text">IDE Bridge: Connecting...</span>
    `;
    badgeEl.addEventListener('click', checkConnection);
    document.body.appendChild(badgeEl);
    checkConnection();
  }

  function checkConnection() {
    GM_xmlhttpRequest({
      method: 'POST',
      url: `${config.gatewayUrl}/api/action/get_active_project`,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.apiKey}`
      },
      data: JSON.stringify({}),
      onload: function (res) {
        const dot = document.getElementById('gemini-dot');
        const text = document.getElementById('gemini-badge-text');
        if (res.status === 200) {
          try {
            const data = JSON.parse(res.responseText);
            config.activeProject = data.active_project || data.project || 'Default Root';
            if (dot) dot.className = 'gemini-ide-dot';
            if (text) text.innerText = `IDE: ${config.activeProject}`;
          } catch(e) {}
        } else {
          if (dot) dot.className = 'gemini-ide-dot offline';
          if (text) text.innerText = 'IDE: Offline';
        }
      },
      onerror: function () {
        const dot = document.getElementById('gemini-dot');
        const text = document.getElementById('gemini-badge-text');
        if (dot) dot.className = 'gemini-ide-dot offline';
        if (text) text.innerText = 'IDE: Offline';
      }
    });
  }

  function executeAction(tool, params, domNode) {
    const hash = `${tool}-${JSON.stringify(params)}`;
    if (executedHashes.has(hash)) return;
    executedHashes.add(hash);

    const dot = document.getElementById('gemini-dot');
    const text = document.getElementById('gemini-badge-text');
    if (dot) dot.className = 'gemini-ide-dot executing';
    if (text) text.innerText = `⚡ Running: ${tool}...`;

    let card = null;
    if (domNode) {
      card = document.createElement('div');
      card.className = 'gemini-action-card';
      card.innerHTML = `<span>⚡ <b>Executing on local IDE:</b> <code>${tool}</code></span><span style="color:#fbbc05;">Running...</span>`;
      domNode.parentNode.insertBefore(card, domNode);
    }

    const t0 = performance.now();

    GM_xmlhttpRequest({
      method: 'POST',
      url: `${config.gatewayUrl}/api/tools/${tool}`,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.apiKey}`
      },
      data: JSON.stringify(params),
      onload: function (res) {
        const duration = Math.round(performance.now() - t0);
        let result = res.responseText;
        try {
          const json = JSON.parse(res.responseText);
          result = json.result || json;
        } catch(e) {}

        if (dot) dot.className = 'gemini-ide-dot';
        if (text) text.innerText = `IDE: ${config.activeProject || 'Connected'}`;

        if (card) {
          card.className = 'gemini-action-card completed';
          card.innerHTML = `<span>✅ <b>Completed:</b> <code>${tool}</code> in ${duration}ms</span><span style="color:#34a853;">Delivered to Gemini</span>`;
        }

        postResult(tool, result);
      },
      onerror: function (err) {
        if (dot) dot.className = 'gemini-ide-dot';
        if (card) {
          card.className = 'gemini-action-card';
          card.innerHTML = `<span>❌ <b>Failed:</b> <code>${tool}</code></span><span style="color:#ea4335;">Error</span>`;
        }
        postResult(tool, { error: 'Request to IDE Gateway failed' });
      }
    });
  }

  function postResult(tool, result) {
    const formatted = `[IDE Tool Result for ${tool}]:\n\`\`\`json\n${JSON.stringify(result, null, 2)}\n\`\`\``;
    const inputEl = document.querySelector('rich-textarea div[contenteditable="true"]') ||
                    document.querySelector('div.ql-editor[contenteditable="true"]') ||
                    document.querySelector('div[contenteditable="true"]') ||
                    document.querySelector('textarea');

    if (!inputEl) return;
    inputEl.focus();

    if (inputEl.tagName.toLowerCase() === 'textarea') {
      inputEl.value = formatted;
      inputEl.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      inputEl.innerText = formatted;
      inputEl.dispatchEvent(new InputEvent('input', { bubbles: true }));
    }

    setTimeout(() => {
      const sendBtn = document.querySelector('button[aria-label*="Send"]') ||
                      document.querySelector('button.send-button') ||
                      document.querySelector('button:has(mat-icon[fonticon="send"])');
      if (sendBtn && !sendBtn.disabled && sendBtn.getAttribute('aria-disabled') !== 'true') {
        sendBtn.click();
      } else {
        inputEl.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
      }
    }, 350);
  }

  function scanDOM() {
    const codeBlocks = document.querySelectorAll('pre, code');
    for (const block of codeBlocks) {
      const text = block.textContent.trim();
      if (text.includes('"tool"') || text.includes('"action"')) {
        try {
          const jsonMatch = text.match(/\{[\s\S]*\}/);
          if (jsonMatch) {
            const parsed = JSON.parse(jsonMatch[0]);
            const tool = parsed.tool || parsed.action;
            const params = parsed.params || parsed.parameters || parsed.args || {};
            if (tool && typeof tool === 'string') {
              executeAction(tool, params, block);
            }
          }
        } catch(e) {}
      }
    }
  }

  setInterval(scanDOM, 800);
  setInterval(checkConnection, 30000);
  window.addEventListener('load', initUI);
  setTimeout(initUI, 1500);
})();
