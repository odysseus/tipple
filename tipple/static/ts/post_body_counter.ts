// assets/ts/post_body_counter.ts

declare global {
  interface Window {
    tipple?: { initPostBodyCounter: (bodyId: string, counterId: string) => void };
  }
}

function initPostBodyCounter(bodyId: string, counterId: string): void {
  const ta = document.getElementById(bodyId) as HTMLTextAreaElement | null;
  const counter = document.getElementById(counterId) as HTMLElement | null;
  if (!ta || !counter) return;

  const update = () => {
    const len = (ta.value ?? "").length;
    counter.textContent = String(len);
  };

  ta.addEventListener("input", update);
  update();
}

// Expose a single init hook on window (safe merge)
window.tipple = Object.assign({}, window.tipple, { initPostBodyCounter });

export {}; // keep this a module
