"use strict";

export const SUPPORTED_LOCALES = new Set(["en", "ja", "zh-TW", "zh-CN"]);
export const SPEECH_LOCALES = { en: "en-US", ja: "ja-JP", "zh-TW": "zh-TW", "zh-CN": "zh-CN" };

export function preferredLocale() {
  const stored = localStorage.getItem("ninjarobotLocale");
  if (SUPPORTED_LOCALES.has(stored)) return stored;
  const requested = navigator.languages?.[0] || navigator.language || "en";
  if (/^ja/i.test(requested)) return "ja";
  if (/^zh-(tw|hk|mo|hant)/i.test(requested)) return "zh-TW";
  if (/^zh/i.test(requested)) return "zh-CN";
  return "en";
}

export function preferredInterface() {
  const stored = localStorage.getItem("ninjarobotInterface");
  return stored === "gamepad" ? "gamepad" : "agent";
}

export function persistentBrowserChatId() {
  const stored = localStorage.getItem("ninjarobotBrowserChatId");
  if (stored && /^[A-Za-z0-9_-]{16,128}$/.test(stored)) {
    return stored;
  }
  const bytes = new Uint8Array(24);
  window.crypto.getRandomValues(bytes);
  const created = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
  localStorage.setItem("ninjarobotBrowserChatId", created);
  return created;
}

export const state = {
  socket: null,
  leaseId: null,
  reconnectToken: sessionStorage.getItem("ninjarobotReconnectToken"),
  browserChatId: persistentBrowserChatId(),
  heartbeatTimer: null,
  requestCounter: 0,
  pending: new Map(),
  activeAssistant: new Map(),
  voiceEnabled: false,
  recognition: null,
  recognitionActive: false,
  previewTimer: null,
  released: false,
  activeMoveButton: null,
  drawerDragged: false,
  controllerStarted: false,
  certificateHelpLogged: false,
  locale: preferredLocale(),
  interfaceMode: preferredInterface(),
  messages: {},
  englishMessages: {},
  poweroffEnabled: false,
  poweroffAuthorized: false,
  poweroffNonce: null,
  remoteConnection: false,
  previousFocus: null,
  connectionKey: "connection.offline",
  connectionClass: "badge-wait",
  displayGeneration: 0,
};

export const elements = {
  badge: document.querySelector("#connectionBadge"),
  armAi: document.querySelector("#armAiButton"),
  armAiCamera: document.querySelector("#armAiCameraButton"),
  chatMessages: document.querySelector("#chatMessages"),
  chatForm: document.querySelector("#chatForm"),
  chatInput: document.querySelector("#chatInput"),
  log: document.querySelector("#systemLog"),
  toast: document.querySelector("#toast"),
  voiceInput: document.querySelector("#usbMicButton"),
  webMic: document.querySelector("#webMicButton"),
  language: document.querySelector("#languageSelect"),
  preview: document.querySelector("#cameraPreview"),
  cameraImage: document.querySelector("#cameraImage"),
  activityDrawer: document.querySelector("#activityDrawer"),
  activityToggle: document.querySelector("#activityToggle"),
  startOverlay: document.querySelector("#startOverlay"),
  startController: document.querySelector("#startControllerButton"),
  menuButton: document.querySelector("#menuButton"),
  menu: document.querySelector("#robotMenu"),
  closeMenu: document.querySelector("#closeMenuButton"),
  powerOff: document.querySelector("#powerOffButton"),
  powerAvailability: document.querySelector("#powerOffAvailability"),
  powerDialog: document.querySelector("#powerOffDialog"),
  cancelPowerOff: document.querySelector("#cancelPowerOffButton"),
  confirmPowerOff: document.querySelector("#confirmPowerOffButton"),
  gamepadView: document.querySelector("#gamepadView"),
  agentView: document.querySelector("#agentView"),
  switchToGamepad: document.querySelector("#switchToGamepad"),
  switchToAgent: document.querySelector("#switchToAgent"),
  userBehaviorSelect: document.querySelector("#userBehaviorSelect"),
  playBehavior: document.querySelector("#playBehaviorButton"),
  gamepadCamera: document.querySelector("#gamepadCameraButton"),
  speechOn: document.querySelector("#speechOnButton"),
  emergencyStop: document.querySelector("#emergencyStopButton"),
  resumeMovement: document.querySelector("#resumeMovementButton"),
};

export function t(key, replacements = {}) {
  const template = state.messages[key] || state.englishMessages[key] || key;
  return Object.entries(replacements).reduce(
    (value, [name, replacement]) => value.replaceAll(`{${name}}`, String(replacement)),
    template,
  );
}

export function applyTranslations() {
  document.documentElement.lang = state.locale;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nAria));
  });
  document.querySelectorAll("[data-i18n-alt]").forEach((node) => {
    node.setAttribute("alt", t(node.dataset.i18nAlt));
  });
  messageHandlers.applyTranslations?.();
  renderConnection();
  updatePoweroffAvailability();
  updateInterfaceButtons();
}

export async function setLocale(locale) {
  const selected = SUPPORTED_LOCALES.has(locale) ? locale : "en";
  try {
    if (Object.keys(state.englishMessages).length === 0) {
      const english = await fetch("/assets/i18n/en.json", { cache: "no-store" });
      if (!english.ok) throw new Error(`English dictionary HTTP ${english.status}`);
      state.englishMessages = await english.json();
    }
    if (selected === "en") {
      state.messages = state.englishMessages;
    } else {
      const response = await fetch(`/assets/i18n/${encodeURIComponent(selected)}.json`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.messages = await response.json();
    }
    state.locale = selected;
  } catch (error) {
    console.error("NinjaRobot translation load failed", error);
    state.locale = "en";
    state.messages = state.englishMessages;
  }
  localStorage.setItem("ninjarobotLocale", state.locale);
  if (elements.language) elements.language.value = state.locale;
  applyTranslations();
}

/* ── Logging and Toast ───────────────────────────────── */

export function log(message, kind = "info") {
  if (!elements.log) return;
  const row = document.createElement("div");
  row.className = `log-entry ${kind === "error" ? "log-error" : ""}`;
  const timestamp = document.createElement("span");
  timestamp.textContent = new Date().toLocaleTimeString([], { hour12: false });
  const text = document.createElement("span");
  text.textContent = message;
  row.append(timestamp, text);
  elements.log.append(row);
  while (elements.log.children.length > 200) {
    elements.log.firstElementChild.remove();
  }
  elements.log.scrollTop = elements.log.scrollHeight;
}

export function toast(message) {
  if (!elements.toast) return;
  elements.toast.textContent = message;
  elements.toast.classList.remove("hidden");
  window.setTimeout(() => elements.toast?.classList.add("hidden"), 3200);
}

export function renderConnection() {
  if (!elements.badge) return;
  elements.badge.textContent = t(state.connectionKey);
  elements.badge.className = `badge ${state.connectionClass}`;
}

export function setConnection(key, className) {
  state.connectionKey = key;
  state.connectionClass = className;
  renderConnection();
}

/* ── WebSocket ───────────────────────────────────────── */

export function send(type, payload = {}) {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN || !state.leaseId) {
    toast(t("error.controllerDisconnected"));
    return Promise.reject(new Error("controller is disconnected"));
  }
  const requestId = `web-${Date.now()}-${++state.requestCounter}`;
  const message = { type, request_id: requestId, lease_id: state.leaseId, ...payload };
  state.socket.send(JSON.stringify(message));
  return new Promise((resolve, reject) => {
    state.pending.set(requestId, { resolve, reject, type });
    const responseTimeout = type === "chat" ? 620000 : 120000;
    window.setTimeout(() => {
      const pending = state.pending.get(requestId);
      if (pending) {
        state.pending.delete(requestId);
        reject(
          new Error(
            t("error.timeout", { type, seconds: responseTimeout / 1000 }),
          ),
        );
      }
    }, responseTimeout);
  });
}

const messageHandlers = {};

export function registerMessageHandlers(handlers = {}) {
  Object.assign(messageHandlers, handlers);
}

export function connect() {
  state.released = false;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const query = new URLSearchParams({ browser_chat_id: state.browserChatId });
  if (state.reconnectToken) {
    query.set("reconnect_token", state.reconnectToken);
  }
  const socket = new WebSocket(`${protocol}//${window.location.host}/ws?${query}`);
  state.socket = socket;
  setConnection("connection.connecting", "badge-wait");

  socket.addEventListener("open", () => log(t("connection.opened")));
  socket.addEventListener("message", (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      log(t("error.badData"), "error");
      return;
    }
    handleMessage(message);
  });
  socket.addEventListener("close", (event) => {
    window.clearInterval(state.heartbeatTimer);
    state.heartbeatTimer = null;
    state.leaseId = null;
    state.poweroffAuthorized = false;
    messageHandlers.onClose?.(event);
    updatePoweroffAvailability();
    setConnection(
      event.code === 4423 ? "connection.locked" : "connection.disconnected",
      "badge-wait",
    );
    log(
      event.code === 4423
        ? t("error.anotherController")
        : t("connection.closed"),
      event.code === 4423 ? "error" : "info",
    );
    if (!state.released && event.code !== 4423) {
      window.setTimeout(connect, 1500);
    }
  });
  socket.addEventListener("error", () => {
    log(t("error.https"), "error");
    if (!state.certificateHelpLogged) {
      state.certificateHelpLogged = true;
      log(
        t("error.certificateHelp"),
        "error",
      );
      toast(t("error.https"));
    }
  });
}

function handleMessage(message) {
  if (message.type === "lease") {
    state.leaseId = message.lease_id;
    state.certificateHelpLogged = false;
    state.reconnectToken = message.reconnect_token;
    state.remoteConnection = message.remote === true;
    state.poweroffAuthorized = message.poweroff_authorized === true;
    sessionStorage.setItem("ninjarobotReconnectToken", state.reconnectToken);
    setConnection("connection.active", "badge-ok");
    log(t("connection.owned"));
    messageHandlers.onLease?.(message);
    const interval = Math.max(1000, Number(message.heartbeat_seconds) * 1000);
    window.clearInterval(state.heartbeatTimer);
    state.heartbeatTimer = window.setInterval(() => {
      send("heartbeat").catch(() => {});
    }, interval);
    return;
  }
  if (message.type === "heartbeat") {
    settle(message.request_id, true, message);
    return;
  }
  if (message.type === "system_status") {
    const provider = message.data?.provider;
    const providerText = provider
      ? `${provider.provider}: ${provider.status}`
      : t("status.providerUnavailable");
    const toolCount = Array.isArray(message.data?.tools) ? message.data.tools.length : 0;
    log(t("status.ready", { provider: providerText, tools: toolCount }));
    state.poweroffEnabled = message.data?.release?.shutdown?.enabled === true;
    updatePoweroffAvailability();
    messageHandlers.onSystemStatus?.(message);
    return;
  }
  if (message.type === "conversation_history") {
    messageHandlers.onConversationHistory?.(message);
    return;
  }
  if (message.type === "event") {
    const event = message.event || {};
    if (
      event.event_type === "media" &&
      event.data?.kind === "camera_preview" &&
      typeof event.data?.jpeg_base64 === "string"
    ) {
      showCameraPreview(event.data.jpeg_base64);
    }
    if (event.data?.kind === "web_movement_failed") {
      toast(event.message || t("error.requestFailed"));
    }
    messageHandlers.onEvent?.(event);
    log(event.message || t("status.agentEvent"), event.event_type === "error" ? "error" : "info");
    return;
  }
  if (message.type === "chat_delta") {
    messageHandlers.onChatDelta?.(message);
    return;
  }
  if (message.type === "result") {
    settle(message.request_id, true, message.data);
    messageHandlers.onResult?.(message);
    return;
  }
  if (message.type === "error") {
    settle(message.request_id, false, new Error(message.error || t("error.requestFailed")));
    messageHandlers.onError?.(message);
    log(message.error || t("error.requestFailed"), "error");
    toast(message.error || t("error.requestFailed"));
  }
}

export function settle(requestId, succeeded, value) {
  const pending = state.pending.get(requestId);
  if (!pending) return;
  state.pending.delete(requestId);
  if (succeeded) pending.resolve(value);
  else pending.reject(value);
}

/* ── Emergency Stop and Resume (shared) ──────────────── */

export function initSharedActions() {
  document.querySelectorAll("[data-action='emergency']").forEach((button) => {
    button.addEventListener("click", () => {
      send("emergency_stop")
        .then(() => {
          messageHandlers.onEmergencyStop?.();
          toast(t("behavior.emergencyComplete"));
        })
        .catch(() => {});
    });
  });

  document.querySelectorAll("[data-action='resume']").forEach((button) => {
    button.addEventListener("click", () => {
      resumeRobot().catch(() => {});
    });
  });
}

export function resumeRobot(showInChat = false) {
  if (!window.confirm(t("resume.confirm"))) {
    if (showInChat) messageHandlers.onChatResumeCancelled?.();
    return Promise.resolve(false);
  }
  return send("resume", { confirmed: true })
    .then(() => {
      messageHandlers.onEmergencyStop?.();
      const message = t("resume.message");
      if (showInChat) messageHandlers.onChatResumeSuccess?.(message);
      toast(t("resume.toast"));
      return true;
    })
    .catch((error) => {
      if (showInChat) {
        messageHandlers.onChatResumeFailed?.(t("resume.failed", { error: error.message }));
      }
      throw error;
    });
}

/* ── Camera Preview ──────────────────────────────────── */

export function showCameraPreview(jpegBase64) {
  if (!elements.cameraImage || !elements.preview) return;
  elements.cameraImage.src = `data:image/jpeg;base64,${jpegBase64}`;
  elements.preview.classList.remove("hidden");
  window.clearTimeout(state.previewTimer);
  state.previewTimer = window.setTimeout(clearPreview, 15000);
}

export function clearPreview() {
  if (!elements.cameraImage || !elements.preview) return;
  window.clearTimeout(state.previewTimer);
  elements.cameraImage.removeAttribute("src");
  elements.preview.classList.add("hidden");
}

/* ── Menu & Dialogs ──────────────────────────────────── */

export function updatePoweroffAvailability() {
  if (!elements.powerOff || !elements.powerAvailability) return;
  elements.powerOff.disabled =
    !state.poweroffEnabled || !state.poweroffAuthorized || !state.leaseId;
  elements.powerAvailability.textContent =
    state.poweroffEnabled && state.poweroffAuthorized
      ? t("power.enabled")
      : t("power.disabled");
}

export function focusableElements(container) {
  return Array.from(
    container.querySelectorAll(
      'button:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((node) => !node.hidden);
}

export function openMenu() {
  if (!elements.menu) return;
  state.previousFocus = document.activeElement;
  updateInterfaceButtons();
  elements.menu.classList.remove("hidden");
  elements.menuButton?.setAttribute("aria-expanded", "true");
  document.body.classList.add("modal-open");
  elements.closeMenu?.focus();
}

export function closeMenu({ restoreFocus = true } = {}) {
  if (!elements.menu) return;
  elements.menu.classList.add("hidden");
  elements.menuButton?.setAttribute("aria-expanded", "false");
  if (!elements.powerDialog || elements.powerDialog.classList.contains("hidden")) {
    document.body.classList.remove("modal-open");
  }
  if (restoreFocus && state.previousFocus instanceof HTMLElement) {
    state.previousFocus.focus();
  }
}

export function showPowerDialog() {
  closeMenu({ restoreFocus: false });
  if (!elements.powerDialog) return;
  elements.powerDialog.classList.remove("hidden");
  document.body.classList.add("modal-open");
  elements.cancelPowerOff?.focus();
}

export function closePowerDialog() {
  state.poweroffNonce = null;
  if (!elements.powerDialog) return;
  elements.powerDialog.classList.add("hidden");
  document.body.classList.remove("modal-open");
  elements.powerOff?.focus();
}

export function trapDialogFocus(event, container) {
  if (event.key !== "Tab") return;
  const focusable = focusableElements(container);
  if (focusable.length === 0) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

export function updateInterfaceButtons() {
  const currentPath = window.location.pathname;
  let activeMode = "agent";
  if (currentPath.startsWith("/gamepad")) {
    activeMode = "gamepad";
  } else if (currentPath.startsWith("/agent")) {
    // If user has a stored preference and just started, check if preferred is gamepad
    const stored = localStorage.getItem("ninjarobotInterface");
    if (stored === "gamepad" && !sessionStorage.getItem("ninjarobotNavigated")) {
      activeMode = "gamepad";
    } else {
      activeMode = "agent";
    }
  } else {
    activeMode = preferredInterface();
  }

  if (elements.switchToGamepad) {
    elements.switchToGamepad.classList.toggle("active", activeMode === "gamepad");
  }
  if (elements.switchToAgent) {
    elements.switchToAgent.classList.toggle("active", activeMode === "agent");
  }
}

/* ── Activity Drawer ─────────────────────────────────── */

export function setActivityDrawer(open) {
  if (!elements.activityDrawer || !elements.activityToggle) return;
  elements.activityDrawer.classList.toggle("open", open);
  elements.activityToggle.setAttribute("aria-expanded", String(open));
}

export function initActivityDrawer() {
  if (!elements.activityDrawer || !elements.activityToggle) return;
  let drawerStartY = null;
  elements.activityToggle.addEventListener("pointerdown", (event) => {
    drawerStartY = event.clientY;
    state.drawerDragged = false;
    elements.activityToggle.setPointerCapture?.(event.pointerId);
  });
  elements.activityToggle.addEventListener("pointermove", (event) => {
    if (drawerStartY === null) return;
    const distance = event.clientY - drawerStartY;
    if (Math.abs(distance) < 10) return;
    state.drawerDragged = true;
    if (distance < -35) setActivityDrawer(true);
    if (distance > 35) setActivityDrawer(false);
  });
  elements.activityToggle.addEventListener("pointerup", () => {
    drawerStartY = null;
    window.setTimeout(() => {
      state.drawerDragged = false;
    }, 0);
  });
  elements.activityToggle.addEventListener("pointercancel", () => {
    drawerStartY = null;
  });
  elements.activityToggle.addEventListener("click", (event) => {
    if (state.drawerDragged) {
      event.preventDefault();
      return;
    }
    setActivityDrawer(!elements.activityDrawer.classList.contains("open"));
  });

  const clearLog = document.querySelector("#clearLogButton");
  if (clearLog && elements.log) {
    clearLog.addEventListener("click", () => {
      elements.log.replaceChildren();
    });
  }
}

/* ── Viewport & Screen ───────────────────────────────── */

export function syncViewportHeight() {
  const height = window.visualViewport?.height || window.innerHeight;
  const orientation = window.screen.orientation?.type;
  const landscape = orientation ? orientation.startsWith("landscape")
    : window.screen.width > window.screen.height;
  document.body.classList.toggle("physical-landscape", landscape);
  document.documentElement.style.setProperty("--app-height", `${height}px`);
}

export function standaloneDisplay() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

export async function requestControllerFullscreen() {
  if (standaloneDisplay() || document.fullscreenElement) return;
  const root = document.documentElement;
  const requestFullscreen = root.requestFullscreen || root.webkitRequestFullscreen;
  if (!requestFullscreen) {
    log(t("start.fullscreenHelp"));
    return;
  }
  try {
    await requestFullscreen.call(root);
    if (window.screen.orientation?.lock) {
      await window.screen.orientation.lock("portrait").catch(() => {});
    }
  } catch (error) {
    log(t("error.fullscreenUnavailable", { error: error.message }));
  }
}

export async function startController() {
  if (state.controllerStarted) return;
  state.controllerStarted = true;
  sessionStorage.setItem("ninjarobotStarted", "true");
  await requestControllerFullscreen();
  elements.startOverlay?.classList.add("started");
  connect();
  openMenu();
}

export function attachPressState(button) {
  if (!button) return;
  const setPressing = (on) => {
    button.classList.toggle("pressing", on);
  };
  if (window.PointerEvent) {
    button.addEventListener("pointerdown", (event) => {
      if (!event.isPrimary || event.button !== 0) return;
      setPressing(true);
    });
    button.addEventListener("pointerup", () => setPressing(false));
    button.addEventListener("pointercancel", () => setPressing(false));
    button.addEventListener("lostpointercapture", () => setPressing(false));
  } else {
    button.addEventListener("touchstart", () => setPressing(true), { passive: true });
    button.addEventListener("touchend", () => setPressing(false), { passive: true });
    button.addEventListener("touchcancel", () => setPressing(false), { passive: true });
  }
  button.addEventListener("blur", () => setPressing(false));
}

/* ── Initialization of Shared Infrastructure ─────────── */

export async function initShared({ pageName }) {
  await setLocale(state.locale);
  syncViewportHeight();
  window.addEventListener("resize", syncViewportHeight);
  window.visualViewport?.addEventListener("resize", syncViewportHeight);

  window.addEventListener("pagehide", () => {
    window.clearInterval(state.heartbeatTimer);
  });

  initSharedActions();
  initActivityDrawer();

  const closePreview = document.querySelector("#closePreviewButton");
  if (closePreview) {
    closePreview.addEventListener("click", clearPreview);
  }

  if (elements.menuButton) elements.menuButton.addEventListener("click", openMenu);
  if (elements.closeMenu) elements.closeMenu.addEventListener("click", () => closeMenu());
  if (elements.menu) {
    elements.menu.addEventListener("click", (event) => {
      if (event.target === elements.menu) closeMenu();
    });
  }

  if (elements.language) {
    elements.language.addEventListener("change", () => {
      setLocale(elements.language.value).catch((error) => {
        log(String(error), "error");
      });
    });
  }

  // Interface button navigation
  if (elements.switchToGamepad) {
    elements.switchToGamepad.addEventListener("click", () => {
      localStorage.setItem("ninjarobotInterface", "gamepad");
      sessionStorage.setItem("ninjarobotNavigated", "true");
      if (window.location.pathname.startsWith("/gamepad")) {
        closeMenu();
      } else {
        window.location.href = "/gamepad";
      }
    });
  }

  if (elements.switchToAgent) {
    elements.switchToAgent.addEventListener("click", () => {
      localStorage.setItem("ninjarobotInterface", "agent");
      sessionStorage.setItem("ninjarobotNavigated", "true");
      if (window.location.pathname.startsWith("/agent")) {
        closeMenu();
      } else {
        window.location.href = "/agent";
      }
    });
  }

  // Power off handlers
  if (elements.powerOff) {
    elements.powerOff.addEventListener("click", () => {
      if (!state.poweroffEnabled || !state.poweroffAuthorized) return;
      elements.powerOff.disabled = true;
      elements.powerAvailability.textContent = t("power.preparing");
      send("poweroff_prepare")
        .then((data) => {
          state.poweroffNonce = data.nonce;
          showPowerDialog();
        })
        .catch(() => {})
        .finally(updatePoweroffAvailability);
    });
  }

  if (elements.cancelPowerOff) {
    elements.cancelPowerOff.addEventListener("click", closePowerDialog);
  }

  if (elements.confirmPowerOff) {
    elements.confirmPowerOff.addEventListener("click", () => {
      const nonce = state.poweroffNonce;
      if (!nonce) {
        closePowerDialog();
        return;
      }
      elements.cancelPowerOff.disabled = true;
      elements.confirmPowerOff.disabled = true;
      send("poweroff_confirm", { confirmed: true, nonce })
        .then(() => {
          state.released = true;
          elements.powerDialog?.classList.add("hidden");
          document.body.classList.remove("modal-open");
          toast(t("power.shuttingDown"));
          setConnection("power.shuttingDown", "badge-wait");
        })
        .catch(() => {
          closePowerDialog();
        })
        .finally(() => {
          if (elements.cancelPowerOff) elements.cancelPowerOff.disabled = false;
          if (elements.confirmPowerOff) elements.confirmPowerOff.disabled = false;
        });
    });
  }

  // Keyboard accessibility
  document.addEventListener("keydown", (event) => {
    if (elements.powerDialog && !elements.powerDialog.classList.contains("hidden")) {
      if (event.key === "Escape") closePowerDialog();
      else trapDialogFocus(event, elements.powerDialog);
      return;
    }
    if (elements.menu && !elements.menu.classList.contains("hidden")) {
      if (event.key === "Escape") closeMenu();
      else trapDialogFocus(event, elements.menu);
    }
  });

  // Attach button press states to action buttons on the page
  document.querySelectorAll(".action-button").forEach(attachPressState);

  // Start Overlay Flow
  const started = sessionStorage.getItem("ninjarobotStarted") === "true";
  if (started) {
    state.controllerStarted = true;
    elements.startOverlay?.classList.add("started");
    connect();
  } else if (standaloneDisplay()) {
    sessionStorage.setItem("ninjarobotStarted", "true");
    elements.startOverlay?.classList.add("started");
    state.controllerStarted = true;
    connect();
    openMenu();
  } else if (elements.startController) {
    elements.startController.addEventListener("click", () => {
      startController().catch((error) => {
        state.controllerStarted = false;
        sessionStorage.removeItem("ninjarobotStarted");
        log(`${t("error.controllerStart")} ${error.message}`, "error");
        toast(t("error.controllerStart"));
      });
    });
  }
}
