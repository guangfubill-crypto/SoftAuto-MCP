chrome.runtime.sendMessage({ type: "softauto-status" }, response => {
  const node = document.getElementById("status");
  if (chrome.runtime.lastError || !response) {
    node.textContent = "扩展后台未就绪";
    return;
  }
  node.textContent = response.connected ? "● 已连接 SoftAuto" : "○ 等待 SoftAuto 启动";
  node.classList.toggle("ok", Boolean(response.connected));
});
