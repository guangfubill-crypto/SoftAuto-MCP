const BRIDGE_URL = "ws://127.0.0.1:17856";
let socket = null;
let reconnectTimer = null;
let keepAliveTimer = null;
let pendingPick = null;

function extensionInfo() {
  const manifest = chrome.runtime.getManifest();
  return { id: chrome.runtime.id, name: manifest.name, version: manifest.version };
}

function sendBridge(message) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(message));
  return true;
}

function connectBridge() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
  try {
    socket = new WebSocket(BRIDGE_URL);
    socket.onopen = () => {
      sendBridge({ type: "hello", extension: extensionInfo() });
      clearInterval(keepAliveTimer);
      keepAliveTimer = setInterval(() => sendBridge({ type: "hello", extension: extensionInfo() }), 20000);
    };
    socket.onmessage = event => {
      let message;
      try { message = JSON.parse(event.data); } catch (_) { return; }
      if (message.type === "command") handleCommand(message);
    };
    socket.onclose = scheduleReconnect;
    socket.onerror = () => socket && socket.close();
  } catch (_) { scheduleReconnect(); }
}

function scheduleReconnect() {
  clearInterval(keepAliveTimer);
  clearTimeout(reconnectTimer);
  socket = null;
  reconnectTimer = setTimeout(connectBridge, 1500);
}

async function activeTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tab = tabs[0];
  if (!tab || !tab.id || !/^https?:/i.test(tab.url || "")) {
    throw new Error("请先打开一个 http/https 网页并保持该标签页激活");
  }
  return tab;
}

async function allFrames(tabId) {
  try {
    const frames = await chrome.webNavigation.getAllFrames({ tabId });
    return frames || [{ frameId: 0, url: "" }];
  } catch (_) { return [{ frameId: 0, url: "" }]; }
}

async function sendToFrames(tabId, message, stopOnSuccess) {
  const frames = await allFrames(tabId);
  const desiredUrl = message.payload?.locator?.frame?.url;
  frames.sort((a, b) => Number(b.url === desiredUrl) - Number(a.url === desiredUrl));
  let lastError = null;
  const successes = [];
  for (const frame of frames) {
    try {
      const response = await chrome.tabs.sendMessage(tabId, message, { frameId: frame.frameId });
      if (response && response.ok) {
        successes.push(response);
        if (stopOnSuccess) return response;
      } else if (response && response.error) lastError = response.error;
    } catch (error) { lastError = error.message; }
  }
  if (successes.length) return successes[0];
  throw new Error(lastError || "网页连接器未能进入当前页面，请刷新网页后重试");
}

async function handleCommand(message) {
  const requestId = message.request_id;
  try {
    const tab = await activeTab();
    if (message.command === "start_pick") {
      if (pendingPick) throw new Error("已有网页元素拾取正在进行");
      pendingPick = { requestId, tabId: tab.id };
      await sendToFrames(tab.id, {
        source: "softauto-extension", command: "start_pick", requestId,
        payload: message.payload || {}
      }, false);
      return;
    }
    const response = await sendToFrames(tab.id, {
      source: "softauto-extension", command: message.command, requestId,
      payload: message.payload || {}
    }, true);
    sendBridge({ type: "result", request_id: requestId, ok: true, result: response.result });
  } catch (error) {
    if (message.command === "start_pick") pendingPick = null;
    sendBridge({ type: "result", request_id: requestId, ok: false, error: error.message || String(error) });
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "softauto-pick-result" && pendingPick) {
    const current = pendingPick;
    if (sender.tab && sender.tab.id !== current.tabId) return;
    pendingPick = null;
    sendBridge({ type: "result", request_id: current.requestId, ok: Boolean(message.ok), result: message.result, error: message.error });
    sendToFrames(current.tabId, { source: "softauto-extension", command: "stop_pick" }, false).catch(() => {});
    sendResponse({ ok: true });
    return true;
  }
  if (message && message.type === "softauto-status") {
    connectBridge();
    sendResponse({ connected: Boolean(socket && socket.readyState === WebSocket.OPEN), extension: extensionInfo() });
    return true;
  }
  if (message && message.type === "softauto-content-ready") {
    connectBridge();
    sendResponse({ ok: true });
    return true;
  }
  return false;
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ installedAt: new Date().toISOString() });
  connectBridge();
});
chrome.runtime.onStartup.addListener(connectBridge);
connectBridge();
