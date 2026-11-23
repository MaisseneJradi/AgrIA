// AgrIA web app: one page, French or Arabic (right to left), works on a phone and a computer.
// 1. A leaf photo is chosen: POST /identify (Identification agent) pre-fills the "detected crop" field.
// 2. The farmer keeps or corrects the crop, then POST /diagnose runs the seven agents for that crop.
// The answer shows the crop and the detected problem in two fields, the full text, products and the agents' trace.

const I18N = {
  fr: {
    tagline: "Le médecin des plantes", photo: "Prendre ou choisir une photo",
    photoHelp: "Une feuille ou un fruit atteint, de près, à la lumière du jour",
    message: "Décrivez le problème (facultatif)", messagePh: "Ex. : taches noires sur les feuilles depuis la pluie",
    gov: "Gouvernorat", choose: "— choisir —", crop: "Culture détectée", cropAuto: "— ajoutez une photo —",
    cropNone: "— choisir la culture —",
    analyse: "Analyser", loading: "Les agents analysent la photo…", products: "Produits homologués",
    product: "Produit", dose: "Dose", dar: "Délai avant récolte", how: "Comment AgrIA a décidé",
    again: "Nouvelle analyse", confidence: "confiance",
    foot: "AgrIA ne remplace pas un technicien : en cas de doute, contactez le CRDA. Seuls des produits homologués en Tunisie sont proposés.",
    issue: { conseil: "Diagnostic", question: "Questions", autre_photo: "Autre photo", crda: "CRDA" },
    days: "j", label: "voir l'étiquette",
    errNothing: "Ajoutez une photo ou un message.", errServer: "Le serveur ne répond pas. Réessayez.",
    seen: "Ce que le modèle a vu", route: { leaf: "feuille", fruit: "fruit", other: "autre" },
    model: { diseases: "maladies", deficiency: "carences", fruits: "fruits" },
    identifying: "Reconnaissance de la culture…",
    cropFound: (n, c) => `Détectée sur la photo : ${n} (${c} %). Corrigez si besoin.`,
    cropUnsure: (n, c) => `Culture incertaine (${n} ? ${c} %) : choisissez-la.`,
    cropOther: "Cette plante ne semble pas faire partie des cultures d'AgrIA.",
    cropNotLeaf: "Pas de feuille reconnue : la culture sera déduite au diagnostic, ou choisissez-la.",
    notPlant: "Cette photo ne ressemble pas à une plante : envoyez une photo d'une feuille ou d'un fruit, de près.",
    cropField: "Culture", problemField: "Maladie détectée", healthy: "Plante saine", none: "—",
    fbQuestion: "Ce diagnostic est-il correct ?", yes: "Oui", no: "Non",
    fbTruth: "Quelle est la bonne réponse ? (plante et maladie)", fbPh: "Ex. : olivier, œil de paon",
    fbSend: "Envoyer", fbThanks: "Merci, c'est enregistré.",
    fbKeep: "J'accepte qu'AgrIA garde cette photo pour mieux reconnaître les maladies en Tunisie",
  },
  ar: {
    tagline: "طبيب النباتات", photo: "التقط صورة أو اخترها",
    photoHelp: "ورقة أو ثمرة مصابة، من قريب وفي ضوء النهار",
    message: "صف المشكلة (اختياري)", messagePh: "مثال: بقع سوداء على الأوراق منذ نزول المطر",
    gov: "الولاية", choose: "— اختر —", crop: "الزراعة المكتشفة", cropAuto: "— أضف صورة —",
    cropNone: "— اختر الزراعة —",
    analyse: "تحليل", loading: "الوكلاء يحللون الصورة…", products: "المبيدات المصادق عليها",
    product: "المنتج", dose: "الجرعة", dar: "المدة قبل الجني", how: "كيف قرر AgrIA",
    again: "تحليل جديد", confidence: "نسبة الثقة",
    foot: "لا يعوّض AgrIA التقني: في حالة الشك اتصل بالـCRDA. لا تُقترح إلا مبيدات مصادق عليها في تونس.",
    issue: { conseil: "التشخيص", question: "أسئلة", autre_photo: "صورة أخرى", crda: "CRDA" },
    days: "أيام", label: "راجع الملصق",
    errNothing: "أضف صورة أو رسالة.", errServer: "الخادم لا يستجيب. أعد المحاولة.",
    seen: "ما رآه النموذج", route: { leaf: "ورقة", fruit: "ثمرة", other: "غير ذلك" },
    model: { diseases: "الأمراض", deficiency: "النقص", fruits: "الثمار" },
    identifying: "جارٍ التعرف على الزراعة…",
    cropFound: (n, c) => `تم التعرف عليها من الصورة: ${n} (${c} %). صحّحها إن لزم.`,
    cropUnsure: (n, c) => `زراعة غير مؤكدة (${n}؟ ${c} %): اخترها.`,
    cropOther: "لا يبدو أن هذه النبتة من زراعات AgrIA.",
    cropNotLeaf: "لم يتم التعرف على ورقة: اختر الزراعة أو ستُستنتج عند التشخيص.",
    notPlant: "لا تبدو هذه الصورة صورة نبات: أرسل صورة ورقة أو ثمرة عن قرب.",
    cropField: "الزراعة", problemField: "المرض المكتشف", healthy: "نبتة سليمة", none: "—",
    fbQuestion: "هل هذا التشخيص صحيح؟", yes: "نعم", no: "لا",
    fbTruth: "ما هو الجواب الصحيح؟ (النبتة والمرض)", fbPh: "مثال: زيتون، عين الطاووس",
    fbSend: "إرسال", fbThanks: "شكرًا، تم التسجيل.",
    fbKeep: "أوافق على أن يحتفظ AgrIA بهذه الصورة لتحسين التعرف على الأمراض في تونس",
  },
};

const $ = (id) => document.getElementById(id);
let lang = "fr";
let governorates = [];
let cultures = [];
let lastIdentify = null;
let journalId = null;
let fbCorrect = null;

function readLang() {
  try { return localStorage.getItem("agria-lang") || "fr"; } catch { return "fr"; }
}
function saveLang(l) {
  try { localStorage.setItem("agria-lang", l); } catch { /* private mode: the choice is not kept */ }
}

function cropLabel(code) {
  const c = cultures.find((x) => x.code === code);
  return c ? (lang === "ar" ? c.ar : c.fr) : code;
}

function setLang(l) {
  lang = l;
  saveLang(l);
  const t = I18N[l];
  document.documentElement.lang = l;
  document.documentElement.dir = l === "ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    if (typeof t[el.dataset.i18n] === "string") el.textContent = t[el.dataset.i18n];
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t[el.dataset.i18nPh]; });
  document.querySelectorAll(".lang button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === l)));
  fillGovernorates();
  fillCultures();
  if (lastIdentify) showCropHint(lastIdentify);
}

function fillGovernorates() {
  const sel = $("gouvernorat");
  const keep = sel.value;
  sel.length = 1;
  for (const g of governorates) sel.add(new Option(lang === "ar" ? g.ar : g.fr, g.fr));
  sel.value = keep;
}

function fillCultures() {
  const sel = $("culture");
  const keep = sel.value;
  sel.length = 1;
  sel.options[0].textContent = $("photo").files[0] ? I18N[lang].cropNone : I18N[lang].cropAuto;
  for (const c of cultures) sel.add(new Option(lang === "ar" ? c.ar : c.fr, c.code));
  sel.value = keep;
}

async function loadLists() {
  try { governorates = await (await fetch("gouvernorats")).json(); fillGovernorates(); } catch { /* optional */ }
  try { cultures = await (await fetch("cultures")).json(); fillCultures(); } catch { /* optional */ }
}

function showError(msg) {
  $("error").textContent = msg;
  $("error").hidden = !msg;
}

function showCropChoices(r) {
  // the three most likely crops as one-tap buttons: the farmer corrects the model in one tap
  const box = $("crop-choices");
  box.replaceChildren();
  const options = ((r && r.top3) || []).filter((o) => cultures.some((c) => c.code === o.code));
  for (const o of options) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = `${cropLabel(o.code)} ${Math.round(o.confiance * 100)} %`;
    b.setAttribute("aria-pressed", String($("culture").value === o.code));
    b.addEventListener("click", () => {
      $("culture").value = o.code;
      box.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    });
    box.append(b);
  }
  box.hidden = !options.length;
}

function showCropHint(r) {
  const t = I18N[lang];
  const hint = $("crop-hint");
  hint.className = "hint";
  showCropChoices(r && !r.loading ? r : null);
  if (!r) { hint.hidden = true; return; }
  if (r.loading) { hint.textContent = t.identifying; }
  else if (r.photo_plante === false) { hint.textContent = t.notPlant; hint.classList.add("warn"); }
  else if (!r.feuille || !r.culture) { hint.textContent = t.cropNotLeaf; hint.classList.add("warn"); }
  else if (r.autre_plante && r.sure) { hint.textContent = t.cropOther; hint.classList.add("warn"); }
  else if (r.sure) {
    const agree = r.n_avis ? ` — ${r.accord}/${r.n_avis} ${lang === "ar" ? "آراء متفقة" : "avis d'accord"}` : "";
    hint.textContent = t.cropFound(cropLabel(r.culture), Math.round(r.confiance * 100)) + agree;
    hint.classList.add("ok");
  }
  else { hint.textContent = t.cropUnsure(cropLabel(r.culture), Math.round(r.confiance * 100)); hint.classList.add("warn"); }
  if (r && !r.loading && r.culture) {  // second opinion of the VLM, when enabled
    if (r.source_culture === "vlm") hint.textContent += lang === "ar" ? " — اقتراح نموذج الرؤية" : " — proposé par le VLM";
    else if (r.desaccord_vlm) hint.textContent += lang === "ar" ? " — نموذج الرؤية يرى زراعة أخرى" : " — le VLM voit une autre culture";
  }
  hint.hidden = false;
}

async function identify(file) {
  lastIdentify = { loading: true };
  showCropHint(lastIdentify);
  $("submit").disabled = true;
  const data = new FormData();
  data.append("photo", file);
  try {
    const r = await fetch("identify", { method: "POST", body: data });
    const body = await r.json();
    if (!r.ok) throw new Error(body.detail || I18N[lang].errServer);
    lastIdentify = body;
    // the detected crop pre-fills the field only when the model is sure and it is a crop of AgrIA
    $("culture").value = body.sure && !body.autre_plante && cultures.some((c) => c.code === body.culture) ? body.culture : "";
    showCropHint(body);
  } catch (err) {
    lastIdentify = null;
    showCropHint(null);
    showError(err.message && !/fetch/i.test(err.message) ? err.message : I18N[lang].errServer);
  } finally {
    $("submit").disabled = false;
  }
}

function linkify(text) {
  const div = document.createElement("div");
  for (const part of text.split(/(https?:\/\/\S+)/g)) {
    if (/^https?:\/\//.test(part)) {
      const a = document.createElement("a");
      a.href = part; a.textContent = part; a.target = "_blank"; a.rel = "noopener";
      div.append(a);
    } else div.append(document.createTextNode(part));
  }
  return div;
}

function li(text, ltr) {
  const el = document.createElement("li");
  el.textContent = text;
  if (ltr) el.dir = "ltr";
  return el;
}

function render(r) {
  const t = I18N[lang];
  const d = r.diagnostic;
  const c = r.culture;
  const badge = $("badge");
  badge.className = `badge ${r.issue}`;
  badge.textContent = t.issue[r.issue] || r.issue;
  $("confidence").textContent = d && d.confiance != null ? `${t.confidence} ${d.confiance} %` : "";

  // the two fields: crop (confirmed or detected) and the problem found for that crop
  const cropCode = (c && c.code) || $("culture").value || "";
  $("res-crop").textContent = cropCode ? cropLabel(cropCode) : t.none;
  $("res-problem").textContent = !d ? t.none
    : d.classe && (d.classe === "healthy" || d.classe.endsWith("__healthy")) ? t.healthy
    : `${d.nom} (${d.confiance} %)`;

  const answer = $("answer");
  answer.dir = r.langue === "ar" ? "rtl" : "ltr";
  answer.replaceChildren(linkify(r.texte));

  const rows = $("products");
  rows.replaceChildren();
  for (const p of r.produits || []) {
    const tr = document.createElement("tr");
    const dar = p.dar_jours == null ? t.label : `${p.dar_jours} ${t.days}`;
    for (const v of [p.nom, p.dose, dar]) {
      const td = document.createElement("td"); td.textContent = v; tr.append(td);
    }
    rows.append(tr);
  }
  $("products-box").hidden = !(r.produits || []).length;

  const trace = $("trace");
  trace.replaceChildren();
  for (const s of r.trace || []) {
    const item = document.createElement("li");
    const b = document.createElement("b"); b.textContent = s.agent;
    item.append(b, document.createTextNode(` — ${s.action} (${s.duree_ms} ms)`));
    trace.append(item);
  }

  const seen = $("seen");
  seen.replaceChildren();
  if (c && c.predite) seen.append(li(`${t.cropField} : ${cropLabel(c.predite)} ${Math.round(c.confiance * 100)} %`));
  if (d && d.top3) {
    seen.append(li(`${t.route[d.routing] || d.routing} → ${t.model[d.task] || d.task}`));
    for (const [cls, p] of d.top3) seen.append(li(`${cls} : ${Math.round(p * 100)} %`, true));
  }
  $("seen-box").hidden = !seen.children.length;

  journalId = r.journal_id || null;
  fbCorrect = null;
  $("feedback").hidden = !journalId;
  $("fb-truth").hidden = true;
  $("fb-send").hidden = true;
  $("fb-keep-label").hidden = true;
  $("fb-keep").checked = false;
  $("fb-done").hidden = true;
  $("fb-text").value = "";
  document.querySelectorAll("[data-correct]").forEach((b) => b.setAttribute("aria-pressed", "false"));

  $("result").hidden = false;
  $("result").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function sendFeedback() {
  const data = new FormData();
  data.append("journal_id", journalId);
  data.append("correct", fbCorrect);
  data.append("vraie_reponse", $("fb-text").value.trim());
  data.append("garder_photo", $("fb-keep").checked ? "oui" : "non");
  try {
    const r = await fetch("feedback", { method: "POST", body: data });
    if (r.ok) { $("fb-done").hidden = false; $("fb-send").hidden = true; }
  } catch { showError(I18N[lang].errServer); }
}

$("culture").addEventListener("change", () => {
  $("crop-choices").querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", "false"));
});

$("photo").addEventListener("change", () => {
  const f = $("photo").files[0];
  const img = $("preview");
  showError("");
  if (!f) { img.hidden = true; $("photo-hint").hidden = false; lastIdentify = null; showCropHint(null); fillCultures(); return; }
  img.src = URL.createObjectURL(f);
  img.hidden = false;
  $("photo-hint").hidden = true;
  fillCultures();
  identify(f);
});

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("");
  const photo = $("photo").files[0];
  const message = $("message").value.trim();
  if (!photo && !message) { showError(I18N[lang].errNothing); return; }
  const data = new FormData();
  if (photo) data.append("photo", photo);
  data.append("message", message);
  data.append("langue", lang);
  data.append("mois", String(new Date().getMonth() + 1));
  if ($("gouvernorat").value) data.append("gouvernorat", $("gouvernorat").value);
  if ($("culture").value) data.append("culture", $("culture").value);

  $("submit").disabled = true;
  $("loading").hidden = false;
  $("result").hidden = true;
  try {
    const r = await fetch("diagnose", { method: "POST", body: data });
    const body = await r.json();
    if (!r.ok) throw new Error(body.detail || I18N[lang].errServer);
    render(body);
  } catch (err) {
    showError(err.message && !/fetch/i.test(err.message) ? err.message : I18N[lang].errServer);
  } finally {
    $("submit").disabled = false;
    $("loading").hidden = true;
  }
});

$("again").addEventListener("click", () => {
  $("form").reset();
  $("preview").hidden = true;
  $("photo-hint").hidden = false;
  $("result").hidden = true;
  lastIdentify = null;
  showCropHint(null);
  fillCultures();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

document.querySelectorAll("[data-correct]").forEach((b) => b.addEventListener("click", () => {
  fbCorrect = b.dataset.correct;
  document.querySelectorAll("[data-correct]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  $("fb-truth").hidden = fbCorrect === "oui";
  $("fb-send").hidden = false;
  $("fb-keep-label").hidden = false;
  $("fb-done").hidden = true;
  if (fbCorrect === "oui") sendFeedback();
}));
$("fb-send").addEventListener("click", sendFeedback);
document.querySelectorAll(".lang button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));

setLang(readLang());
loadLists();
