document.addEventListener('DOMContentLoaded', () => {
  const gatewayInput = document.getElementById('gateway-url');
  const apiKeyInput = document.getElementById('api-key');
  const autoRunCheckbox = document.getElementById('auto-run');
  const statusBadge = document.getElementById('status-badge');
  const activeProjSpan = document.getElementById('active-project');
  const saveBtn = document.getElementById('save-btn');

  // Load saved settings
  chrome.storage.local.get(['gatewayUrl', 'apiKey', 'autoRun'], (items) => {
    if (items.gatewayUrl) gatewayInput.value = items.gatewayUrl;
    if (items.apiKey) apiKeyInput.value = items.apiKey;
    if (typeof items.autoRun === 'boolean') autoRunCheckbox.checked = items.autoRun;
    testConnection();
  });

  async function testConnection() {
    const gateway = gatewayInput.value.trim().replace(/\/+$/, '');
    const key = apiKeyInput.value.trim();

    statusBadge.innerText = 'Checking...';
    statusBadge.className = 'badge';

    try {
      const resp = await fetch(`${gateway}/api/action/get_active_project`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${key}`
        }
      });

      if (resp.ok) {
        const data = await resp.json();
        statusBadge.innerText = 'Connected';
        statusBadge.className = 'badge green';
        activeProjSpan.innerText = data.active_project || data.project || 'Default Root';
        return;
      }
    } catch (e) {}

    statusBadge.innerText = 'Offline';
    statusBadge.className = 'badge red';
    activeProjSpan.innerText = 'Unreachable';
  }

  saveBtn.addEventListener('click', () => {
    const gatewayUrl = gatewayInput.value.trim().replace(/\/+$/, '');
    const apiKey = apiKeyInput.value.trim();
    const autoRun = autoRunCheckbox.checked;

    chrome.storage.local.set({ gatewayUrl, apiKey, autoRun }, () => {
      testConnection();
      saveBtn.innerText = '✅ Saved!';
      setTimeout(() => { saveBtn.innerText = 'Save & Test Connection'; }, 1500);
    });
  });
});
