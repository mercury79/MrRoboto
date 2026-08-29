const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

async function api(path, method = "GET", body) {
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if (body) opt.body = JSON.stringify(body);
  const r = await fetch(path, opt);
  return r.json();
}

function getPath(o, p) { return p.split(".").reduce((a, k) => (a ? a[k] : undefined), o); }
function setPath(o, p, v) {
  const ks = p.split("."); let a = o;
  ks.slice(0, -1).forEach((k) => { a[k] = a[k] || {}; a = a[k]; });
  a[ks[ks.length - 1]] = v;
}

function bindFrom(settings) {
  $$("[data-path]").forEach((el) => {
    const v = getPath(settings, el.dataset.path);
    if (v === undefined) return;
    if (el.type === "checkbox") el.checked = !!v;
    else if (v === null) el.value = "";
    else el.value = v;
  });
}

function gatherSettings() {
  const s = {};
  $$("[data-path]").forEach((el) => {
    let v;
    if (el.type === "checkbox") v = el.checked;
    else if (el.hasAttribute("data-int")) v = el.value === "" ? null : Number(el.value);
    else if (el.type === "number") v = Number(el.value);
    else v = el.value;
    setPath(s, el.dataset.path, v);
  });
  return s;
}

async function loadAudioDevices() {
  const r = await api("/api/audio/devices");
  const fill = (sel, list) => {
    const cur = sel.value;
    sel.innerHTML = `<option value="">(por defecto)</option>` +
      list.map((d) => `<option value="${d.index}">[${d.index}] ${d.name}</option>`).join("");
    sel.value = cur;
  };
  fill($("#sel_in"), r.input);
  fill($("#sel_out"), r.output);
}

function badge(text, cls) { return `<span class="badge ${cls || ""}">${text}</span>`; }

async function loadStatus() {
  const st = await api("/api/status");
  // modelos
  const sel = $("#sel_model");
  if (sel && !sel.dataset.filled) {
    sel.innerHTML = Object.entries(st.models).map(([id, d]) => `<option value="${id}">${d}</option>`).join("");
    sel.dataset.filled = "1";
  }
  // badges
  const b = [];
  b.push(badge(st.robot_reachable ? `robot ✓ ${st.robot_ip}` : `robot ✗ ${st.robot_ip}`, st.robot_reachable ? "ok" : "err"));
  b.push(badge(st.secrets.anthropic_api_key.set ? "Anthropic ✓" : "Anthropic ✗", st.secrets.anthropic_api_key.set ? "ok" : "err"));
  b.push(badge(st.secrets.elevenlabs_api_key.set ? "ElevenLabs ✓" : "ElevenLabs —", st.secrets.elevenlabs_api_key.set ? "ok" : ""));
  const missing = Object.entries(st.deps).filter(([, d]) => !d.installed).map(([m]) => m);
  b.push(badge(missing.length ? `deps faltan: ${missing.length}` : "deps ✓", missing.length ? "err" : "ok"));
  b.push(badge(st.running ? "sesión ● activa" : "sesión ○ parada", st.running ? "ok" : ""));
  $("#badges").innerHTML = b.join("");
  $("#enrolled").textContent = "Caras conocidas: " + (st.enrolled.join(", ") || "ninguna");
  $("#btn_start").disabled = st.running;
  $("#btn_stop").disabled = !st.running;
  return st;
}

async function loadConfig() {
  const c = await api("/api/config");
  bindFrom(c.settings);
}

function result(el, items) {
  el.innerHTML = items.map((i) => `<div class="line ${i.ok ? "ok" : "err"}">${i.ok ? "✓" : "✗"} ${i.msg}</div>`).join("");
}

// ---- handlers ----
$("#btn_save_keys").onclick = async () => {
  const r = await api("/api/keys", "POST", {
    anthropic_api_key: $("#key_anthropic").value || undefined,
    elevenlabs_api_key: $("#key_elevenlabs").value || undefined,
  });
  $("#key_anthropic").value = ""; $("#key_elevenlabs").value = "";
  result($("#keys_result"), [{ ok: r.ok, msg: "Keys guardadas." }]);
  loadStatus();
};

$("#btn_verify_keys").onclick = async () => {
  $("#keys_result").textContent = "Verificando...";
  const r = await api("/api/keys/verify", "POST", {
    anthropic_api_key: $("#key_anthropic").value || undefined,
    elevenlabs_api_key: $("#key_elevenlabs").value || undefined,
  });
  result($("#keys_result"), [
    { ok: r.anthropic.ok, msg: "Anthropic: " + r.anthropic.msg },
    { ok: r.elevenlabs.ok, msg: "ElevenLabs: " + r.elevenlabs.msg },
  ]);
};

$("#btn_save_config").onclick = async () => {
  const r = await api("/api/config", "POST", { settings: gatherSettings() });
  if (r.ok) flash($("#btn_save_config"), "Guardado ✓");
};

$("#btn_robot_test").onclick = async () => {
  const r = await api("/api/robot/test", "POST");
  flash($("#btn_robot_test"), r.ok ? "Saludó ✓" : "Sin respuesta ✗");
};

$("#btn_load_voices").onclick = async () => {
  const r = await api("/api/voices");
  const sel = $("#sel_voice");
  const cur = sel.value;
  sel.innerHTML = `<option value="">(por defecto)</option>` +
    r.voices.map((v) => `<option value="${v.id}">${v.name}</option>`).join("");
  sel.value = cur;
  flash($("#btn_load_voices"), r.voices.length ? `${r.voices.length} voces` : "sin voces");
};

$("#btn_enroll").onclick = async () => {
  const name = $("#enroll_name").value.trim();
  if (!name) return;
  flash($("#btn_enroll"), "Capturando...");
  const r = await api("/api/vision/enroll", "POST", { name });
  flash($("#btn_enroll"), r.ok ? `✓ ${r.captured} fotos` : `✗ ${r.error}`);
  loadStatus();
};

$("#btn_say").onclick = async () => {
  const text = $("#say_text").value.trim();
  if (!text) return;
  const r = await api("/api/llm/say", "POST", { text, speak: $("#say_speak").checked });
  $("#say_text").value = "";
};

$("#btn_load_audio").onclick = async () => { await loadAudioDevices(); flash($("#btn_load_audio"), "cargados"); };

$("#btn_start").onclick = async () => { await api("/api/session/start", "POST"); loadStatus(); };
$("#btn_stop").onclick = async () => { await api("/api/session/stop", "POST"); loadStatus(); };

function flash(btn, msg) {
  const old = btn.textContent; btn.textContent = msg;
  setTimeout(() => (btn.textContent = old), 1800);
}

// ---- log polling ----
let logCursor = 0;
async function pollLog() {
  try {
    const r = await api("/api/log?since=" + logCursor);
    if (r.entries.length) {
      const box = $("#log");
      const atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 20;
      r.entries.forEach((e) => {
        const div = document.createElement("div");
        div.className = "e " + e.kind;
        const who = { user: "tú", robot: "MrRoboto", sys: "·", error: "!" }[e.kind] || e.kind;
        div.innerHTML = `<span class="t">${e.t}</span><b>${who}</b> ${e.text}`;
        box.appendChild(div);
      });
      logCursor = r.next;
      if (atBottom) box.scrollTop = box.scrollHeight;
    }
  } catch (_) {}
}

(async function init() {
  await loadStatus();
  await loadAudioDevices();   // opciones antes de bindear los valores guardados
  await loadConfig();
  setInterval(loadStatus, 4000);
  setInterval(pollLog, 800);
})();
