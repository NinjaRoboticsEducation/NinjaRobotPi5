(() => {
  "use strict";

  const state = {
    socket: null,
    leaseId: null,
    reconnectToken: sessionStorage.getItem("ninjarobotReconnectToken"),
    heartbeatTimer: null,
    requestCounter: 0,
    pending: new Map(),
    activeAssistant: new Map(),
    usbRecording: false,
    recognition: null,
    recognitionActive: false,
    previewTimer: null,
    released: false,
    activeMoveButton: null,
    drawerDragged: false,
    controllerStarted: false,
    certificateHelpLogged: false,
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
    usbMic: document.querySelector("#usbMicButton"),
    webMic: document.querySelector("#webMicButton"),
    language: document.querySelector("#languageSelect"),
    preview: document.querySelector("#cameraPreview"),
    cameraImage: document.querySelector("#cameraImage"),
    activityDrawer: document.querySelector("#activityDrawer"),
    activityToggle: document.querySelector("#activityToggle"),
    startOverlay: document.querySelector("#startOverlay"),
    startController: document.querySelector("#startControllerButton"),
  };

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

  function setConnection(label, className) {
    elements.badge.textContent = label;
    elements.badge.className = `badge ${className}`;
  }

  function addMessage(role, text = "") {
    const node = document.createElement("div");
    node.className = `message ${role}`;
    node.textContent = text;
    elements.chatMessages.append(node);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    return node;
  }

  function send(type, payload = {}) {
    if (!state.socket || state.socket.readyState !== WebSocket.OPEN || !state.leaseId) {
      toast("The robot controller is not connected.");
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
            new Error(`${type} did not answer within ${responseTimeout / 1000} seconds`),
          );
        }
      }, responseTimeout);
    });
  }

  function connect() {
    state.released = false;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const query = state.reconnectToken
      ? `?reconnect_token=${encodeURIComponent(state.reconnectToken)}`
      : "";
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws${query}`);
    state.socket = socket;
    setConnection("Connecting", "badge-wait");

    socket.addEventListener("open", () => log("Secure controller connection opened."));
    socket.addEventListener("message", (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        log("The service returned malformed data.", "error");
        return;
      }
      handleMessage(message);
    });
    socket.addEventListener("close", (event) => {
      window.clearInterval(state.heartbeatTimer);
      state.heartbeatTimer = null;
      state.leaseId = null;
      updateAiCamera(false);
      setConnection(event.code === 4423 ? "Controller locked" : "Disconnected", "badge-wait");
      log(
        event.code === 4423
          ? "Another device currently controls NinjaRobot."
          : "Controller connection closed.",
        event.code === 4423 ? "error" : "info",
      );
      if (!state.released && event.code !== 4423) {
        window.setTimeout(connect, 1500);
      }
    });
    socket.addEventListener("error", () => {
      log("Could not establish the HTTPS WebSocket connection.", "error");
      if (!state.certificateHelpLogged) {
        state.certificateHelpLogged = true;
        log(
          "Chrome: accept the HTTPS warning for this exact address, then reload. Safari: install and trust the NinjaRobotPi5 Local CA. Run 'ninjarobot-agent web certificate-status' on the Pi for details.",
          "error",
        );
        toast("Secure connection failed. Open Live Activity for certificate help.");
      }
    });
  }

  function handleMessage(message) {
    if (message.type === "lease") {
      state.leaseId = message.lease_id;
      state.certificateHelpLogged = false;
      state.reconnectToken = message.reconnect_token;
      sessionStorage.setItem("ninjarobotReconnectToken", state.reconnectToken);
      setConnection("Controller active", "badge-ok");
      log("This device owns the exclusive controller lease.");
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
        : "provider status unavailable";
      const toolCount = Array.isArray(message.data?.tools) ? message.data.tools.length : 0;
      log(`System ready · ${providerText} · ${toolCount} tools`);
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
        addMessage("assistant", "Hello. NinjaRobotAgent is ready.");
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
      log(event.message || "Agent event", event.event_type === "error" ? "error" : "info");
      return;
    }
    if (message.type === "chat_delta") {
      let node = state.activeAssistant.get(message.request_id);
      if (!node) {
        node = addMessage("assistant");
        state.activeAssistant.set(message.request_id, node);
      }
      node.textContent += message.text || "";
      elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
      return;
    }
    if (message.type === "result") {
      settle(message.request_id, true, message.data);
      const assistant = state.activeAssistant.get(message.request_id);
      if (assistant && !assistant.textContent.trim()) {
        assistant.textContent = message.data?.text || "(No text response)";
      }
      state.activeAssistant.delete(message.request_id);
      return;
    }
    if (message.type === "error") {
      settle(message.request_id, false, new Error(message.error || "Request failed"));
      state.activeAssistant.delete(message.request_id);
      log(message.error || "Request failed.", "error");
      toast(message.error || "Request failed.");
    }
  }

  function settle(requestId, succeeded, value) {
    const pending = state.pending.get(requestId);
    if (!pending) return;
    state.pending.delete(requestId);
    if (succeeded) pending.resolve(value);
    else pending.reject(value);
  }

  function startMovement(button, event) {
    if (state.activeMoveButton) return;
    event.preventDefault();
    state.activeMoveButton = button;
    button.classList.add("active");
    send("move_start", { direction: button.dataset.direction }).catch((error) => {
      button.classList.remove("active");
      state.activeMoveButton = null;
      log(error.message, "error");
    });
  }

  function stopMovement(event) {
    if (event) event.preventDefault();
    const button = state.activeMoveButton;
    if (!button) return;
    state.activeMoveButton = null;
    button.classList.remove("active");
    send("move_stop").catch(() => {});
  }

  document.querySelectorAll(".dpad-button").forEach((button) => {
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

  document.querySelector("#emergencyButton").addEventListener("click", () => {
    send("emergency_stop")
      .then(() => {
        updateAiMotion(false);
        updateAiCamera(false);
        toast("Emergency stop completed.");
      })
      .catch(() => {});
  });

  function resumeRobot(showInChat = false) {
    if (!window.confirm("Health-check and resume all robot modules after the emergency stop?")) {
      if (showInChat) addMessage("assistant", "System resume was cancelled.");
      return Promise.resolve(false);
    }
    return send("resume", { confirmed: true })
      .then(() => {
        updateAiMotion(false);
        const message =
          "Robot modules resumed and Idle restored. AI motion remains disarmed; use Arm AI Motion before requesting servo movement.";
        if (showInChat) addMessage("assistant", message);
        toast("Robot modules resumed.");
        return true;
      })
      .catch((error) => {
        if (showInChat) addMessage("assistant", `Resume failed: ${error.message}`);
        throw error;
      });
  }

  document.querySelector("#resumeButton").addEventListener("click", () => {
    resumeRobot().catch(() => {});
  });

  document.querySelector("#greetingButton").addEventListener("click", () => {
    send("behavior", { name: "greeting" }).catch(() => {});
  });

  document.querySelector("#celebrateButton").addEventListener("click", () => {
    send("behavior", { name: "celebrate" }).catch(() => {});
  });

  document.querySelector("#armAiButton").addEventListener("click", (event) => {
    const armed = event.currentTarget.dataset.armed === "true";
    if (armed) {
      send("disarm_chat_motion")
        .then(() => updateAiMotion(false))
        .catch(() => {});
      return;
    }
    if (
      !window.confirm(
        "Allow natural-language requests to move the robot for this browser session?",
      )
    ) {
      return;
    }
    send("arm_chat_motion", { confirmed: true })
      .then(() => updateAiMotion(true))
      .catch(() => {});
  });

  function updateAiMotion(armed) {
    const button = elements.armAi;
    button.dataset.armed = String(armed);
    button.textContent = armed ? "Disarm AI motion" : "Arm AI motion";
    button.setAttribute("aria-pressed", String(armed));
  }

  document.querySelector("#armAiCameraButton").addEventListener("click", (event) => {
    const granted = event.currentTarget.dataset.granted === "true";
    if (granted) {
      send("revoke_chat_camera")
        .then(() => updateAiCamera(false))
        .catch(() => {});
      return;
    }
    if (
      !window.confirm(
        "Allow NinjaRobotAgent to take one temporary photo? The photo is not retained.",
      )
    ) {
      return;
    }
    send("grant_chat_camera", { confirmed: true })
      .then((data) => {
        updateAiCamera(true);
        toast(`AI camera grant #${data.grant_sequence} is ready for one photo.`);
      })
      .catch(() => {});
  });

  function updateAiCamera(granted) {
    const button = elements.armAiCamera;
    button.dataset.granted = String(granted);
    button.textContent = granted ? "AI camera ready" : "AI camera";
    button.setAttribute("aria-pressed", String(granted));
  }

  document.querySelector("#cameraButton").addEventListener("click", () => {
    send("camera")
      .then((data) => {
        showCameraPreview(data.jpeg_base64);
      })
      .catch(() => {});
  });

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

  elements.usbMic.addEventListener("click", () => {
    if (state.usbRecording) {
      send("usb_microphone_stop").catch(() => {});
      return;
    }
    state.usbRecording = true;
    elements.usbMic.classList.add("recording");
    elements.usbMic.querySelector("strong").textContent = "STOP USB MICROPHONE";
    const language = elements.language.value.startsWith("ja") ? "ja" : "en";
    send("usb_microphone", { duration_seconds: 5, language })
      .then((data) => {
        if (data.transcript) {
          elements.chatInput.value = data.transcript;
          submitChat(data.transcript);
        }
      })
      .catch(() => {})
      .finally(() => {
        state.usbRecording = false;
        elements.usbMic.classList.remove("recording");
        elements.usbMic.querySelector("strong").textContent = "USB MICROPHONE";
      });
  });

  function configureSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      elements.webMic.disabled = true;
      elements.webMic.querySelector("small").textContent = "Not supported by this browser";
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onstart = () => {
      state.recognitionActive = true;
      elements.webMic.classList.add("recording");
      elements.webMic.querySelector("strong").textContent = "STOP LISTENING";
    };
    recognition.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
      }
      elements.chatInput.value = transcript.trim();
      if (event.results[event.results.length - 1].isFinal && transcript.trim()) {
        elements.chatInput.focus();
        toast("Speech added to the message box. Review it, then tap Send.");
      }
    };
    recognition.onerror = (event) => {
      const messages = {
        "not-allowed": "Microphone permission was denied.",
        "service-not-allowed": "Browser speech recognition is unavailable on this device.",
        "audio-capture": "No working browser microphone was found.",
        "no-speech": "No speech was detected. Tap Web Microphone and try again.",
        network: "The browser speech service could not be reached.",
      };
      const message = messages[event.error] || `Browser microphone error: ${event.error}`;
      log(message, "error");
      toast(message);
    };
    recognition.onend = () => {
      state.recognitionActive = false;
      elements.webMic.classList.remove("recording");
      elements.webMic.querySelector("strong").textContent = "WEB MICROPHONE";
    };
    state.recognition = recognition;
    elements.webMic.addEventListener("click", () => {
      if (state.recognitionActive) {
        recognition.stop();
        return;
      }
      recognition.lang = elements.language.value;
      try {
        recognition.start();
      } catch (error) {
        const message = `Browser microphone could not start: ${error.message}`;
        log(message, "error");
        toast(message);
      }
    });
  }

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
            `AI camera grant #${data.grant_sequence} is ready for one temporary photo. ` +
              "Ask me to take a photo. You can use /camera again after it succeeds.",
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

  document.querySelector("#clearChatButton").addEventListener("click", () => {
    elements.chatMessages.replaceChildren();
  });
  document.querySelector("#clearLogButton").addEventListener("click", () => {
    elements.log.replaceChildren();
  });

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

  function syncViewportHeight() {
    const height = window.visualViewport?.height || window.innerHeight;
    document.documentElement.style.setProperty("--app-height", `${height}px`);
  }
  window.addEventListener("resize", syncViewportHeight);
  window.visualViewport?.addEventListener("resize", syncViewportHeight);

  window.addEventListener("pagehide", () => {
    stopMovement();
    window.clearInterval(state.heartbeatTimer);
  });

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
        "This browser does not offer page fullscreen. Use Add to Home Screen for a full-screen controller.",
      );
      return;
    }
    try {
      await requestFullscreen.call(root);
      if (window.screen.orientation?.lock) {
        await window.screen.orientation.lock("portrait").catch(() => {});
      }
    } catch (error) {
      log(`Full-screen mode was unavailable: ${error.message}`);
    }
  }

  async function startController() {
    if (state.controllerStarted) return;
    state.controllerStarted = true;
    await requestControllerFullscreen();
    elements.startOverlay.classList.add("started");
    connect();
  }

  elements.startController.addEventListener("click", () => {
    startController().catch((error) => {
      state.controllerStarted = false;
      log(`Controller could not start: ${error.message}`, "error");
      toast("Controller could not start.");
    });
  });

  syncViewportHeight();
  configureSpeechRecognition();
  if (standaloneDisplay()) {
    elements.startOverlay.classList.add("started");
    state.controllerStarted = true;
    connect();
  }
})();
