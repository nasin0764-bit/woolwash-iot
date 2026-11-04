// WoolWash Monitor – web + installable mobile app (PWA). EN / RU.
const I18N = {
  en: {title:"WoolWash Monitor",overview:"Overview",charts:"Trends",lab:"Lab & model",simdata:"SIMULATED DATA",
    moisture:"Residual moisture (predicted)",power:"Power",omega:"Squeeze drum ω",feed:"Feed rate",
    kwhkg:"Specific energy",lkg:"Specific water",bowls:"Washing bowls",alerts:"Alerts",updated:"Last update",
    window:"Window",export:"Export CSV",addlab:"Add lab moisture sample",
    labhelp:"Take a wool sample right after the squeeze device, measure residual moisture by oven-drying (105 °C to constant mass) and enter it here. The current machine state is attached automatically and the soft sensor is recalibrated.",
    save:"Save",model:"Soft-sensor model",samples:"Samples",time:"Time",note:"Note",bowl:"Bowl",
    temp:"Temperature",level:"Level",turb:"Turbidity",noalerts:"No active alerts",nodata:"No data yet",
    temp_low:"Temperature low",temp_high:"Temperature high",level_low:"Liquor level low",
    liquor_dirty:"Liquor dirty – change recommended",omega_dev:"Drum speed out of range",moisture_high:"Residual moisture above 60 %",
    c_moist:"Residual moisture, % (predicted)",c_temp:"Bowl temperature, °C",c_turb:"Liquor turbidity, NTU",c_power:"Power, kW",
    saved:"Saved",setup:"Commissioning",token:"Device token",geom:"Squeezing device geometry",limits:"Alarm limits",
    setuphelp:"Machine-specific settings, set once at commissioning. Saving requires the device token (WW_TOKEN of the server).",
    g_hole:"Mesh hole diameter, mm",g_drum:"Squeeze drum diameter, mm",g_gap:"Drum–mesh gap, mm",g_rake:"Rake length, mm",
    l_tmin:"Min. temperature, bowls 1–5, °C",l_tmax:"Max. temperature, bowls 1–5, °C",l_level:"Min. liquor level, cm",
    l_ton:"Dirty liquor ON above, NTU",l_toff:"Dirty liquor OFF below, NTU",l_deb:"Debounce, messages (×2 s)",
    l_om:"Nominal drum ω, rad/s",l_omt:"ω tolerance, rad/s",l_moist:"Moisture alarm above, %",
    badtoken:"Wrong token",needtoken:"Enter the device token first",err:"Error"},
  ru: {title:"Монитор шерстомойки",overview:"Обзор",charts:"Графики",lab:"Лаборатория",simdata:"ДАННЫЕ СИМУЛЯЦИИ",
    moisture:"Остаточная влажность (прогноз)",power:"Мощность",omega:"ω отжимного барабана",feed:"Подача",
    kwhkg:"Удельная энергия",lkg:"Удельный расход воды",bowls:"Моечные барки",alerts:"Сигналы",updated:"Обновлено",
    window:"Период",export:"Экспорт CSV",addlab:"Лабораторная проба влажности",
    labhelp:"Отберите пробу шерсти сразу после отжимного устройства, определите остаточную влажность высушиванием (105 °C до постоянной массы) и введите здесь. Текущее состояние машины прикрепляется автоматически, модель пересчитывается.",
    save:"Сохранить",model:"Модель виртуального датчика",samples:"Пробы",time:"Время",note:"Примечание",bowl:"Барка",
    temp:"Температура",level:"Уровень",turb:"Мутность",noalerts:"Активных сигналов нет",nodata:"Нет данных",
    temp_low:"Низкая температура",temp_high:"Высокая температура",level_low:"Низкий уровень раствора",
    liquor_dirty:"Раствор загрязнён – требуется замена",omega_dev:"Скорость барабана вне нормы",moisture_high:"Остаточная влажность выше 60 %",
    c_moist:"Остаточная влажность, % (прогноз)",c_temp:"Температура в барках, °C",c_turb:"Мутность раствора, NTU",c_power:"Мощность, кВт",
    saved:"Сохранено",setup:"Пусконаладка",token:"Токен устройства",geom:"Геометрия отжимного устройства",limits:"Пороги сигнализации",
    setuphelp:"Настройки конкретной машины, задаются один раз при пусконаладке. Для сохранения нужен токен устройства (WW_TOKEN сервера).",
    g_hole:"Диаметр отверстий сетки, мм",g_drum:"Диаметр отжимного барабана, мм",g_gap:"Зазор барабан–сетка, мм",g_rake:"Длина граблин, мм",
    l_tmin:"Мин. температура, барки 1–5, °C",l_tmax:"Макс. температура, барки 1–5, °C",l_level:"Мин. уровень раствора, см",
    l_ton:"Загрязнение: включить выше, NTU",l_toff:"Загрязнение: выключить ниже, NTU",l_deb:"Задержка, сообщений (×2 с)",
    l_om:"Номинальная ω барабана, рад/с",l_omt:"Допуск ω, рад/с",l_moist:"Сигнал влажности выше, %",
    badtoken:"Неверный токен",needtoken:"Сначала введите токен устройства",err:"Ошибка"}
};
let lang = (()=>{try{return localStorage.getItem("ww-lang")||"en"}catch(e){return "en"}})();
const t = k => (I18N[lang]||I18N.en)[k] || k;
const $ = s => document.querySelector(s);
let machine = null, charts = {}, lastMsg = null;

function applyLang(){
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach(el => el.textContent = t(el.dataset.i18n));
  $("#lang").textContent = lang === "en" ? "RU" : "EN";
  document.title = t("title");
  if (lastMsg) render(lastMsg);
  buildCharts(); loadHistory();
}
$("#lang").onclick = () => { lang = lang === "en" ? "ru" : "en"; try{localStorage.setItem("ww-lang",lang)}catch(e){} applyLang(); };

document.querySelectorAll(".tab").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tab,.pane").forEach(x => x.classList.remove("active"));
  b.classList.add("active"); $("#"+b.dataset.tab).classList.add("active");
  if (b.dataset.tab === "charts") loadHistory();
  if (b.dataset.tab === "lab") loadLab();
  if (b.dataset.tab === "setup") loadSetup();
});

// ---- commissioning tab: per-machine geometry and alarm limits (token-protected PUT)
try { $("#tok").value = sessionStorage.getItem("ww-token") || ""; } catch(e) {}
$("#tok").onchange = () => { try { sessionStorage.setItem("ww-token", $("#tok").value); } catch(e) {} };

function fillForm(form, obj){
  [...form.elements].forEach(el => { if (el.name && el.name in obj) el.value = Array.isArray(obj[el.name]) ? obj[el.name].join(", ") : obj[el.name]; });
}
async function loadSetup(){
  if (!machine) return;
  try {
    const [lim, mod] = await Promise.all([api(`/api/limits/${machine}`), api(`/api/model/${machine}`)]);
    fillForm($("#limform"), lim); fillForm($("#geomform"), mod.geometry || {});
  } catch(e) {}
}
async function saveForm(form, path, ev){
  ev.preventDefault();
  const msg = form.querySelector(".msg"); msg.className = "msg"; msg.textContent = "";
  const token = $("#tok").value.trim();
  if (!token) { msg.className = "msg err"; msg.textContent = t("needtoken"); return; }
  const body = {};
  [...form.elements].forEach(el => { if (el.name && el.value !== "") body[el.name] = el.type === "number" ? Number(el.value) : el.value; });
  try {
    const r = await fetch(`${path}/${machine}`, {method:"PUT", headers:{"Content-Type":"application/json","X-Token":token}, body:JSON.stringify(body)});
    if (r.status === 401) { msg.className = "msg err"; msg.textContent = t("badtoken"); return; }
    if (!r.ok) { const d = await r.json().catch(()=>({})); msg.className = "msg err"; msg.textContent = `${t("err")}: ${d.detail || r.status}`; return; }
    fillForm(form, await r.json()); msg.className = "msg ok"; msg.textContent = t("saved");
  } catch(e) { msg.className = "msg err"; msg.textContent = `${t("err")}: ${e.message}`; }
}
$("#limform").onsubmit = ev => saveForm($("#limform"), "/api/limits", ev);
$("#geomform").onsubmit = ev => saveForm($("#geomform"), "/api/geometry", ev);

const fmt = (v,d=1) => v==null||isNaN(v) ? "–" : Number(v).toFixed(d);

function render(m){
  lastMsg = m;
  const d = m.data, sq = (d.squeeze||[{}])[0];
  $("#simbadge").classList.toggle("hidden", d.source !== "sim");
  $("#k-moist").textContent = fmt(m.moisture_pred,1);
  $("#k-moist").parentElement.classList.toggle("bad", m.moisture_pred > 60);
  $("#k-power").textContent = fmt(d.power_w/1000,2);
  $("#k-omega").textContent = fmt(sq.drum_omega,2);
  $("#k-feed").textContent = fmt(d.feed_kg_h,0);
  const lvl = {};
  (m.alerts||[]).forEach(a => { if (a.bowl) lvl[a.bowl] = (lvl[a.bowl]==="crit"?"crit":a.level); });
  $("#bowls").innerHTML = (d.bowls||[]).map(b => `<div class="bowl ${lvl[b.id]||""}"><h3>${t("bowl")} ${b.id}</h3>
    <div><span>${t("temp")}</span><span>${fmt(b.temp_c)} °C</span></div>
    <div><span>${t("level")}</span><span>${fmt(b.level_cm)} cm</span></div>
    <div><span>${t("turb")}</span><span>${fmt(b.turbidity_ntu,0)} NTU</span></div></div>`).join("");
  $("#alerts").innerHTML = (m.alerts||[]).length ? m.alerts.map(a =>
      `<li class="${a.level}">${t(a.code)}${a.bowl?` – ${t("bowl")} ${a.bowl}`:""}: <b>${fmt(a.value,1)}</b></li>`).join("")
    : `<li class="none">${t("noalerts")}</li>`;
  $("#updated").textContent = new Date(m.ts*1000).toLocaleString(lang==="ru"?"ru-RU":"en-GB");
}

async function api(p, opt){ const r = await fetch(p, opt); if(!r.ok) throw new Error(r.status); return r.json(); }

async function loadMachines(){
  const ms = await api("/api/machines").catch(()=>[]);
  const sel = $("#machine");
  sel.innerHTML = ms.map(m => `<option>${m.id}</option>`).join("") || `<option>${t("nodata")}</option>`;
  if (!machine && ms.length) machine = ms[0].id;
  if (machine) sel.value = machine;
  sel.onchange = () => { machine = sel.value; refresh(); };
}

async function refresh(){
  if (!machine) return;
  try { const l = await api(`/api/latest/${machine}`); render({...l, machine}); } catch(e){}
  loadHistory();
}

function mkChart(id, label, n){
  const colors = ["#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd"];
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($("#"+id), {type:"line",
    data:{labels:[],datasets:Array.from({length:n},(_,i)=>({label:n>1?`${t("bowl")} ${i+1}`:label,data:[],
      borderColor:colors[i],pointRadius:0,borderWidth:1.6,tension:.2}))},
    options:{animation:false,maintainAspectRatio:false,plugins:{title:{display:true,text:label},legend:{display:n>1}},
      scales:{x:{ticks:{maxTicksLimit:6}}}}});
}
function buildCharts(){
  if (!window.Chart) return;
  mkChart("c-moist", t("c_moist"), 1); mkChart("c-temp", t("c_temp"), 5);
  mkChart("c-turb", t("c_turb"), 5);   mkChart("c-power", t("c_power"), 1);
}
async function loadHistory(){
  if (!machine || !window.Chart) return;
  const win = $("#win").value;
  $("#csv").href = `/api/export/${machine}.csv?hours=${win/60}`;
  const h = await api(`/api/history/${machine}?minutes=${win}`).catch(()=>null);
  if (!h) return;
  const lab = h.points.map(p => new Date(p.ts*1000).toLocaleTimeString(lang==="ru"?"ru-RU":"en-GB",{hour:"2-digit",minute:"2-digit"}));
  const set = (id, fn) => { const c = charts[id]; c.data.labels = lab; c.data.datasets.forEach((ds,i)=>ds.data=h.points.map(p=>fn(p,i))); c.update(); };
  set("c-moist", p => p.moisture); set("c-temp", (p,i) => p.temps[i]);
  set("c-turb", (p,i) => p.turb[i]); set("c-power", p => p.power_w/1000);
  const k = h.kpi||{};
  $("#k-kwhkg").textContent = fmt(k.kwh_per_kg,4); $("#k-lkg").textContent = fmt(k.l_per_kg,2);
}
$("#win").onchange = loadHistory;

async function loadLab(){
  if (!machine) return;
  const [mi, rows] = await Promise.all([api(`/api/model/${machine}`), api(`/api/lab/${machine}`)]).catch(()=>[null,[]]);
  if (mi) $("#modelinfo").textContent = JSON.stringify(mi, null, 2);
  $("#labrows").innerHTML = rows.map(r => `<tr><td>${new Date(r.ts*1000).toLocaleString()}</td><td>${fmt(r.moisture_pct,2)}</td><td>${r.note||""}</td></tr>`).join("");
}
$("#labform").onsubmit = async e => {
  e.preventDefault();
  await api("/api/lab", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({machine, moisture_pct: parseFloat($("#labval").value), note: $("#labnote").value})});
  $("#labval").value = ""; $("#labnote").value = ""; loadLab();
};

function connectWS(){
  const ws = new WebSocket((location.protocol==="https:"?"wss://":"ws://") + location.host + "/ws");
  ws.onopen = () => $("#conn").className = "dot on";
  ws.onclose = () => { $("#conn").className = "dot off"; setTimeout(connectWS, 3000); };
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (!machine) { machine = m.machine; loadMachines(); }
    if (m.machine === machine) render(m);
    else if (![...$("#machine").options].some(o => o.value === m.machine)) loadMachines();
  };
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(()=>{});
(async () => { await loadMachines(); applyLang(); refresh(); connectWS(); setInterval(loadHistory, 30000); })();
