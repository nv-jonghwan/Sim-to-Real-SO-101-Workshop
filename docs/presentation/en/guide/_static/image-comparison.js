"use strict";

document.querySelectorAll(".image-comparison").forEach((root) => {
  const control = (name) => root.querySelector(`[data-control="${name}"]`);
  const stage = root.querySelector(".image-comparison-stage");
  const status = root.querySelector(".image-comparison-status");
  const images = Object.fromEntries(["real", "sim"].map((name) => [name, root.querySelector(`[data-image="${name}"] img`)]));
  const defaults = Object.fromEntries(Object.entries(images).map(([name, img]) => [name, {src: img.src, alt: img.alt}]));
  const urls = {};
  const requests = {real: 0, sim: 0};

  function update() {
    const ready = Object.values(images).every((img) => img.complete && img.naturalWidth);
    if (!ready) {
      control("opacity").disabled = true;
      status.textContent = "An image is unavailable. Load two saved images to compare.";
      return;
    }
    const equal = images.real.naturalWidth === images.sim.naturalWidth && images.real.naturalHeight === images.sim.naturalHeight;
    control("mode").querySelector('[value="overlay"]').disabled = !equal;
    if (!equal && control("mode").value === "overlay") control("mode").value = "side";
    stage.dataset.mode = control("mode").value;
    stage.style.setProperty("--sim-opacity", Number(control("opacity").value) / 100);
    control("opacity").disabled = !equal || stage.dataset.mode !== "overlay";
    control("value").textContent = `${control("opacity").value}%`;
    const dimensions = Object.entries(images).map(([name, img]) => `${name}: ${img.naturalWidth} × ${img.naturalHeight}`).join("; ");
    const labels = {overlay: "Overlay: real underneath, simulation on top", side: "Real left; simulation right", real: "Real only", sim: "Simulation only"};
    status.textContent = `${labels[stage.dataset.mode]}. ${dimensions}.${equal ? "" : " Overlay disabled: use images with matching pixel dimensions; do not stretch them to align."}`;
  }

  Object.values(images).forEach((img) => {
    img.addEventListener("load", update);
    img.addEventListener("error", update);
  });
  control("mode").addEventListener("change", update);
  control("opacity").addEventListener("input", update);
  control("toggle").addEventListener("click", () => {
    control("mode").value = control("mode").value === "real" ? "sim" : "real";
    update();
  });
  for (const name of ["real", "sim"]) {
    control(`${name}-file`).addEventListener("change", async (event) => {
      const file = event.target.files[0];
      if (!file) return;
      const request = ++requests[name];
      const url = URL.createObjectURL(file);
      const candidate = new Image();
      candidate.src = url;
      try {
        await candidate.decode();
        if (request !== requests[name]) { URL.revokeObjectURL(url); return; }
        if (urls[name]) URL.revokeObjectURL(urls[name]);
        urls[name] = url;
        images[name].src = url;
        images[name].alt = `Selected ${name} image: ${file.name}`;
        await images[name].decode();
        update();
      } catch {
        URL.revokeObjectURL(url);
        if (request === requests[name]) status.textContent = `Could not read the selected ${name} image. Choose a PNG, JPEG, or WebP file.`;
      }
    });
  }
  control("reset").addEventListener("click", () => {
    for (const name of ["real", "sim"]) {
      requests[name]++;
      if (urls[name]) { URL.revokeObjectURL(urls[name]); delete urls[name]; }
      images[name].src = defaults[name].src;
      images[name].alt = defaults[name].alt;
      control(`${name}-file`).value = "";
    }
    control("mode").value = "overlay";
    control("opacity").value = "50";
    Promise.all(Object.values(images).map((img) => img.decode())).then(update).catch(update);
  });
  root.querySelector(".image-comparison-controls").hidden = false;
  Promise.all(Object.values(images).map((img) => img.decode())).then(update).catch(update);
});
