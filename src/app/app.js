// AgrIA web app: one page, French or Arabic (right to left), works on a phone and a computer.
// It sends the photo, the message and the governorate to POST /diagnose and shows the agents' answer.

const I18N = {
  fr: {
    tagline: "Le médecin des plantes", photo: "Prendre ou choisir une photo",
    photoHelp: "Une feuille ou un fruit atteint, de près, à la lumière du jour",
    message: "Décrivez le problème (facultatif)", messagePh: "Ex. : taches noires sur les feuilles depuis la pluie",
    gov: "Gouvernorat", choose: "— choisir —", crop: "Culture (facultatif)", cropPh: "tomate, olivier…",
    analyse: "Analyser", loading: "Les agents analysent la photo…", products: "Produits homologués",
    product: "Produit", dose: "Dose", dar: "Délai avant récolte", how: "Comment AgrIA a décidé",
    again: "Nouvelle analyse", confidence: "confiance",
    foot: "AgrIA ne remplace pas un technicien : en cas de doute, contactez le CRDA. Seuls des produits homologués en Tunisie sont proposés.",
    issue: { conseil: "Diagnostic", question: "Questions", autre_photo: "Autre photo", crda: "CRDA" },
    days: "j", label: "voir l'étiquette",
    errNothing: "Ajoutez une photo ou un message.", errServer: "Le serveur ne répond pas. Réessayez.",
    seen: "Ce que le modèle a vu", route: { leaf: "feuille", fruit: "fruit", other: "autre" },
    model: { diseases: "maladies", deficiency: "carences", fruits: "fruits" },
    fbQuestion: "Ce diagnostic est-il correct ?", yes: "Oui", no: "Non",
    fbTruth: "Quelle est la bonne réponse ? (plante et maladie)", fbPh: "Ex. : olivier, œil de paon",
    fbSend: "Envoyer", fbThanks: "Merci, c'est enregistré.",
  },
  ar: {
    tagline: "طبيب النباتات", photo: "التقط صورة أو اخترها",
    photoHelp: "ورقة أو ثمرة مصابة، من قريب وفي ضوء النهار",
    message: "صف المشكلة (اختياري)", messagePh: "مثال: بقع سوداء على الأوراق منذ نزول المطر",
    gov: "الولاية", choose: "— اختر —", crop: "الزراعة (اختياري)", cropPh: "طماطم، زيتون…",
    analyse: "تحليل", loading: "الوكلاء يحللون الصورة…", products: "المبيدات المصادق عليها",
    product: "المنتج", dose: "الجرعة", dar: "المدة قبل الجني", how: "كيف قرر AgrIA",
    again: "تحليل جديد", confidence: "نسبة الثقة",
    foot: "لا يعوّض AgrIA التقني: في حالة الشك اتصل بالـCRDA. لا تُقترح إلا مبيدات مصادق عليها في تونس.",
    issue: { conseil: "التشخيص", question: "أسئلة", autre_photo: "صورة أخرى", crda: "CRDA" },
    days: "أيام", label: "راجع الملصق",
    errNothing: "أضف صورة أو رسالة.", errServer: "الخادم لا يستجيب. أعد المحاولة.",
    seen: "ما رآه النموذج", route: { leaf: "ورقة", fruit: "ثمرة", other: "غير ذلك" },
    model: { diseases: "الأمراض", deficiency: "النقص", fruits: "الثمار" },
    fbQuestion: "هل هذا التشخيص صحيح؟", yes: "نعم", no: "لا",
    fbTruth: "ما هو الجواب الصحيح؟ (النبتة والمرض)", fbPh: "مثال: زيتون، عين الطاووس",
    fbSend: "إرسال", fbThanks: "شكرًا، تم التسجيل.",
  },
};

const $ = (id) => document.getElementById(id);
let lang = "fr";
let governorates = [];
let journalId = null;
let fbCorrect = null;

function readLang() {
  try { return localStorage.getItem("agria-lang") || "fr"; } catch { return "fr"; }
}
function saveLang(l) {
  try { localStorage.setItem("agria-lang", l); } catch { /* private mode: the choice is not kept */ }
}

function setLang(l) {
  lang = l;
  saveLang(l);
  const t = I18N[l];
  document.documentElement.lang = l;
  document.documentElement.dir = l === "ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t[el.dataset.i18n]; });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t[el.dataset.i18nPh]; });
  async function sendFeedback() {
  const data = new FormData();
  data.append("journal_id", journalId);
  data.append("correct", fbCorrect);
  data.append("vraie_reponse", $("fb-text").value.trim());
  try {
    const r = await fetch("feedback", { method: "POST", body: data });
    if (r.ok) { $("fb-done").hidden = false; $("fb-send").hidden = true; }
  } catch { showError(I18N[lang].errServer); }
}

document.querySelectorAll("[data-correct]").forEach((b) => b.addEventListener("click", () => {
  fbCorrect = b.dataset.correct;
  document.querySelectorAll("[data-correct]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  $("fb-truth").hidden = fbCorrect === "oui";
  $("fb-send").hidden = false;
  $("fb-done").hidden = true;
  if (fbCorrect === "oui") sendFeedback();
}));
$("fb-send").addEventListener("click", sendFeedback);

document.querySelectorAll(".lang button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === l)));
  fillGovernorates();
}

function fillGovernorates() {
  const sel = $("gouvernorat");
  const keep = sel.value;
  sel.length = 1;
  for (const g of governorates) sel.add(new Option(lang === "ar" ? g.ar : g.fr, g.fr));
  sel.value = keep;
}

async function loadGovernorates() {
  try {
    const r = await fetch("gouvernorats");
    governorates = await r.json();
    fillGovernorates();
  } catch { /* the field stays optional */ }
}

function showError(msg) {
  $("error").textContent = msg;
  $("error").hidden = !msg;
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

function render(r) {
  const t = I18N[lang];
  const badge = $("badge");
  badge.className = `badge ${r.issue}`;
  badge.textContent = t.issue[r.issue] || r.issue;
  $("confidence").textContent = r.diagnostic && r.diagnostic.confiance != null
    ? `${t.confidence} ${r.diagnostic.confiance} %` : "";
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
    const li = document.createElement("li");
    const b = document.createElement("b"); b.textContent = s.agent;
    li.append(b, document.createTextNode(` — ${s.action} (${s.duree_ms} ms)`));
    trace.append(li);
  }
  const seen = $("seen");
  seen.replaceChildren();
  const d = r.diagnostic;
  if (d && d.top3) {
    const head = document.createElement("li");
    head.textContent = `${t.route[d.routing] || d.routing} → ${t.model[d.task] || d.task}`;
    seen.append(head);
    for (const [cls, p] of d.top3) {
      const li = document.createElement("li");
      li.textContent = `${cls} : ${Math.round(p * 100)} %`;
      li.dir = "ltr";
      seen.append(li);
    }
    if (d.autre_modele) {
      const li = document.createElement("li");
      li.textContent = `(${d.autre_modele.classe} : ${Math.round(d.autre_modele.confiance * 100)} %)`;
      li.dir = "ltr";
      seen.append(li);
    }
  }
  $("seen-box").hidden = !seen.children.length;

  journalId = r.journal_id || null;
  fbCorrect = null;
  $("feedback").hidden = !journalId;
  $("fb-truth").hidden = true;
  $("fb-send").hidden = true;
  $("fb-done").hidden = true;
  $("fb-text").value = "";
  document.querySelectorAll("[data-correct]").forEach((b) => b.setAttribute("aria-pressed", "false"));

  $("result").hidden = false;
  $("result").scrollIntoView({ behavior: "smooth", block: "start" });
}

$("photo").addEventListener("change", () => {
  const f = $("photo").files[0];
  const img = $("preview");
  if (!f) { img.hidden = true; $("photo-hint").hidden = false; return; }
  img.src = URL.createObjectURL(f);
  img.hidden = false;
  $("photo-hint").hidden = true;
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
  if ($("culture").value.trim()) data.append("culture", $("culture").value.trim());

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
  window.scrollTo({ top: 0, behavior: "smooth" });
});

document.querySelectorAll(".lang button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));
setLang(readLang());
loadGovernorates();
