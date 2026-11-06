import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

// ---------- state ----------
const state = {
  tab: "text",
  imageMode: "relief",
  imageFile: null,
  currentId: null,
  wireframe: false,
};

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const ENGINE_INFO = {
  local:  { label: "Local engine",        cloud: false },
  shape:  { label: "Shap-E (OpenAI, local)", cloud: false,
            note: "Runs fully local. First use downloads ~1 GB of weights — minutes on CPU." },
  meshy:  { label: "Meshy cloud AI",      cloud: true,
            keyName: "Meshy", keyUrl: "meshy.ai" },
  tripo:  { label: "Tripo AI cloud",      cloud: true,
            keyName: "Tripo AI", keyUrl: "platform.tripo3d.ai" },
  sf3d:   { label: "Stable Fast 3D",      cloud: true,
            keyName: "Stability AI", keyUrl: "platform.stability.ai" },
  spar3d: { label: "Stability SPAR3D",    cloud: true,
            keyName: "Stability AI", keyUrl: "platform.stability.ai" },
};

const ENH_MODELS = {
  openai: "gpt-4o-mini",
  claude: "claude-sonnet-4-5",
  kimi: "kimi-k3",
  qwen: "qwen-plus",
  llama: "meta-llama/llama-3.3-70b-instruct",
  ollama: "llama3.1",
};

// ---------- toasts ----------
function toast(msg, type = "info") {
  const box = $("#toasts");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  box.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 350);
  }, 4200);
}

// ---------- three.js viewport ----------
const container = $("#viewport");
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x211f1c);
scene.fog = new THREE.Fog(0x211f1c, 14, 40);

const camera = new THREE.PerspectiveCamera(50, 1, 0.01, 200);
camera.position.set(3.2, 2.4, 3.2);

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.autoRotateSpeed = 1.4;

scene.add(new THREE.HemisphereLight(0xebecd0, 0x312e2b, 0.9));
const key = new THREE.DirectionalLight(0xffffff, 2.2);
key.position.set(4, 6, 3);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
scene.add(key);
const rim = new THREE.DirectionalLight(0x81b64c, 0.8);
rim.position.set(-4, 2, -4);
scene.add(rim);

const grid = new THREE.GridHelper(20, 40, 0x4a463f, 0x35322e);
scene.add(grid);
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(20, 20),
  new THREE.ShadowMaterial({ opacity: 0.35 })
);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.001;
ground.receiveShadow = true;
scene.add(ground);

let currentModel = null;
const loader = new GLTFLoader();

function resize() {
  const { clientWidth: w, clientHeight: h } = container;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(container);
resize();

(function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
})();

function applyWireframe() {
  if (!currentModel) return;
  currentModel.traverse((o) => {
    if (o.isMesh) {
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      mats.forEach((m) => (m.wireframe = state.wireframe));
    }
  });
}

function captureThumb(id) {
  try {
    renderer.render(scene, camera);
    const url = renderer.domElement.toDataURL("image/jpeg", 0.65);
    localStorage.setItem("shaper_thumb_" + id, url);
  } catch { /* storage full or blocked — thumbnails are optional */ }
}

function loadModel(url, info, modelId) {
  loader.load(url, (gltf) => {
    if (currentModel) scene.remove(currentModel);
    currentModel = gltf.scene;
    // normalize scale + center on grid
    const box = new THREE.Box3().setFromObject(currentModel);
    const size = box.getSize(new THREE.Vector3()).length() || 1;
    currentModel.scale.setScalar(3 / size);
    const box2 = new THREE.Box3().setFromObject(currentModel);
    const center = box2.getCenter(new THREE.Vector3());
    currentModel.position.sub(center);
    currentModel.position.y += (box2.max.y - box2.min.y) / 2;
    currentModel.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    applyWireframe();
    scene.add(currentModel);
    $("#hudInfo").textContent = info;
    setExportEnabled(true);
    if (modelId) captureThumb(modelId);
  });
}

// ---------- viewport tools ----------
$("#rotateBtn").addEventListener("click", () => {
  controls.autoRotate = !controls.autoRotate;
  $("#rotateBtn").classList.toggle("active", controls.autoRotate);
});

$("#wireBtn").addEventListener("click", () => {
  state.wireframe = !state.wireframe;
  $("#wireBtn").classList.toggle("active", state.wireframe);
  applyWireframe();
});

const BG_PRESETS = { dark: 0x211f1c, moss: 0x26311e, slate: 0x22303c };
$$(".bgsw").forEach((b) =>
  b.addEventListener("click", () => {
    $$(".bgsw").forEach((x) => x.classList.toggle("active", x === b));
    const c = BG_PRESETS[b.dataset.bg];
    scene.background = new THREE.Color(c);
    scene.fog.color.set(c);
  })
);

// ---------- tabs ----------
$$(".tab").forEach((t) =>
  t.addEventListener("click", () => {
    $$(".tab").forEach((x) => x.classList.toggle("active", x === t));
    state.tab = t.dataset.tab;
    $$(".tabpane").forEach((p) => p.classList.toggle("active", p.id === "tab-" + state.tab));
    syncEngineUI();
  })
);

// ---------- engine selection ----------
function currentEngine() {
  return state.tab === "text" ? $("#textEngine").value : $("#imageEngine").value;
}

function syncEngineUI() {
  const engine = currentEngine();
  const info = ENGINE_INFO[engine];
  const pane = $("#tab-" + state.tab);

  pane.querySelectorAll(".local-only").forEach((el) =>
    el.classList.toggle("hidden", engine !== "local"));
  pane.querySelectorAll(".meshy-only").forEach((el) =>
    el.classList.toggle("hidden", engine !== "meshy"));

  const keyWrap = state.tab === "text" ? $("#textKeyWrap") : $("#imageKeyWrap");
  const keyHint = state.tab === "text" ? $("#textKeyHint") : $("#imageKeyHint");
  keyWrap.classList.toggle("hidden", !info.keyName);
  if (info.keyName)
    keyHint.textContent = `${info.keyName} key — get one at ${info.keyUrl}. Never stored, sent only with this request.`;

  $(".shape-only").classList.toggle("hidden",
    !(state.tab === "text" && engine === "shape"));

  $("#providerDot").classList.toggle("cloud", info.cloud);
  $("#providerLabel").textContent = info.label;
}
$("#textEngine").addEventListener("change", syncEngineUI);
$("#imageEngine").addEventListener("change", syncEngineUI);
syncEngineUI();

// ---------- prompt enhancer ----------
function syncEnhUI() {
  const p = $("#enhProvider").value;
  $("#enhConfig").classList.toggle("hidden", p === "none");
  $("#enhKey").classList.toggle("hidden", p === "ollama");
  $("#enhModel").placeholder = ENH_MODELS[p] ? `${ENH_MODELS[p]} (default)` : "model (optional)";
}
$("#enhProvider").addEventListener("change", syncEnhUI);
syncEnhUI();

$("#enhanceBtn").addEventListener("click", async () => {
  const prompt = $("#prompt").value.trim();
  const provider = $("#enhProvider").value;
  if (!prompt) return toast("Type a prompt first.", "err");
  if (provider === "none") return toast("Pick an enhancer model first.", "err");
  const btn = $("#enhanceBtn");
  btn.disabled = true;
  btn.textContent = "…";
  try {
    const fd = new FormData();
    fd.set("prompt", prompt);
    fd.set("provider", provider);
    fd.set("api_key", $("#enhKey").value);
    fd.set("model", $("#enhModel").value);
    const res = await fetch("/api/enhance", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Enhancement failed");
    $("#prompt").value = data.enhanced;
    toast("Prompt enhanced.");
  } catch (e) {
    toast(e.message, "err");
  } finally {
    btn.disabled = false;
    btn.textContent = "Enhance";
  }
});

// ---------- sliders live labels ----------
[["complexity", "complexityVal"], ["depth", "depthVal"], ["threshold", "thresholdVal"], ["smooth", "smoothVal"]]
  .forEach(([inp, out]) => $("#" + inp).addEventListener("input", (e) => ($("#" + out).textContent = e.target.value)));

// ---------- image mode seg ----------
$("#imageMode").addEventListener("click", (e) => {
  const btn = e.target.closest(".segbtn");
  if (!btn) return;
  $$("#imageMode .segbtn").forEach((b) => b.classList.toggle("active", b === btn));
  state.imageMode = btn.dataset.v;
});

// ---------- dropzone ----------
const dz = $("#dropzone");
dz.addEventListener("click", () => $("#imageInput").click());
dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
dz.addEventListener("drop", (e) => {
  e.preventDefault(); dz.classList.remove("drag");
  if (e.dataTransfer.files[0]) setImage(e.dataTransfer.files[0]);
});
$("#imageInput").addEventListener("change", (e) => e.target.files[0] && setImage(e.target.files[0]));

function setImage(file) {
  state.imageFile = file;
  const img = $("#imagePreview");
  img.src = URL.createObjectURL(file);
  img.classList.remove("hidden");
}

// ---------- generation ----------
const spinner = $("#spinner");
function busy(on, text = "Generating…") {
  spinner.classList.toggle("hidden", !on);
  $("#spinnerText").textContent = text;
  $("#generateBtn").disabled = on;
}

function status(msg, isErr = false) {
  const el = $("#statusMsg");
  el.textContent = msg;
  el.classList.toggle("err", isErr);
  if (isErr) toast(msg, "err");
}

function busyText(engine) {
  if (engine === "local") return "Generating locally…";
  if (engine === "shape") return "Shap-E running (slow on first use)…";
  return "Cloud AI working (1–5 min)…";
}

$("#generateBtn").addEventListener("click", async () => {
  status("");
  const fd = new FormData();
  const engine = currentEngine();

  if (state.tab === "text") {
    const prompt = $("#prompt").value.trim();
    if (!prompt) return status("Type a prompt first.", true);
    fd.set("prompt", prompt);
    fd.set("provider", engine);
    fd.set("complexity", $("#complexity").value);
    if ($("#seed").value) fd.set("seed", $("#seed").value);
    fd.set("art_style", $("#artStyle").value);
    fd.set("api_key", $("#textKey").value);
    busy(true, busyText(engine));
    await runGenerate("/api/generate/text", fd);
  } else {
    if (!state.imageFile) return status("Pick an image first.", true);
    fd.set("file", state.imageFile);
    fd.set("provider", engine);
    fd.set("mode", state.imageMode);
    fd.set("depth", $("#depth").value);
    fd.set("threshold", $("#threshold").value);
    fd.set("smooth", $("#smooth").value);
    fd.set("api_key", $("#imageKey").value);
    busy(true, busyText(engine));
    await runGenerate("/api/generate/image", fd);
  }
});

async function runGenerate(url, fd) {
  try {
    const res = await fetch(url, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Generation failed");
    state.currentId = data.model.id;
    loadModel(data.glb_url,
      `${data.model.name} · ${data.model.vertices.toLocaleString()} verts`,
      data.model.id);
    status("Done — model loaded in viewport.");
    toast(`Generated “${data.model.name}”`, "ok");
    refreshLibrary();
  } catch (e) {
    status(e.message, true);
  } finally {
    busy(false);
  }
}

// ---------- export ----------
function setExportEnabled(on) {
  $$(".exp").forEach((b) => (b.disabled = !on));
  $("#blenderBtn").disabled = !on;
}
setExportEnabled(false);

$$(".exp").forEach((b) =>
  b.addEventListener("click", () => {
    if (!state.currentId) return;
    window.location = `/api/download/${state.currentId}?format=${b.dataset.fmt}`;
    toast(`Downloading ${b.dataset.fmt.toUpperCase()}…`, "ok");
  })
);

$("#blenderBtn").addEventListener("click", () => {
  if (!state.currentId) return;
  window.location = `/api/export/blender/${state.currentId}`;
  toast("Blender script downloaded — run it in Blender's Scripting workspace.", "ok");
});

// ---------- library ----------
async function refreshLibrary() {
  const models = await (await fetch("/api/models")).json();
  const el = $("#library");
  if (!models.length) {
    el.innerHTML = '<div class="empty">Nothing generated yet.<br>Your models will appear here.</div>';
    return;
  }
  el.innerHTML = "";
  models.forEach((m) => {
    const thumb = localStorage.getItem("shaper_thumb_" + m.id);
    const div = document.createElement("div");
    div.className = "lib-item" + (m.id === state.currentId ? " active" : "");
    div.innerHTML = `${thumb ? `<img class="lib-thumb" src="${thumb}" alt="">` : ""}
      <div class="lib-body">
        <div class="nm"></div>
        <div class="meta">${m.source} · ${m.vertices.toLocaleString()} verts<br>${m.created}</div>
      </div>
      <button class="del" title="Delete">×</button>`;
    div.querySelector(".nm").textContent = m.name;
    div.addEventListener("click", (e) => {
      if (e.target.classList.contains("del")) return;
      state.currentId = m.id;
      loadModel(`/api/download/${m.id}?format=glb`,
        `${m.name} · ${m.vertices.toLocaleString()} verts`, m.id);
      refreshLibrary();
    });
    div.querySelector(".del").addEventListener("click", async () => {
      await fetch(`/api/models/${m.id}`, { method: "DELETE" });
      localStorage.removeItem("shaper_thumb_" + m.id);
      if (state.currentId === m.id) { state.currentId = null; setExportEnabled(false); }
      refreshLibrary();
      toast("Model deleted.");
    });
    el.appendChild(div);
  });
}
refreshLibrary();
