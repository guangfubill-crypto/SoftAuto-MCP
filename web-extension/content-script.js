(() => {
  if (window.__softAutoConnectorLoaded) return;
  window.__softAutoConnectorLoaded = true;

  let picking = false;
  let overlay = null;

  const esc = value => window.CSS && CSS.escape
    ? CSS.escape(String(value))
    : String(value).replace(/[^a-zA-Z0-9_-]/g, ch => `\\${ch}`);

  function ensureOverlay() {
    if (overlay && overlay.isConnected) return overlay;
    overlay = document.createElement("div");
    overlay.setAttribute("data-softauto-overlay", "true");
    Object.assign(overlay.style, {
      position: "fixed", zIndex: "2147483647", pointerEvents: "none",
      border: "2px solid #1677ff", background: "rgba(22,119,255,.14)",
      boxSizing: "border-box", display: "none"
    });
    document.documentElement.appendChild(overlay);
    return overlay;
  }

  function showHighlight(element, duration = 0) {
    if (!element || !(element instanceof Element)) return;
    const rect = element.getBoundingClientRect();
    const node = ensureOverlay();
    Object.assign(node.style, {
      display: "block", left: `${rect.left}px`, top: `${rect.top}px`,
      width: `${Math.max(1, rect.width)}px`, height: `${Math.max(1, rect.height)}px`
    });
    if (duration) setTimeout(() => { if (!picking && node) node.style.display = "none"; }, duration);
  }

  function hideHighlight() { if (overlay) overlay.style.display = "none"; }

  function uniqueCss(selector) {
    try { return document.querySelectorAll(selector).length === 1; } catch (_) { return false; }
  }

  function stableClasses(element) {
    return [...element.classList].filter(name =>
      name.length < 64 && !/^(active|focus|focused|hover|selected|disabled|ng-|css-)/i.test(name) &&
      !/[a-f0-9]{8,}/i.test(name)
    ).slice(0, 3);
  }

  function cssPath(element) {
    const parts = [];
    let node = element;
    while (node && node.nodeType === Node.ELEMENT_NODE && parts.length < 7) {
      let part = node.tagName.toLowerCase();
      if (node.id) {
        part += `#${esc(node.id)}`;
        parts.unshift(part);
        break;
      }
      const classes = stableClasses(node);
      if (classes.length) part += classes.map(name => `.${esc(name)}`).join("");
      const parent = node.parentElement;
      if (parent) {
        const siblings = [...parent.children].filter(child => child.tagName === node.tagName);
        if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      if (uniqueCss(parts.join(" > "))) break;
      node = parent;
    }
    return parts.join(" > ");
  }

  function selectorsFor(element) {
    const selectors = [];
    const add = (kind, value, score) => {
      if (value && !selectors.some(item => item.kind === kind && item.value === value)) {
        selectors.push({ kind, value, score, enabled: true });
      }
    };
    if (element.id) add("css", `#${esc(element.id)}`, 100);
    for (const attr of ["data-testid", "data-test", "data-qa", "name", "aria-label", "placeholder"]) {
      const value = element.getAttribute(attr);
      if (!value) continue;
      const selector = `${element.tagName.toLowerCase()}[${attr}="${esc(value)}"]`;
      add("css", selector, uniqueCss(selector) ? 95 : 75);
    }
    const path = cssPath(element);
    add("css", path, uniqueCss(path) ? 85 : 60);
    return selectors.sort((a, b) => b.score - a.score);
  }

  function textOf(element) {
    return String(element.innerText || element.textContent || "").replace(/\s+/g, " ").trim().slice(0, 200);
  }

  function snapshot(element) {
    const rect = element.getBoundingClientRect();
    const attrs = {};
    for (const name of ["id", "name", "type", "role", "aria-label", "placeholder", "data-testid", "data-test", "data-qa"]) {
      const value = element.getAttribute(name);
      if (value !== null && value !== "") attrs[name] = value;
    }
    return {
      tag: element.tagName.toLowerCase(), text: textOf(element), attributes: attrs,
      classes: stableClasses(element),
      bounds: { x: rect.left, y: rect.top, width: rect.width, height: rect.height },
      visible: Boolean(rect.width && rect.height),
      focused: document.activeElement === element,
      value: "value" in element ? String(element.value ?? "") : undefined
    };
  }

  function locatorFor(element) {
    return {
      backend: "browser-dom", version: 1,
      page: { url: location.href, origin: location.origin, title: document.title },
      frame: { url: location.href, is_top: window === window.top },
      target: snapshot(element), selectors: selectorsFor(element)
    };
  }

  function scoreCandidate(element, target) {
    if (!target) return 0;
    let score = element.tagName.toLowerCase() === target.tag ? 20 : 0;
    for (const [name, value] of Object.entries(target.attributes || {})) {
      if (element.getAttribute(name) === value) score += name === "id" ? 80 : 30;
    }
    if (target.text && textOf(element) === target.text) score += 25;
    return score;
  }

  function resolve(locator) {
    if (!locator || locator.backend !== "browser-dom") throw new Error("不是网页 DOM 元素定位器");
    if (locator.page?.origin && locator.page.origin !== location.origin) {
      throw new Error(`当前网页域名不匹配：${location.origin}`);
    }
    let candidates = [];
    for (const selector of locator.selectors || []) {
      if (selector.enabled === false || selector.kind !== "css") continue;
      try {
        const found = [...document.querySelectorAll(selector.value)];
        if (found.length === 1) return found[0];
        candidates.push(...found);
      } catch (_) {}
    }
    candidates = [...new Set(candidates)];
    if (candidates.length) {
      candidates.sort((a, b) => scoreCandidate(b, locator.target) - scoreCandidate(a, locator.target));
      if (scoreCandidate(candidates[0], locator.target) > 0) return candidates[0];
    }
    throw new Error("未找到网页元素；页面可能已跳转，或所选属性发生了变化");
  }

  function nativeSetValue(element, value) {
    if (element.isContentEditable) {
      element.textContent = value;
    } else {
      const prototype = element instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : element instanceof HTMLSelectElement
          ? HTMLSelectElement.prototype
          : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
      if (setter) setter.call(element, value); else element.value = value;
    }
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function stopPicking() {
    picking = false;
    hideHighlight();
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("click", onClick, true);
    document.removeEventListener("keydown", onKey, true);
  }

  function onMove(event) {
    if (!picking || event.target === overlay) return;
    showHighlight(event.target);
  }

  function onClick(event) {
    if (!picking || !event.ctrlKey) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const element = event.target;
    const result = { captured: snapshot(element), locator: locatorFor(element) };
    stopPicking();
    chrome.runtime.sendMessage({ type: "softauto-pick-result", ok: true, result });
  }

  function onKey(event) {
    if (event.key !== "Escape") return;
    event.preventDefault();
    stopPicking();
    chrome.runtime.sendMessage({ type: "softauto-pick-result", ok: false, error: "已取消网页元素拾取" });
  }

  function startPicking() {
    stopPicking();
    picking = true;
    document.addEventListener("mousemove", onMove, true);
    document.addEventListener("click", onClick, true);
    document.addEventListener("keydown", onKey, true);
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.source !== "softauto-extension") return false;
    try {
      if (message.command === "start_pick") {
        startPicking();
        sendResponse({ ok: true, result: { picking: true, frame: location.href } });
        return true;
      }
      if (message.command === "stop_pick") {
        stopPicking();
        sendResponse({ ok: true, result: { picking: false } });
        return true;
      }
      const element = resolve(message.payload && message.payload.locator);
      element.scrollIntoView({ block: "center", inline: "center", behavior: "instant" });
      if (message.command === "validate" || message.command === "highlight") {
        showHighlight(element, 1600);
      } else if (message.command === "focus") {
        element.focus();
      } else if (message.command === "click" || message.command === "invoke") {
        element.focus();
        element.click();
      } else if (message.command === "set_value") {
        element.focus();
        nativeSetValue(element, String(message.payload.value ?? ""));
      } else if (message.command === "send_keys") {
        element.focus();
        const current = element.isContentEditable ? element.textContent : element.value;
        nativeSetValue(element, String(current || "") + String(message.payload.text ?? ""));
      } else throw new Error(`不支持的网页操作：${message.command}`);
      sendResponse({
        ok: true,
        result: { found: true, element: snapshot(element), page: { url: location.href, title: document.title } }
      });
    } catch (error) {
      sendResponse({ ok: false, error: error.message || String(error) });
    }
    return true;
  });

  function wakeBackground() {
    chrome.runtime.sendMessage({ type: "softauto-content-ready" }).catch(() => {});
  }

  wakeBackground();
  window.setInterval(wakeBackground, 10000);
})();
