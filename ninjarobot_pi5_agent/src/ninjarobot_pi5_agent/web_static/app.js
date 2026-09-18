(async () => {
  "use strict";

  const SUPPORTED_LOCALES = new Set(["en", "ja", "zh-TW", "zh-CN"]);
  const SPEECH_LOCALES = { en: "en-US", ja: "ja-JP", "zh-TW": "zh-TW", "zh-CN": "zh-CN" };

  function preferredLocale() {
    const stored = localStorage.getItem("ninjarobotLocale");
    if (SUPPORTED_LOCALES.has(stored)) return stored;
    const requested = navigator.languages?.[0] || navigator.language || "en";
    if (/^ja/i.test(requested)) return "ja";
    if (/^zh-(tw|hk|mo|hant)/i.test(requested)) return "zh-TW";
    if (/^zh/i.test(requested)) return "zh-CN";
    return "en";
  }

  function preferredInterface() {
    const stored = localStorage.getItem("ninjarobotInterface");
    return stored === "gamepad" ? "gamepad" : "agent";
  }

  function persistentBrowserChatId() {
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

  const state = {
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

  const elements = {
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
  };

  function t(key, replacements = {}) {
    const template = state.messages[key] || state.englishMessages[key] || key;
    return Object.entries(replacements).reduce(
      (value, [name, replacement]) => value.replaceAll(`{${name}}`, String(replacement)),
      template,
    );
  }

  function applyTranslations() {
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
    if (elements.armAi) {
      updateAiMotion(elements.armAi.dataset.armed === "true");
    }
    if (elements.armAiCamera) {
      updateAiCamera(elements.armAiCamera.dataset.granted === "true");
    }
    updateVoiceInput({ enabled: state.voiceEnabled, state: elements.voiceInput.dataset.state });
    renderConnection();
    updatePoweroffAvailability();
    updateInterfaceButtons();
  }

  async function setLocale(locale) {
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
    elements.language.value = state.locale;
    applyTranslations();
  }

  /* ── View Switching ──────────────────────────────────── */

  function switchView(mode) {
    if (mode !== "gamepad" && mode !== "agent") mode = "agent";
    stopMovement();
    state.interfaceMode = mode;
    localStorage.setItem("ninjarobotInterface", mode);

    const isGamepad = mode === "gamepad";
    elements.gamepadView.hidden = !isGamepad;
    elements.agentView.hidden = isGamepad;
    updateInterfaceButtons();
    closeMenu();
  }

  function updateInterfaceButtons() {
    if (elements.switchToGamepad) {
      elements.switchToGamepad.classList.toggle("active", state.interfaceMode === "gamepad");
    }
    if (elements.switchToAgent) {
      elements.switchToAgent.classList.toggle("active", state.interfaceMode === "agent");
    }
  }

  elements.switchToGamepad.addEventListener("click", () => switchView("gamepad"));
  elements.switchToAgent.addEventListener("click", () => switchView("agent"));

  /* ── Logging and Toast ───────────────────────────────── */

  function log(message, kind = "info") {
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

  function toast(message) {
    elements.toast.textContent = message;
    elements.toast.classList.remove("hidden");
    window.setTimeout(() => elements.toast.classList.add("hidden"), 3200);
  }

  function renderConnection() {
    elements.badge.textContent = t(state.connectionKey);
    elements.badge.className = `badge ${state.connectionClass}`;
  }

  function setConnection(key, className) {
    state.connectionKey = key;
    state.connectionClass = className;
    renderConnection();
  }

  /* ── Chat Messages ───────────────────────────────────── */

  function addMessage(role, text = "") {
    const node = document.createElement("div");
    node.className = `message ${role}`;
    node.textContent = text;
    node.dataset.generation = String(state.displayGeneration);
    elements.chatMessages.append(node);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    return node;
  }

  /* ── WebSocket ───────────────────────────────────────── */

  function send(type, payload = {}) {
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

  function connect() {
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
      updateAiCamera(false);
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
      refreshSpeechState();
      loadUserBehaviors();
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
      updateVoiceInput(message.data?.release?.voice);
      state.poweroffEnabled = message.data?.release?.shutdown?.enabled === true;
      updatePoweroffAvailability();
      return;
    }
    if (message.type === "conversation_history") {
      elements.chatMessages.replaceChildren();
      const history = Array.isArray(message.data) ? message.data : [];
      history.forEach((stored) => {
        const role = stored.message?.role === "user" ? "user" : "assistant";
        const content = stored.message?.content;
        if (typeof content === "string" && content.trim()) addMessage(role, content);
      });
      if (history.length === 0) {
        addMessage("assistant", t("chat.ready"));
      }
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
        updateAiCamera(false);
      }
      if (event.event_type === "voice" && event.data?.kind === "voice_transcript") {
        addMessage("user", t("voice.transcript", { text: event.data.transcript || "" }));
      }
      if (event.event_type === "voice" && event.data?.kind === "voice_reply") {
        addMessage("assistant", event.data.text || t("chat.noResponse"));
      }
      if (event.event_type === "voice" && event.data?.kind === "voice_status") {
        updateVoiceInput({
          enabled: event.data.state !== "disabled",
          state: event.data.state,
        });
      }
      if (event.data?.kind === "web_movement_failed") {
        toast(event.message || t("error.requestFailed"));
      }
      log(event.message || t("status.agentEvent"), event.event_type === "error" ? "error" : "info");
      return;
    }
    if (message.type === "chat_delta") {
      let node = state.activeAssistant.get(message.request_id);
      if (!node) {
        node = addMessage("assistant");
        state.activeAssistant.set(message.request_id, node);
      }
      // Skip update if the node was cleared (belongs to a previous display generation).
      if (Number(node.dataset.generation) < state.displayGeneration) {
        return;
      }
      node.textContent += message.text || "";
      elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
      return;
    }
    if (message.type === "result") {
      settle(message.request_id, true, message.data);
      const assistant = state.activeAssistant.get(message.request_id);
      if (assistant && !assistant.textContent.trim()) {
        assistant.textContent = message.data?.text || t("chat.noResponse");
      }
      state.activeAssistant.delete(message.request_id);
      return;
    }
    if (message.type === "error") {
      settle(message.request_id, false, new Error(message.error || t("error.requestFailed")));
      state.activeAssistant.delete(message.request_id);
      log(message.error || t("error.requestFailed"), "error");
      toast(message.error || t("error.requestFailed"));
    }
  }

  function settle(requestId, succeeded, value) {
    const pending = state.pending.get(requestId);
    if (!pending) return;
    state.pending.delete(requestId);
    if (succeeded) pending.resolve(value);
    else pending.reject(value);
  }

  /* ── D-pad Movement ──────────────────────────────────── */

  let movementGeneration = 0;

  function startMovement(button, event) {
    if (state.activeMoveButton) return;
    event.preventDefault();
    state.activeMoveButton = button;
    const generation = ++movementGeneration;
    button.classList.add("active");
    send("move_start", { direction: button.dataset.direction }).catch((error) => {
      if (generation === movementGeneration) {
        button.classList.remove("active");
        state.activeMoveButton = null;
      }
      log(error.message, "error");
    });
  }

  function stopMovement(event) {
    if (event) event.preventDefault();
    const button = state.activeMoveButton;
    if (!button) return;
    state.activeMoveButton = null;
    movementGeneration += 1;
    button.classList.remove("active");
    send("move_stop").catch(() => {});
  }

  document.querySelectorAll(".dpad-button").forEach((button) => {
    button.addEventListener("keydown", (event) => {
      if (event.key !== " " && event.key !== "Enter") return;
      event.preventDefault();
      if (!event.repeat) startMovement(button, event);
    });
    button.addEventListener("keyup", (event) => {
      if (event.key === " " || event.key === "Enter") stopMovement(event);
    });
    button.addEventListener("blur", () => {
      if (state.activeMoveButton === button) stopMovement();
    });
    button.addEventListener("selectstart", (event) => event.preventDefault());
    button.addEventListener("contextmenu", (event) => event.preventDefault());
    button.addEventListener("dragstart", (event) => event.preventDefault());
    if (window.PointerEvent) {
      button.addEventListener("pointerdown", (event) => {
        if (!event.isPrimary || event.button !== 0) return;
        event.preventDefault();
        button.setPointerCapture?.(event.pointerId);
        startMovement(button, event);
      });
      button.addEventListener("pointerup", stopMovement);
      button.addEventListener("pointercancel", stopMovement);
      button.addEventListener("lostpointercapture", stopMovement);
    } else {
      button.addEventListener(
        "touchstart",
        (event) => startMovement(button, event),
        { passive: false },
      );
      button.addEventListener("touchend", stopMovement, { passive: false });
      button.addEventListener("touchcancel", stopMovement, { passive: false });
    }
  });
  window.addEventListener("blur", stopMovement);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopMovement();
  });

  /* ── Emergency Stop and Resume (shared) ──────────────── */

  document.querySelectorAll("[data-action='emergency']").forEach((button) => {
    button.addEventListener("click", () => {
      send("emergency_stop")
        .then(() => {
          updateAiMotion(false);
          updateAiCamera(false);
          toast(t("behavior.emergencyComplete"));
        })
        .catch(() => {});
    });
  });

  function resumeRobot(showInChat = false) {
    if (!window.confirm(t("resume.confirm"))) {
      if (showInChat) addMessage("assistant", t("resume.cancelled"));
      return Promise.resolve(false);
    }
    return send("resume", { confirmed: true })
      .then(() => {
        updateAiMotion(false);
        const message = t("resume.message");
        if (showInChat) addMessage("assistant", message);
        toast(t("resume.toast"));
        return true;
      })
      .catch((error) => {
        if (showInChat) {
          addMessage("assistant", t("resume.failed", { error: error.message }));
        }
        throw error;
      });
  }

  document.querySelectorAll("[data-action='resume']").forEach((button) => {
    button.addEventListener("click", () => {
      resumeRobot().catch(() => {});
    });
  });

  /* ── AI Motion and Camera (Agent View) ───────────────── */

  if (elements.armAi) {
    elements.armAi.addEventListener("click", (event) => {
      const armed = event.currentTarget.dataset.armed === "true";
      if (armed) {
        send("disarm_chat_motion")
          .then(() => updateAiMotion(false))
          .catch(() => {});
        return;
      }
      if (!window.confirm(t("motion.armConfirm"))) {
        return;
      }
      send("arm_chat_motion", { confirmed: true })
        .then(() => updateAiMotion(true))
        .catch(() => {});
    });
  }

  function updateAiMotion(armed) {
    const button = elements.armAi;
    if (!button) return;
    button.dataset.armed = String(armed);
    const label = document.createElement("span");
    label.dataset.i18n = armed ? "motion.disarm" : "motion.arm";
    label.textContent = armed ? t("motion.disarm") : t("motion.arm");
    const strong = button.querySelector("strong");
    const existingSpan = button.querySelector("span");
    if (existingSpan) existingSpan.textContent = armed ? t("motion.disarm") : t("motion.arm");
    button.setAttribute("aria-pressed", String(armed));
  }

  if (elements.armAiCamera) {
    elements.armAiCamera.addEventListener("click", (event) => {
      const granted = event.currentTarget.dataset.granted === "true";
      if (granted) {
        send("revoke_chat_camera")
          .then(() => updateAiCamera(false))
          .catch(() => {});
        return;
      }
      if (!window.confirm(t("camera.armConfirm"))) {
        return;
      }
      send("grant_chat_camera", { confirmed: true })
        .then((data) => {
          updateAiCamera(true);
          toast(t("chat.cameraGranted", { sequence: data.grant_sequence }));
        })
        .catch(() => {});
    });
  }

  function updateAiCamera(granted) {
    const button = elements.armAiCamera;
    if (!button) return;
    button.dataset.granted = String(granted);
    const span = button.querySelector("span");
    if (span) span.textContent = granted ? t("camera.armed") : t("camera.arm");
    button.setAttribute("aria-pressed", String(granted));
  }

  /* ── Game Pad Camera Button (B) ──────────────────────── */

  if (elements.gamepadCamera) {
    elements.gamepadCamera.addEventListener("click", () => {
      send("camera")
        .then((data) => {
          showCameraPreview(data.jpeg_base64);
        })
        .catch(() => {});
    });
  }

  /* ── Game Pad Greeting Button (A) ────────────────────── */

  document.querySelectorAll("[data-behavior]").forEach((button) => {
    button.addEventListener("click", () => {
      send("behavior", { name: button.dataset.behavior }).catch(() => {});
    });
  });

  /* ── Camera Preview ──────────────────────────────────── */

  function showCameraPreview(jpegBase64) {
    elements.cameraImage.src = `data:image/jpeg;base64,${jpegBase64}`;
    elements.preview.classList.remove("hidden");
    window.clearTimeout(state.previewTimer);
    state.previewTimer = window.setTimeout(clearPreview, 15000);
  }

  function clearPreview() {
    window.clearTimeout(state.previewTimer);
    elements.cameraImage.removeAttribute("src");
    elements.preview.classList.add("hidden");
  }

  document.querySelector("#closePreviewButton").addEventListener("click", clearPreview);

  /* ── Voice Input ─────────────────────────────────────── */

  function updateVoiceInput(status = {}) {
    const enabled = status.enabled === true && status.state !== "disabled";
    state.voiceEnabled = enabled;
    elements.voiceInput.dataset.state =
      typeof status.state === "string" ? status.state : "disabled";
    elements.voiceInput.dataset.enabled = String(enabled);
    elements.voiceInput.setAttribute("aria-pressed", String(enabled));
    elements.voiceInput.classList.toggle("recording", enabled);
    elements.voiceInput.querySelector("strong").textContent = enabled
      ? t("voice.titleOn")
      : t("voice.title");
    const stateLabel = typeof status.state === "string" ? status.state : "disabled";
    elements.voiceInput.querySelector("small").textContent = t("voice.status", {
      state: stateLabel,
    });
  }

  elements.voiceInput.addEventListener("click", () => {
    const request = state.voiceEnabled ? "voice_disable" : "voice_enable";
    send(request)
      .then((data) => updateVoiceInput(data))
      .catch(() => {});
  });

  /* ── Speech Recognition (Web Mic) ────────────────────── */

  function configureSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      elements.webMic.disabled = true;
      elements.webMic.querySelector("small").textContent = t("speech.notSupported");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onstart = () => {
      state.recognitionActive = true;
      elements.webMic.classList.add("recording");
      elements.webMic.querySelector("strong").textContent = t("speech.stop");
    };
    recognition.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
      }
      elements.chatInput.value = transcript.trim();
      if (event.results[event.results.length - 1].isFinal && transcript.trim()) {
        elements.chatInput.focus();
        toast(t("speech.added"));
      }
    };
    recognition.onerror = (event) => {
      const messages = {
        "not-allowed": t("error.permissionDenied"),
        "service-not-allowed": t("error.speechUnavailable"),
        "audio-capture": t("error.noBrowserMic"),
        "no-speech": t("error.noSpeech"),
        network: t("error.speechNetwork"),
      };
      const message =
        messages[event.error] || t("error.browserMic", { error: event.error });
      log(message, "error");
      toast(message);
    };
    recognition.onend = () => {
      state.recognitionActive = false;
      elements.webMic.classList.remove("recording");
      elements.webMic.querySelector("strong").textContent = t("browserMic.title");
    };
    state.recognition = recognition;
    elements.webMic.addEventListener("click", () => {
      if (state.recognitionActive) {
        recognition.stop();
        return;
      }
      recognition.lang = SPEECH_LOCALES[state.locale];
      try {
        recognition.start();
      } catch (error) {
        const message = t("error.browserMicStart", { error: error.message });
        log(message, "error");
        toast(message);
      }
    });
  }

  /* ── Speech On/Off Toggle ────────────────────────────── */

  let speechStatusPending = false;
  async function refreshSpeechState() {
    if (speechStatusPending || !state.leaseId || document.hidden) return;
    speechStatusPending = true;
    try {
      showSpeechState(await send("speech", { operation: "status" }));
    } catch {
      // A dropped connection is already reported by the connection badge.
    } finally {
      speechStatusPending = false;
    }
  }
  window.setInterval(refreshSpeechState, 5000);

  function showSpeechState(result) {
    const data = result.data || result;
    const enabled = data.enabled === true;
    if (elements.speechOn) {
      elements.speechOn.setAttribute("aria-pressed", String(enabled));
      const detail = elements.speechOn.querySelector("small");
      if (detail) detail.textContent = enabled ? t("speech.enabled") : t("speech.disabled");
    }
    document.querySelector("#speechResult").textContent = enabled
      ? t("speech.enabled") : t("speech.disabled");
  }

  if (elements.speechOn) {
    elements.speechOn.addEventListener("click", async () => {
      try {
        const pressed = elements.speechOn.getAttribute("aria-pressed") === "true";
        const operation = pressed ? "off" : "on";
        const result = await send("speech", { operation });
        showSpeechState(result);
        refreshSpeechState();
      } catch (error) {
        document.querySelector("#speechResult").textContent = t("speech.unavailable");
        log(error.message || String(error), "error");
      }
    });
  }

  /* ── Chat ────────────────────────────────────────────── */

  elements.chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitChat(elements.chatInput.value);
  });

  function submitChat(rawText) {
    const text = rawText.trim();
    if (!text) return;
    elements.chatInput.value = "";
    addMessage("user", text);
    if (text === "/resume") {
      resumeRobot(true).catch(() => {});
      return;
    }
    if (text === "/camera") {
      send("grant_chat_camera", { confirmed: true })
        .then((data) => {
          updateAiCamera(true);
          addMessage(
            "assistant",
            t("chat.cameraGranted", { sequence: data.grant_sequence }),
          );
        })
        .catch(() => {});
      return;
    }
    send("chat", { text }).catch(() => {});
  }

  elements.chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.chatForm.requestSubmit();
    }
  });

  /* ── Clear Message (preserves streaming safety) ──────── */

  document.querySelector("#clearChatButton").addEventListener("click", () => {
    state.displayGeneration += 1;
    elements.chatMessages.replaceChildren();
  });
  document.querySelector("#clearLogButton").addEventListener("click", () => {
    elements.log.replaceChildren();
  });

  /* ── User-created Behaviors ──────────────────────────── */

  async function loadUserBehaviors() {
    try {
      const result = await send("user_behaviors_list");
      const behaviors = result.behaviors || [];
      elements.userBehaviorSelect.replaceChildren();
      if (behaviors.length === 0) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = t("behavior.user.empty");
        elements.userBehaviorSelect.append(option);
        elements.playBehavior.disabled = true;
      } else {
        for (const behavior of behaviors) {
          const option = document.createElement("option");
          option.value = behavior.name;
          option.textContent = behavior.name.replace(/_/g, " ");
          if (behavior.contains_motion) option.dataset.motion = "true";
          elements.userBehaviorSelect.append(option);
        }
        elements.playBehavior.disabled = false;
      }
    } catch {
      // Silent — behavior list is best-effort.
    }
  }

  elements.playBehavior.addEventListener("click", async () => {
    const name = elements.userBehaviorSelect.value;
    if (!name) return;
    const selected = elements.userBehaviorSelect.selectedOptions[0];
    if (selected?.dataset.motion === "true") {
      if (!window.confirm(t("behavior.user.confirmMotion"))) return;
    }
    try {
      elements.playBehavior.disabled = true;
      await send("user_behavior_run", { name });
    } catch (error) {
      toast(error.message || t("behavior.user.error"));
    } finally {
      elements.playBehavior.disabled = !elements.userBehaviorSelect.value;
    }
  });

  /* ── Power Off ───────────────────────────────────────── */

  function updatePoweroffAvailability() {
    elements.powerOff.disabled =
      !state.poweroffEnabled || !state.poweroffAuthorized || !state.leaseId;
    elements.powerAvailability.textContent =
      state.poweroffEnabled && state.poweroffAuthorized
      ? t("power.enabled")
      : t("power.disabled");
  }

  function focusableElements(container) {
    return Array.from(
      container.querySelectorAll(
        'button:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((node) => !node.hidden);
  }

  function openMenu() {
    state.previousFocus = document.activeElement;
    elements.menu.classList.remove("hidden");
    elements.menuButton.setAttribute("aria-expanded", "true");
    document.body.classList.add("modal-open");
    elements.closeMenu.focus();
  }

  function closeMenu({ restoreFocus = true } = {}) {
    elements.menu.classList.add("hidden");
    elements.menuButton.setAttribute("aria-expanded", "false");
    if (elements.powerDialog.classList.contains("hidden")) {
      document.body.classList.remove("modal-open");
    }
    if (restoreFocus && state.previousFocus instanceof HTMLElement) {
      state.previousFocus.focus();
    }
  }

  function showPowerDialog() {
    closeMenu({ restoreFocus: false });
    elements.powerDialog.classList.remove("hidden");
    document.body.classList.add("modal-open");
    elements.cancelPowerOff.focus();
  }

  function closePowerDialog() {
    state.poweroffNonce = null;
    elements.powerDialog.classList.add("hidden");
    document.body.classList.remove("modal-open");
    elements.powerOff.focus();
  }

  function trapDialogFocus(event, container) {
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

  elements.menuButton.addEventListener("click", openMenu);
  elements.closeMenu.addEventListener("click", () => closeMenu());
  elements.menu.addEventListener("click", (event) => {
    if (event.target === elements.menu) closeMenu();
  });
  elements.language.addEventListener("change", () => {
    setLocale(elements.language.value).catch((error) => {
      log(String(error), "error");
    });
  });

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

  elements.cancelPowerOff.addEventListener("click", closePowerDialog);
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
        elements.powerDialog.classList.add("hidden");
        document.body.classList.remove("modal-open");
        toast(t("power.shuttingDown"));
        setConnection("power.shuttingDown", "badge-wait");
      })
      .catch(() => {
        closePowerDialog();
      })
      .finally(() => {
        elements.cancelPowerOff.disabled = false;
        elements.confirmPowerOff.disabled = false;
      });
  });

  /* ── Keyboard ────────────────────────────────────────── */

  document.addEventListener("keydown", (event) => {
    if (!elements.powerDialog.classList.contains("hidden")) {
      if (event.key === "Escape") closePowerDialog();
      else trapDialogFocus(event, elements.powerDialog);
      return;
    }
    if (!elements.menu.classList.contains("hidden")) {
      if (event.key === "Escape") closeMenu();
      else trapDialogFocus(event, elements.menu);
    }
  });

  /* ── Activity Drawer ─────────────────────────────────── */

  function setActivityDrawer(open) {
    elements.activityDrawer.classList.toggle("open", open);
    elements.activityToggle.setAttribute("aria-expanded", String(open));
  }

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

  /* ── Viewport ────────────────────────────────────────── */

  function syncViewportHeight() {
    const height = window.visualViewport?.height || window.innerHeight;
    // The keyboard changes viewport proportions, not the physical orientation.
    const orientation = window.screen.orientation?.type;
    const landscape = orientation ? orientation.startsWith("landscape")
      : window.screen.width > window.screen.height;
    document.body.classList.toggle("physical-landscape", landscape);
    document.documentElement.style.setProperty("--app-height", `${height}px`);
  }
  window.addEventListener("resize", syncViewportHeight);
  window.visualViewport?.addEventListener("resize", syncViewportHeight);

  window.addEventListener("pagehide", () => {
    stopMovement();
    window.clearInterval(state.heartbeatTimer);
  });

  /* ── Standalone / Fullscreen ─────────────────────────── */

  function standaloneDisplay() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true
    );
  }

  async function requestControllerFullscreen() {
    if (standaloneDisplay() || document.fullscreenElement) return;
    const root = document.documentElement;
    const requestFullscreen = root.requestFullscreen || root.webkitRequestFullscreen;
    if (!requestFullscreen) {
      log(
        t("start.fullscreenHelp"),
      );
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

  async function startController() {
    if (state.controllerStarted) return;
    state.controllerStarted = true;
    await requestControllerFullscreen();
    elements.startOverlay.classList.add("started");
    switchView(state.interfaceMode);
    connect();
  }

  elements.startController.addEventListener("click", () => {
    startController().catch((error) => {
      state.controllerStarted = false;
      log(`${t("error.controllerStart")} ${error.message}`, "error");
      toast(t("error.controllerStart"));
    });
  });

  /* ── Initialization ──────────────────────────────────── */

  await setLocale(state.locale);
  syncViewportHeight();
  configureSpeechRecognition();
  if (standaloneDisplay()) {
    elements.startOverlay.classList.add("started");
    state.controllerStarted = true;
    switchView(state.interfaceMode);
    connect();
  }
})();
