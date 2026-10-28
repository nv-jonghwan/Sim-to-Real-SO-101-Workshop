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
    text("groot-repeat-label", `Repeat for ${format(steps)} updates`);
    text("groot-effective-batch", format(effective));
    text("groot-batch-equation", `= ${batch} × ${gpus} GPU process${gpus === 1 ? "" : "es"}`);
    text("groot-total-windows", format(effective * steps));
    text("groot-total-equation", `= ${format(effective)} × ${format(steps)} updates`);
  }

  function updateInference() {
    const horizon = Number(el("groot-horizon").value);
    const coverage = Math.round(horizon / 30 * 1000);
    text("groot-horizon-value", horizon);
    text("groot-prefix-label", `Execute ${horizon} action${horizon === 1 ? "" : "s"}`);
    text("groot-coverage", `${coverage} ms`);
    text("groot-coverage-equation", `= ${horizon} action${horizon === 1 ? "" : "s"} ÷ 30 Hz`);
    text("groot-tail", `${(30 / horizon).toFixed(2)} predictions per second. The robot still executes 30 actions per second.`);
    const timeline = el("groot-action-window");
    timeline.setAttribute("aria-label", `32 actions at 30 Hz. New prediction every ${horizon} actions, or ${coverage} milliseconds; ${(30/horizon).toFixed(2)} predictions per second.`);
    [...timeline.children].forEach((step, index) => {
      const start = index % horizon === 0;
      step.classList.toggle("prediction-start", start);
      step.classList.toggle("alternate-chunk", Math.floor(index / horizon) % 2 === 1);
      step.textContent = start ? "▼" : "·";
      step.title = `Action ${index+1} at ${(index/30).toFixed(2)} s${start ? ": new prediction" : ""}`;
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
