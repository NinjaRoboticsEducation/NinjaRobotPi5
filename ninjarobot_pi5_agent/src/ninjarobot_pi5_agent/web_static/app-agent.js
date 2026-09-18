"use strict";

import {
  state,
  elements,
  t,
  send,
  log,
  toast,
  showCameraPreview,
  resumeRobot,
  initShared,
  registerMessageHandlers,
  attachPressState,
  SPEECH_LOCALES,
} from "./app-shared.js";

/* ── Chat Messages ───────────────────────────────────── */

export function addMessage(role, text = "") {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = text;
  node.dataset.generation = String(state.displayGeneration);
  if (elements.chatMessages) {
    elements.chatMessages.append(node);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
  }
  return node;
}

/* ── Chat Submission ─────────────────────────────────── */

export function submitChat(rawText) {
  const text = rawText.trim();
  if (!text) return;
  if (elements.chatInput) elements.chatInput.value = "";
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

if (elements.chatForm) {
  elements.chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (elements.chatInput) submitChat(elements.chatInput.value);
  });

  const sendBtn = elements.chatForm.querySelector('button[type="submit"]');
  if (sendBtn) attachPressState(sendBtn);
}

if (elements.chatInput) {
  elements.chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.chatForm?.requestSubmit();
    }
  });
}

const clearChatBtn = document.querySelector("#clearChatButton");
if (clearChatBtn) {
  clearChatBtn.addEventListener("click", () => {
    state.displayGeneration += 1;
    elements.chatMessages?.replaceChildren();
  });
}

/* ── AI Motion & Camera Controls ─────────────────────── */

export function updateAiMotion(armed) {
  const button = elements.armAi;
  if (!button) return;
  button.dataset.armed = String(armed);
  const span = button.querySelector("span");
  if (span) span.textContent = armed ? t("motion.disarm") : t("motion.arm");
  button.setAttribute("aria-pressed", String(armed));
}

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

export function updateAiCamera(granted) {
  const button = elements.armAiCamera;
  if (!button) return;
  button.dataset.granted = String(granted);
  const span = button.querySelector("span");
  if (span) span.textContent = granted ? t("camera.armed") : t("camera.arm");
  button.setAttribute("aria-pressed", String(granted));
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

/* ── Voice Input (USB Mic) ───────────────────────────── */

export function updateVoiceInput(status = {}) {
  if (!elements.voiceInput) return;
  const enabled = status.enabled === true && status.state !== "disabled";
  state.voiceEnabled = enabled;
  elements.voiceInput.dataset.state =
    typeof status.state === "string" ? status.state : "disabled";
  elements.voiceInput.dataset.enabled = String(enabled);
  elements.voiceInput.setAttribute("aria-pressed", String(enabled));
  elements.voiceInput.classList.toggle("recording", enabled);
  const strong = elements.voiceInput.querySelector("strong");
  if (strong) {
    strong.textContent = enabled ? t("voice.titleOn") : t("voice.title");
  }
  const stateLabel = typeof status.state === "string" ? status.state : "disabled";
  const small = elements.voiceInput.querySelector("small");
  if (small) {
    small.textContent = t("voice.status", { state: stateLabel });
  }
}

if (elements.voiceInput) {
  elements.voiceInput.addEventListener("click", () => {
    const request = state.voiceEnabled ? "voice_disable" : "voice_enable";
    send(request)
      .then((data) => updateVoiceInput(data))
      .catch(() => {});
  });
}

/* ── Speech Recognition (Web Mic) ────────────────────── */

export function configureSpeechRecognition() {
  if (!elements.webMic) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    elements.webMic.disabled = true;
    const small = elements.webMic.querySelector("small");
    if (small) small.textContent = t("speech.notSupported");
    return;
  }
  const recognition = new SpeechRecognition();
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition.onstart = () => {
    state.recognitionActive = true;
    elements.webMic.classList.add("recording");
    const strong = elements.webMic.querySelector("strong");
    if (strong) strong.textContent = t("speech.stop");
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
    const strong = elements.webMic.querySelector("strong");
    if (strong) strong.textContent = t("browserMic.title");
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
export async function refreshSpeechState() {
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

export function showSpeechState(result) {
  const data = result.data || result;
  const enabled = data.enabled === true;
  if (elements.speechOn) {
    elements.speechOn.setAttribute("aria-pressed", String(enabled));
    const detail = elements.speechOn.querySelector("small");
    if (detail) detail.textContent = enabled ? t("speech.enabled") : t("speech.disabled");
  }
  const resultEl = document.querySelector("#speechResult");
  if (resultEl) {
    resultEl.textContent = enabled ? t("speech.enabled") : t("speech.disabled");
  }
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
      const resultEl = document.querySelector("#speechResult");
      if (resultEl) resultEl.textContent = t("speech.unavailable");
      log(error.message || String(error), "error");
    }
  });
}

/* ── Message Handlers ────────────────────────────────── */

registerMessageHandlers({
  onLease: () => {
    refreshSpeechState();
  },
  onClose: () => {
    updateAiCamera(false);
  },
  onEmergencyStop: () => {
    updateAiMotion(false);
    updateAiCamera(false);
  },
  onChatResumeSuccess: (message) => {
    updateAiMotion(false);
    addMessage("assistant", message);
  },
  onChatResumeFailed: (errorText) => {
    addMessage("assistant", errorText);
  },
  onChatResumeCancelled: () => {
    addMessage("assistant", t("resume.cancelled"));
  },
  onConversationHistory: (message) => {
    if (!elements.chatMessages) return;
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
  },
  onChatDelta: (message) => {
    let node = state.activeAssistant.get(message.request_id);
    if (!node) {
      node = addMessage("assistant");
      state.activeAssistant.set(message.request_id, node);
    }
    if (Number(node.dataset.generation) < state.displayGeneration) return;
    node.textContent += message.text || "";
    if (elements.chatMessages) {
      elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    }
  },
  onResult: (message) => {
    const assistant = state.activeAssistant.get(message.request_id);
    if (assistant && !assistant.textContent.trim()) {
      assistant.textContent = message.data?.text || t("chat.noResponse");
    }
    state.activeAssistant.delete(message.request_id);
  },
  onError: (message) => {
    state.activeAssistant.delete(message.request_id);
  },
  onEvent: (event) => {
    if (
      event.event_type === "media" &&
      event.data?.kind === "camera_preview"
    ) {
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
  },
  onSystemStatus: (message) => {
    updateVoiceInput(message.data?.release?.voice);
  },
  applyTranslations: () => {
    if (elements.armAi) {
      updateAiMotion(elements.armAi.dataset.armed === "true");
    }
    if (elements.armAiCamera) {
      updateAiCamera(elements.armAiCamera.dataset.granted === "true");
    }
    if (elements.voiceInput) {
      updateVoiceInput({ enabled: state.voiceEnabled, state: elements.voiceInput.dataset.state });
    }
  },
});

configureSpeechRecognition();
window.setInterval(refreshSpeechState, 5000);

localStorage.setItem("ninjarobotInterface", "agent");
await initShared({ pageName: "agent" });
