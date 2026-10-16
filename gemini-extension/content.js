/**
 * Gemini IDE Remote Bridge - Content Script for gemini.google.com
 * Automatically intercepts IDE tool calls from Gemini and executes them on your local machine.
 */

(function () {
  'use strict';

  // Config with defaults
  const config = {
    gatewayUrl: 'https://vscode-antigravity-mcp.vercel.app',
    apiKey: 'D4_PROJECT_MCP_SERVER',
    autoRun: true,
    activeProject: null,
    connected: false
  };

  const executedActionHashes = new Set();
  let badgeEl = null;
  let panelEl = null;

  // Load user overrides from storage
  if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(['gatewayUrl', 'apiKey', 'autoRun'], (items) => {
      if (items.gatewayUrl) config.gatewayUrl = items.gatewayUrl.replace(/\/+$/, '');
      if (items.apiKey) config.apiKey = items.apiKey;
      if (typeof items.autoRun === 'boolean') config.autoRun = items.autoRun;
      checkConnection();
    });
  }

  // --- UI Injection ---
  function initUI() {
    if (document.getElementById('gemini-ide-badge')) return;

    // Floating Badge
    badgeEl = document.createElement('div');
    badgeEl.id = 'gemini-ide-badge';
    badgeEl.innerHTML = `
      <div class="gemini-ide-dot" id="gemini-dot"></div>
      <span id="gemini-badge-text">IDE Bridge: Connecting...</span>
    `;
    badgeEl.addEventListener('click', togglePanel);
    document.body.appendChild(badgeEl);

    // Control Panel
    panelEl = document.createElement('div');
    panelEl.id = 'gemini-ide-panel';
    panelEl.innerHTML = `
      <div class="gemini-panel-header">
        <span>⚡ IDE Remote Bridge</span>
        <span style="cursor:pointer; opacity:0.6;" id="gemini-panel-close">✕</span>
      </div>
      <div class="gemini-panel-row">
        <span>Status:</span>
        <span id="gemini-panel-status" class="gemini-panel-badge">Checking...</span>
      </div>
      <div class="gemini-panel-row">
        <span>Active Project:</span>
        <span id="gemini-panel-project" class="gemini-panel-badge">None</span>
      </div>
      <div class="gemini-panel-row">
        <span>Auto-run Actions:</span>
        <label style="cursor:pointer; display:flex; align-items:center; gap:4px;">
          <input type="checkbox" id="gemini-autorun-toggle" ${config.autoRun ? 'checked' : ''}>
          <span style="font-size:11px;">Enabled</span>
        </label>
      </div>
      <div class="gemini-panel-row">
        <span>Gateway:</span>
        <span class="gemini-panel-badge" style="max-width:160px; overflow:hidden; text-overflow:ellipsis;">${config.gatewayUrl.replace('https://', '')}</span>
      </div>
      <button class="gemini-btn-primary" id="gemini-refresh-btn">🔄 Refresh Connection</button>
      <button class="gemini-btn-primary" id="gemini-copy-prompt-btn" style="background:rgba(255,255,255,0.08); margin-top:6px;">📋 Copy Gem Prompt</button>
    `;
    document.body.appendChild(panelEl);

    document.getElementById('gemini-panel-close').addEventListener('click', () => {
      panelEl.classList.remove('visible');
    });

    document.getElementById('gemini-autorun-toggle').addEventListener('change', (e) => {
      config.autoRun = e.target.checked;
      if (typeof chrome !== 'undefined' && chrome.storage) {
        chrome.storage.local.set({ autoRun: config.autoRun });
      }
    });

    document.getElementById('gemini-refresh-btn').addEventListener('click', () => {
      checkConnection();
    });

    document.getElementById('gemini-copy-prompt-btn').addEventListener('click', copyGemPrompt);

    checkConnection();
  }

  function togglePanel() {
    if (!panelEl) return;
    panelEl.classList.toggle('visible');
  }

  // --- Connection Check ---
  async function checkConnection() {
    const dot = document.getElementById('gemini-dot');
    const badgeText = document.getElementById('gemini-badge-text');
    const panelStatus = document.getElementById('gemini-panel-status');
    const panelProject = document.getElementById('gemini-panel-project');

    try {
      const resp = await fetch(`${config.gatewayUrl}/api/action/get_active_project`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${config.apiKey}`
        }
      });

      if (resp.ok) {
        const data = await resp.json();
        config.connected = true;
        config.activeProject = data.active_project || data.project || 'Default Root';

        if (dot) dot.className = 'gemini-ide-dot';
        if (badgeText) badgeText.innerText = `IDE: ${config.activeProject}`;
        if (panelStatus) {
          panelStatus.innerText = 'Connected';
          panelStatus.style.color = '#34a853';
        }
        if (panelProject) panelProject.innerText = config.activeProject;
        return;
      }
    } catch (e) {
      // Failed to reach gateway
    }

    config.connected = false;
    if (dot) dot.className = 'gemini-ide-dot offline';
    if (badgeText) badgeText.innerText = 'IDE Bridge: Offline';
    if (panelStatus) {
      panelStatus.innerText = 'Offline';
      panelStatus.style.color = '#ea4335';
    }
  }

  // --- Copy Gem Prompt ---
  function copyGemPrompt() {
    const prompt = `You are an expert AI software engineer with direct access to my local IDE and project files via the Universal IDE Remote Bridge.

Whenever you need to inspect files, edit code, run terminal commands, or check projects, ALWAYS output the action in a single block using the exact syntax:

\`\`\`ide_action
{
  "tool": "<tool_name>",
  "params": { ... }
}
\`\`\`

Available Tools:
1. list_projects: {} -> Lists all available project folders in the workspace.
2. set_active_project: {"project_name": "<folder_name>"} -> Switches the active project context.
3. get_active_project: {} -> Gets the current project name and path.
4. read_workspace_file: {"path": "<file_path>", "max_lines": 500, "start_line": 1} -> Reads file content.
5. write_workspace_file: {"path": "<file_path>", "content": "<text>"} -> Creates or replaces a file.
6. edit_workspace_file: {"path": "<file_path>", "old_str": "<text>", "new_str": "<replacement>"} -> Performs precise code replacement.
7. list_workspace_directory: {"path": ".", "max_depth": 2} -> Lists files in a folder.
8. search_workspace_files: {"query": "<text>", "path": "."} -> Grep search across files.
9. run_terminal_command: {"command": "<command>"} -> Runs a command in the terminal.
10. run_git_command: {"subcommand": "<status/diff/log>"} -> Runs a git command.

The browser extension will automatically execute your action on my machine and post the result back to you. When you see the result, continue your answer!`;

    navigator.clipboard.writeText(prompt).then(() => {
      alert('✅ Gem Instructions copied to clipboard! Paste this into your Gem Instructions on gemini.google.com/gems.');
    });
  }

  // --- Action Parsing & Execution ---
  function findActionsInElement(element) {
    if (!element) return [];
    const actions = [];

    // Search code blocks
    const codeBlocks = element.querySelectorAll('pre, code');
    for (const block of codeBlocks) {
      const text = block.textContent.trim();
      const action = parseActionText(text, block);
      if (action) actions.push(action);
    }

    return actions;
  }

  function parseActionText(text, domNode) {
    // 1. Check for ```ide_action ... ```
    if (text.includes('"tool"') || text.includes('"action"')) {
      try {
        // Find JSON block
        const jsonMatch = text.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[0]);
          const tool = parsed.tool || parsed.action;
          const params = parsed.params || parsed.parameters || parsed.args || {};
          if (tool && typeof tool === 'string') {
            return { tool, params, domNode, raw: text };
          }
        }
      } catch (e) {
        // invalid JSON, ignore
      }
    }

    // 2. Check for [ACTION: tool_name {...}]
    const actionTagMatch = text.match(/\[ACTION:\s*([a-zA-Z0-9_-]+)\s*(\{[\s\S]*?\})\]/);
    if (actionTagMatch) {
      try {
        const tool = actionTagMatch[1];
        const params = JSON.parse(actionTagMatch[2]);
        return { tool, params, domNode, raw: text };
      } catch (e) {}
    }

    return null;
  }

  async function executeAction(action) {
    const actionHash = `${action.tool}-${JSON.stringify(action.params)}`;
    if (executedActionHashes.has(actionHash)) return;
    executedActionHashes.add(actionHash);

    const dot = document.getElementById('gemini-dot');
    const badgeText = document.getElementById('gemini-badge-text');

    if (dot) dot.className = 'gemini-ide-dot executing';
    if (badgeText) badgeText.innerText = `⚡ Running: ${action.tool}...`;

    // Render visual execution banner on the code block
    if (action.domNode) {
      const card = document.createElement('div');
      card.className = 'gemini-action-card';
      card.innerHTML = `
        <span>⚡ <b>Executing on local IDE:</b> <code>${action.tool}</code></span>
        <span style="color:#fbbc05; font-size:11px;">Running...</span>
      `;
      action.domNode.parentNode.insertBefore(card, action.domNode);
      action.card = card;
    }

    const t0 = performance.now();
    let result = null;
    let error = null;

    try {
      const resp = await fetch(`${config.gatewayUrl}/api/tools/${action.tool}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${config.apiKey}`
        },
        body: JSON.stringify(action.params)
      });

      const data = await resp.json();
      result = data.result || data;
    } catch (e) {
      error = e.message || String(e);
    }

    const durationMs = Math.round(performance.now() - t0);

    if (dot) dot.className = 'gemini-ide-dot';
    if (badgeText) badgeText.innerText = `IDE: ${config.activeProject || 'Connected'}`;

    if (action.card) {
      action.card.className = 'gemini-action-card completed';
      action.card.innerHTML = `
        <span>✅ <b>Completed:</b> <code>${action.tool}</code> in ${durationMs}ms</span>
        <span style="color:#34a853; font-size:11px;">Delivered to Gemini</span>
      `;
    }

    // Feed result back into Gemini chat
    postResultToGemini(action.tool, result, error);
  }

  // --- Input & Send Automation ---
  function postResultToGemini(toolName, result, error) {
    const resultPayload = error ? { error } : result;
    const formattedResult = `[IDE Tool Result for ${toolName}]:\n\`\`\`json\n${JSON.stringify(resultPayload, null, 2)}\n\`\`\``;

    // Look for Gemini input elements
    const inputEl = document.querySelector('rich-textarea div[contenteditable="true"]') ||
                    document.querySelector('div.ql-editor[contenteditable="true"]') ||
                    document.querySelector('div[contenteditable="true"][role="textbox"]') ||
                    document.querySelector('div[contenteditable="true"]') ||
                    document.querySelector('textarea');

    if (!inputEl) {
      console.warn('[Gemini IDE Bridge] Could not locate chat input textarea.');
      return;
    }

    inputEl.focus();

    if (inputEl.tagName.toLowerCase() === 'textarea') {
      inputEl.value = formattedResult;
      inputEl.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      inputEl.innerText = formattedResult;
      inputEl.dispatchEvent(new InputEvent('input', { bubbles: true }));
    }

    // Trigger Send
    setTimeout(() => {
      const sendButton = document.querySelector('button[aria-label*="Send message"]') ||
                         document.querySelector('button[aria-label*="Send"]') ||
                         document.querySelector('button.send-button') ||
                         document.querySelector('button[aria-label*="Submit"]') ||
                         document.querySelector('button:has(mat-icon[fonticon="send"])');

      if (sendButton && !sendButton.disabled && sendButton.getAttribute('aria-disabled') !== 'true') {
        sendButton.click();
      } else {
        // Fallback: Dispatch Enter key
        inputEl.dispatchEvent(new KeyboardEvent('keydown', {
          key: 'Enter',
          code: 'Enter',
          keyCode: 13,
          which: 13,
          bubbles: true
        }));
      }
    }, 350);
  }

  // --- DOM Observer for Streaming Responses ---
  let scanTimeout = null;

  function observeChat() {
    const observer = new MutationObserver(() => {
      clearTimeout(scanTimeout);
      scanTimeout = setTimeout(scanForActions, 500);
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }

  function scanForActions() {
    // Only search recent responses
    const responseContainers = document.querySelectorAll('model-response, message-content, div.markdown, div.response-container');
    const targetContainers = responseContainers.length > 0
      ? Array.from(responseContainers).slice(-3)
      : [document.body];

    for (const container of targetContainers) {
      const actions = findActionsInElement(container);
      for (const action of actions) {
        const hash = `${action.tool}-${JSON.stringify(action.params)}`;
        if (!executedActionHashes.has(hash)) {
          if (config.autoRun) {
            executeAction(action);
          } else {
            renderManualApproveButton(action);
          }
        }
      }
    }
  }

  function renderManualApproveButton(action) {
    const hash = `${action.tool}-${JSON.stringify(action.params)}`;
    if (executedActionHashes.has(hash)) return;

    if (action.domNode && !action.domNode.dataset.hasApproveBtn) {
      action.domNode.dataset.hasApproveBtn = "true";
      const card = document.createElement('div');
      card.className = 'gemini-action-card';
      card.innerHTML = `
        <span>⚡ <b>Action Ready:</b> <code>${action.tool}</code></span>
        <button class="gemini-action-btn" id="run-${Math.random().toString(36).substring(7)}">▶ Run Action</button>
      `;
      action.domNode.parentNode.insertBefore(card, action.domNode);
      card.querySelector('button').addEventListener('click', () => {
        executeAction(action);
        card.remove();
      });
    }
  }

  // --- Bootstrap ---
  function start() {
    initUI();
    observeChat();
    setInterval(checkConnection, 30000); // Heartbeat check every 30s
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }

})();
