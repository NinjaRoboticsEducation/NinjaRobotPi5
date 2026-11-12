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

let stopWebMicSession = null;

export function submitChat(rawText) {
  const text = rawText.trim();
  if (!text) return;
  if (typeof stopWebMicSession === "function") {
    stopWebMicSession({ abort: true });
  }
  if (elements.chatInput) elements.chatInput.value = "";
  addMessage("user", text);
  if (text === "/resume") {
    resumeRobot(true).catch(() => {});
    return;
  }
  if (text === "/arm") {
    if (!window.confirm(t("motion.armConfirm"))) {
      return;
    }
    send("arm_chat_motion", { confirmed: true })
      .then(() => {
        updateAiMotion(true);
        addMessage("assistant", t("motion.disarm"));
      })
      .catch(() => {});
    return;
  }
  if (text === "/disarm") {
    send("disarm_chat_motion")
      .then(() => {
        updateAiMotion(false);
        addMessage("assistant", t("motion.arm"));
      })
      .catch(() => {});
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

/* ── Special Robot Controls (X Emergency, Y Resume) ───── */

export function updateEmergencyStop(active) {
  const button = elements.emergencyStop || document.querySelector("#emergencyStopButton");
  if (!button) return;
  button.setAttribute("aria-pressed", String(active));
}

export function updateResumeMovement(active) {
  const button = elements.resumeMovement || document.querySelector("#resumeMovementButton");
  if (!button) return;
  button.setAttribute("aria-pressed", String(active));
}

const emergencyBtn = elements.emergencyStop || document.querySelector("#emergencyStopButton");
if (emergencyBtn) {
  emergencyBtn.addEventListener("click", async () => {
    const isAlreadyStopped = emergencyBtn.getAttribute("aria-pressed") === "true";
    if (isAlreadyStopped) {
      try {
        const resumed = await resumeRobot(true);
        if (resumed) {
          updateEmergencyStop(false);
          updateResumeMovement(true);
          updateAiMotion(false);
        }
      } catch {
        // cancelled or failed
      }
      return;
    }
    try {
      await send("emergency_stop");
      updateEmergencyStop(true);
      updateResumeMovement(false);
      updateAiMotion(false);
      updateAiCamera(false);
      toast(t("behavior.emergencyComplete"));
    } catch {
      // error handled by send
    }
  });
}

const resumeBtn = elements.resumeMovement || document.querySelector("#resumeMovementButton");
if (resumeBtn) {
  resumeBtn.addEventListener("click", async () => {
    const isAlreadyResumed = resumeBtn.getAttribute("aria-pressed") === "true";
    if (isAlreadyResumed) {
      updateResumeMovement(false);
      return;
    }
    try {
      const resumed = await resumeRobot(true);
      if (resumed) {
        updateResumeMovement(true);
        updateEmergencyStop(false);
        updateAiMotion(false);
      }
    } catch {
      // cancelled or failed
    }
  });
}

/* ── Voice Input (USB Mic) ───────────────────────────── */

export function updateVoiceInput(status = {}) {
  if (!elements.voiceInput) return;
  const enabled =
    status.enabled === true &&
    status.state !== "disabled" &&
    status.state !== "failed" &&
    status.state !== "stopped";
  state.voiceEnabled = enabled;
  elements.voiceInput.dataset.state =
    typeof status.state === "string" ? status.state : "disabled";
  elements.voiceInput.dataset.enabled = String(enabled);
  elements.voiceInput.setAttribute("aria-pressed", String(enabled));
  elements.voiceInput.classList.toggle("recording", enabled);
}

if (elements.voiceInput) {
  elements.voiceInput.addEventListener("click", () => {
    const request = state.voiceEnabled ? "voice_disable" : "voice_enable";
    send(request)
      .then((data) => updateVoiceInput(data))
      .catch((error) => {
        const message = String(error?.message || error);
        log(message, "error");
        toast(message);
      });
  });
}

/* ── Speech Recognition (Web Mic) ────────────────────── */

export function configureSpeechRecognition() {
  if (!elements.webMic) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let pttRecording = false;

  function resetWebMicButton() {
    if (!elements.webMic) return;
    elements.webMic.setAttribute("aria-pressed", "false");
    elements.webMic.classList.remove("recording");
    const strong = elements.webMic.querySelector("strong");
    if (strong) strong.textContent = t("browserMic.title");
  }

  async function toggleRobotPushToTalk() {
    if (pttRecording) {
      pttRecording = false;
      send("usb_microphone_stop").catch(() => {});
      return;
    }
    pttRecording = true;
    elements.webMic.setAttribute("aria-pressed", "true");
    elements.webMic.classList.add("recording");
    const strong = elements.webMic.querySelector("strong");
    if (strong) strong.textContent = t("speech.stop");
    try {
      const result = await send("usb_microphone", {
        duration_seconds: 5,
        language: state.locale || "auto",
      });
      const text = String(result?.transcript || result?.data?.transcript || "").trim();
      if (text) {
        const prefix = elements.chatInput.value.trim();
        elements.chatInput.value = prefix ? `${prefix} ${text}` : text;
        elements.chatInput.focus();
        toast(t("speech.added"));
      }
    } catch (error) {
      const message = String(error?.message || error);
      log(message, "error");
      toast(message);
    } finally {
      pttRecording = false;
      resetWebMicButton();
    }
  }

  if (!SpeechRecognition) {
    elements.webMic.addEventListener("click", () => {
      toggleRobotPushToTalk();
    });
    return;
  }

  let phase = "IDLE";
  let pendingStart = false;
  let cancelled = false;
  let initialPrefix = "";

  function stopActiveRecognition({ abort = false } = {}) {
    pendingStart = false;
    cancelled = abort;
    const active = state.recognition;
    if (!active) return;
    phase = "STOPPING";
    state.recognitionActive = false;
    resetWebMicButton();
    try {
      if (abort && typeof active.abort === "function") {
        active.abort();
      } else {
        active.stop();
      }
    } catch {
      // Ignore errors when stopping an already closed session.
    }
  }

  stopWebMicSession = stopActiveRecognition;

  function createRecognitionSession() {
    const recognition = new SpeechRecognition();
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.lang = SPEECH_LOCALES[state.locale] || "en-US";
    recognition.onstart = () => {
      if (state.recognition !== recognition) return;
      if (phase === "STOPPING") return;
      phase = "RECORDING";
      state.recognitionActive = true;
      if (elements.webMic) {
        elements.webMic.setAttribute("aria-pressed", "true");
        elements.webMic.classList.add("recording");
        const strong = elements.webMic.querySelector("strong");
        if (strong) strong.textContent = t("speech.stop");
      }
    };
    recognition.onresult = (event) => {
      if (state.recognition !== recognition || cancelled) return;
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
      }
      const clean = transcript.trim();
      elements.chatInput.value =
        initialPrefix && clean ? `${initialPrefix} ${clean}` : clean || initialPrefix;
      if (event.results[event.results.length - 1].isFinal && clean) {
        elements.chatInput.focus();
        toast(t("speech.added"));
        phase = "STOPPING";
        state.recognitionActive = false;
        resetWebMicButton();
      }
    };
    recognition.onerror = (event) => {
      if (state.recognition !== recognition) return;
      const errorCode = event?.error;
      const expectedAbort = cancelled && errorCode === "aborted";
      phase = "STOPPING";
      state.recognitionActive = false;
      resetWebMicButton();
      if (expectedAbort) return;
      pendingStart = false;
      const messages = {
        "not-allowed": t("error.permissionDenied"),
        "service-not-allowed": t("error.speechUnavailable"),
        "audio-capture": t("error.noBrowserMic"),
        "no-speech": t("error.noSpeech"),
        network: t("error.speechNetwork"),
      };
      const message =
        messages[errorCode] || t("error.browserMic", { error: errorCode });
      log(message, "error");
      toast(message);
    };
    recognition.onend = () => {
      if (state.recognition !== recognition) return;
      state.recognition = null;
      phase = "IDLE";
      state.recognitionActive = false;
      resetWebMicButton();
      if (pendingStart && !document.hidden) {
        pendingStart = false;
        startRecognition();
      }
    };
    return recognition;
  }

  function startRecognition() {
    initialPrefix = elements.chatInput.value.trim();
    cancelled = false;
    const recognition = createRecognitionSession();
    state.recognition = recognition;
    try {
      phase = "STARTING";
      recognition.start();
    } catch (error) {
      state.recognition = null;
      phase = "IDLE";
      resetWebMicButton();
      const message = t("error.browserMicStart", { error: error.message });
      log(message, "error");
      toast(message);
    }
  }

  elements.webMic.addEventListener("click", () => {
    if (phase === "STOPPING") {
      pendingStart = !pendingStart;
      elements.webMic.setAttribute("aria-pressed", String(pendingStart));
    } else if (phase !== "IDLE") {
      stopActiveRecognition();
    } else {
      startRecognition();
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopActiveRecognition({ abort: true });
  });
  window.addEventListener("pagehide", () => stopActiveRecognition({ abort: true }));

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
    elements.speechOn.dataset.speech = enabled ? "on" : "off";
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
    stopWebMicSession?.({ abort: true });
    updateAiMotion(false);
    updateAiCamera(false);
  },
  onEmergencyStop: () => {
    updateAiMotion(false);
    updateAiCamera(false);
    updateEmergencyStop(true);
    updateResumeMovement(false);
  },
  onChatResumeSuccess: (message) => {
    updateEmergencyStop(false);
    updateResumeMovement(true);
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
