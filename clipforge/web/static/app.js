/* ClipForge Web UI */

let currentJobId = null;

const $ = (sel) => document.querySelector(sel);

// --- Helpers ---

function showStep(id) {
  document.querySelectorAll(".step").forEach((s) => (s.hidden = true));
  $(`#step-${id}`).hidden = false;
}

function showError(msg) {
  $("#error-message").textContent = msg;
  showStep("error");
}

// --- Slider live values ---

function bindSlider(sliderId, displayId) {
  const slider = $(sliderId);
  const display = $(displayId);
  display.textContent = slider.value;
  slider.addEventListener("input", () => (display.textContent = slider.value));
}

bindSlider("#threshold", "#threshold-val");
bindSlider("#min-duration", "#min-duration-val");
bindSlider("#padding", "#padding-val");

// --- Upload ---

const dropZone = $("#drop-zone");
const fileInput = $("#file-input");

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});
dropZone.addEventListener("dragleave", () =>
  dropZone.classList.remove("drag-over")
);
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
});

async function uploadFile(file) {
  const status = $("#upload-status");
  status.hidden = false;
  status.textContent = `Uploading ${file.name}...`;

  const form = new FormData();
  form.append("file", file);

  try {
    const resp = await fetch("/api/upload", { method: "POST", body: form });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || "Upload failed");
    }
    const data = await resp.json();
    currentJobId = data.job_id;
    $("#file-info").textContent = `File: ${data.filename}`;
    showStep("config");
  } catch (e) {
    showError(e.message);
  }
}

// --- Process ---

$("#btn-process").addEventListener("click", startProcessing);

async function startProcessing() {
  const config = {
    silence_cut: {
      enabled: $("#silence-enabled").checked,
      threshold_db: parseFloat($("#threshold").value),
      min_duration: parseFloat($("#min-duration").value),
      padding: parseFloat($("#padding").value),
    },
    captions: {
      enabled: $("#captions-enabled").checked,
      model: $("#whisper-model").value,
      output_format: $("#caption-format").value,
    },
  };

  showStep("progress");
  $("#progress-bar").style.width = "0%";
  $("#progress-stage").textContent = "Starting...";

  try {
    const resp = await fetch(`/api/jobs/${currentJobId}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || "Failed to start processing");
    }
    listenProgress();
  } catch (e) {
    showError(e.message);
  }
}

// --- SSE Progress ---

function listenProgress() {
  const source = new EventSource(`/api/jobs/${currentJobId}/progress`);

  source.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.error) {
      source.close();
      showError(data.error);
      return;
    }

    const pct = Math.round((data.progress || 0) * 100);
    $("#progress-bar").style.width = pct + "%";
    $("#progress-stage").textContent = data.stage || "";

    if (data.stage === "complete") {
      source.close();
      showResult(data.result);
    }
  };

  source.onerror = () => {
    source.close();
    showError("Lost connection to server");
  };
}

// --- Result ---

function showResult(result) {
  const info = $("#result-info");
  if (result) {
    const saved = result.duration_original - result.duration_final;
    info.innerHTML =
      `<strong>Original:</strong> ${result.duration_original.toFixed(1)}s<br>` +
      `<strong>Final:</strong> ${result.duration_final.toFixed(1)}s<br>` +
      `<strong>Saved:</strong> ${saved.toFixed(1)}s` +
      (result.segments_removed
        ? ` (${result.segments_removed} silent segments removed)`
        : "");
  } else {
    info.textContent = "Processing complete.";
  }

  const url = `/api/jobs/${currentJobId}/result`;
  $("#result-video").src = url;
  $("#btn-download").href = url;
  showStep("result");
}

// --- Restart / Retry ---

$("#btn-restart").addEventListener("click", () => {
  currentJobId = null;
  fileInput.value = "";
  $("#upload-status").hidden = true;
  showStep("upload");
});

$("#btn-retry").addEventListener("click", () => {
  if (currentJobId) {
    showStep("config");
  } else {
    showStep("upload");
  }
});
