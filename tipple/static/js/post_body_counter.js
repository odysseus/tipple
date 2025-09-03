(() => {
  // tipple/static/ts/post_body_counter.ts
  function initPostBodyCounter(bodyId, counterId) {
    const ta = document.getElementById(bodyId);
    const counter = document.getElementById(counterId);
    if (!ta || !counter) return;
    const update = () => {
      const len = (ta.value ?? "").length;
      counter.textContent = String(len);
    };
    ta.addEventListener("input", update);
    update();
  }
  window.tipple = Object.assign({}, window.tipple, { initPostBodyCounter });
})();
