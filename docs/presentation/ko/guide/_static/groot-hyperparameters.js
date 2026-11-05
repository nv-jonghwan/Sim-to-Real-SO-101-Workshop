(() => {
  "use strict";

  const training = document.getElementById("groot-training");
  const inference = document.getElementById("groot-inference");
  if (!training || !inference) return;

  const el = (id) => document.getElementById(id);
  const text = (id, value) => { el(id).textContent = value; };
  const format = (value) => value.toLocaleString("en-US");

  function updateTraining() {
    const batch = Number(el("groot-batch").value);
    const gpus = Number(el("groot-gpus").value);
    const steps = Number(el("groot-steps").value);
    const effective = batch * gpus;
    text("groot-batch-label", `${format(effective)} windows / update`);
    text("groot-repeat-label", `${format(steps)}번 update 반복`);
    text("groot-effective-batch", format(effective));
    text("groot-batch-equation", `= ${batch} × ${gpus} GPU process${gpus === 1 ? "" : "es"}`);
    text("groot-total-windows", format(effective * steps));
    text("groot-total-equation", `= ${format(effective)} × ${format(steps)} updates`);
  }

  function updateInference() {
    const horizon = Number(el("groot-horizon").value);
    const coverage = Math.round(horizon / 30 * 1000);
    text("groot-horizon-value", horizon);
    text("groot-prefix-label", `${horizon} action${horizon === 1 ? "" : "s"} 실행`);
    text("groot-coverage", `${coverage} ms`);
    text("groot-coverage-equation", `= ${horizon} action${horizon === 1 ? "" : "s"} ÷ 30 Hz`);
    text("groot-tail", `초당 ${(30 / horizon).toFixed(2)} predictions입니다. 로봇은 계속 초당 30 actions를 실행합니다.`);
    const timeline = el("groot-action-window");
    timeline.setAttribute("aria-label", `30 Hz에서 32 actions를 실행합니다. ${horizon} actions마다, 즉 ${coverage} ms마다 새 prediction을 수행하며, 초당 ${(30 / horizon).toFixed(2)} predictions입니다.`);
    [...timeline.children].forEach((step, index) => {
      const start = index % horizon === 0;
      step.classList.toggle("prediction-start", start);
      step.classList.toggle("alternate-chunk", Math.floor(index / horizon) % 2 === 1);
      step.textContent = start ? "▼" : "·";
      step.title = `Action ${index + 1}: ${(index / 30).toFixed(2)} s${start ? ": 새 prediction" : ""}`;
    });
  }

  training.addEventListener("change", updateTraining);
  inference.addEventListener("input", updateInference);
  training.querySelector("button").addEventListener("click", () => {
    el("groot-batch").value = "32";
    el("groot-gpus").value = "1";
    el("groot-steps").value = "20000";
    updateTraining();
  });
  inference.querySelector("button").addEventListener("click", () => {
    el("groot-horizon").value = "16";
    updateInference();
  });
  updateTraining();
  updateInference();
  [training, inference].forEach((section) => {
    section.querySelectorAll("[hidden]").forEach((control) => { control.hidden = false; });
  });
})();
