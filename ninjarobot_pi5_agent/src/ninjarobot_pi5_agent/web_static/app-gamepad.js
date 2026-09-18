"use strict";

import {
  state,
  elements,
  t,
  send,
  log,
  toast,
  showCameraPreview,
  initShared,
  registerMessageHandlers,
  attachPressState,
} from "./app-shared.js";

/* ── D-pad Movement ──────────────────────────────────── */

let movementGeneration = 0;

export function startMovement(button, event) {
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

export function stopMovement(event) {
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
window.addEventListener("pagehide", stopMovement);

/* ── Game Pad Greeting Button (A) ────────────────────── */

document.querySelectorAll("[data-behavior]").forEach((button) => {
  button.addEventListener("click", () => {
    send("behavior", { name: button.dataset.behavior }).catch(() => {});
  });
});

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

/* ── User-created Behaviors ──────────────────────────── */

export async function loadUserBehaviors() {
  try {
    const result = await send("user_behaviors_list");
    const behaviors = result.behaviors || [];
    if (!elements.userBehaviorSelect) return;
    elements.userBehaviorSelect.replaceChildren();
    if (behaviors.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = t("behavior.user.empty");
      elements.userBehaviorSelect.append(option);
      if (elements.playBehavior) elements.playBehavior.disabled = true;
    } else {
      for (const behavior of behaviors) {
        const option = document.createElement("option");
        option.value = behavior.name;
        option.textContent = behavior.name.replace(/_/g, " ");
        if (behavior.contains_motion) option.dataset.motion = "true";
        elements.userBehaviorSelect.append(option);
      }
      if (elements.playBehavior) elements.playBehavior.disabled = false;
    }
  } catch {
    // Silent — best-effort
  }
}

if (elements.playBehavior && elements.userBehaviorSelect) {
  attachPressState(elements.playBehavior);
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
}

/* ── Message Handlers ────────────────────────────────── */

registerMessageHandlers({
  onLease: () => {
    loadUserBehaviors();
  },
  onEmergencyStop: () => {
    stopMovement();
  },
});

localStorage.setItem("ninjarobotInterface", "gamepad");
await initShared({ pageName: "gamepad" });
