"""Writing of the answer, by CODE, in French or Arabic (the two languages of AgrIA: no darija in the answers).

Every sentence that carries a fact (diagnosis, product, dose, DAR, fertilizer, water, CRDA) comes from the phrase
table below and the values chosen by the agents: no language model ever writes or translates a fact. The fixed free
sentences (confirmation questions, warnings) have their Arabic in FIXED_AR. No language model is used: the passages
of the knowledge sheets (French or English) are quoted in French answers; an Arabic answer gives their links instead.
A free sentence with no Arabic in FIXED_AR (rare: a restriction text of the official list) stays in French.

The Arabic sentences were written for AgrIA and are to be checked by an Arabic speaker (docs/validation_langue.xlsx).
"""
from functools import lru_cache

from src.agent import paths  # noqa: F401
from common import query  # src/tools

MONTHS = {
    "fr": ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"],
    "ar": ["", "جانفي", "فيفري", "مارس", "أفريل", "ماي", "جوان", "جويلية", "أوت", "سبتمبر", "أكتوبر", "نوفمبر",
           "ديسمبر"],
}

NUTRIENTS = {"B": ("bore", "البور"), "Ca": ("calcium", "الكالسيوم"), "Fe": ("fer", "الحديد"),
             "K": ("potassium", "البوتاسيوم"), "Mg": ("magnésium", "المغنيزيوم"), "Mn": ("manganèse", "المنغنيز"),
             "N": ("azote", "الآزوت"), "P": ("phosphore", "الفوسفور"), "Zn": ("zinc", "الزنك")}

P = {
    "fr": {
        "photo_absente": "Pour poser un diagnostic, j'ai besoin d'une photo.",
        "photo_inutile": "Je ne vois pas de feuille ou de fruit à analyser sur cette photo.",
        "photo_conseil": "Envoyez une photo nette d'une feuille ou d'un fruit atteint, de près et à la lumière du jour.",
        "doute": "Je ne suis pas encore sûr du diagnostic ({doute}).",
        "doute_court": "Je ne suis pas encore sûr du diagnostic.",
        "pistes": "Pistes possibles : {pistes}.",
        "questions": "Pour vous répondre sans risque, dites-moi :",
        "crda": "Je préfère ne pas vous conseiller de produit pour ce cas. Contactez le CRDA{gov} : un technicien "
                "pourra examiner la plante.",
        "crda_gov": " de {gov}", "crda_sans_gov": " de votre gouvernorat",
        "sain": "Votre plante semble saine ({nom}, confiance {c} %). Aucun traitement n'est nécessaire.",
        "hypothese": "Il pourrait s'agir de : {nom} (confiance {c} %). C'est une hypothèse à confirmer : cette carence "
                     "a été peu observée sur votre culture.",
        "confirmer": "Pour confirmer :",
        "diagnostic": "Diagnostic : {nom} (confiance {c} %).",
        "produits": "Produits homologués en Tunisie pour ce cas :",
        "produit": "{nom} ({substances}) : dose {dose} ; délai avant récolte : {dar}",
        "dar_jours": "{n} jours", "dar_inconnu": "non précisé dans la liste officielle, voir l'étiquette",
        "aucun_produit": "Aucun produit n'est homologué en Tunisie contre ce problème.",
        "conseils": "Conseils tirés des fiches :",
        "engrais": "Engrais correcteurs disponibles :",
        "eau": "Irrigation en {mois} à {gov} : besoin moyen d'environ {mm} mm ({m3} m³/ha), soit {mmj} mm par jour "
               "après la pluie.",
        "a_savoir": "À savoir :",
        "fin": "Respectez la dose et le délai avant récolte indiqués sur l'étiquette. En cas de doute, contactez le "
               "CRDA.",
        "sain_nom": "plante saine", "carence": "carence en {x} ({sym})",
    },
    "ar": {
        "photo_absente": "أحتاج إلى صورة لتشخيص حالة النبتة.",
        "photo_inutile": "لا أرى في هذه الصورة ورقة أو ثمرة يمكن تحليلها.",
        "photo_conseil": "أرسل صورة واضحة لورقة أو ثمرة مصابة، من قريب وفي ضوء النهار.",
        "doute": "لست متأكدًا بعد من التشخيص.", "doute_court": "لست متأكدًا بعد من التشخيص.",
        "pistes": "احتمالات ممكنة: {pistes}.",
        "questions": "لأجيبك دون مخاطرة، أخبرني:",
        "crda": "أفضّل ألّا أنصحك بأي منتج في هذه الحالة. اتصل بالمندوبية الجهوية للتنمية الفلاحية (CRDA){gov}: "
                "يمكن لتقني أن يفحص النبتة.",
        "crda_gov": " بـ{gov}", "crda_sans_gov": " في ولايتك",
        "sain": "تبدو نبتتك سليمة ({nom}، نسبة الثقة {c} %). لا حاجة لأي علاج.",
        "hypothese": "قد يتعلق الأمر بـ: {nom} (نسبة الثقة {c} %). هذه فرضية يجب تأكيدها: هذا النقص لوحظ قليلًا "
                     "على زراعتك.",
        "confirmer": "للتأكد:",
        "diagnostic": "التشخيص: {nom} (نسبة الثقة {c} %).",
        "produits": "المبيدات المصادق عليها في تونس لهذه الحالة:",
        "produit": "{nom} ({substances}): الجرعة {dose}؛ المدة قبل الجني: {dar}",
        "dar_jours": "{n} أيام", "dar_inconnu": "غير محددة في القائمة الرسمية، راجع الملصق",
        "aucun_produit": "لا يوجد أي مبيد مصادق عليه في تونس ضد هذه المشكلة.",
        "conseils": "نصائح من البطاقات التقنية:",
        "sources": "مزيد من المعلومات (بالفرنسية):",
        "engrais": "أسمدة تصحيحية متوفرة:",
        "eau": "الري في {mois} بـ{gov}: حاجة متوسطة تقارب {mm} مم ({m3} م³/هكتار)، أي {mmj} مم في اليوم بعد "
               "احتساب الأمطار.",
        "a_savoir": "معلومات مهمة:",
        "fin": "احترم الجرعة والمدة قبل الجني المذكورتين على الملصق. في حالة الشك، اتصل بالـCRDA.",
        "sain_nom": "نبتة سليمة", "carence": "نقص {x} ({sym})",
    }
}
LANGS = tuple(P)

# fixed free sentences of the agents and tools (questions, warnings) -> Arabic
FIXED_AR = {
    "Quelle est la culture (tomate, olivier, agrumes, poivron, vigne…) ?":
        "ما هي الزراعة (طماطم، زيتون، قوارص، فلفل، عنب…)؟",
    "Pouvez-vous envoyer une autre photo, de près, d'une feuille ou d'un fruit atteint, à la lumière du jour ?":
        "هل يمكنك إرسال صورة أخرى عن قرب لورقة أو ثمرة مصابة، في ضوء النهار؟",
    "Depuis quand voyez-vous ces symptômes, et sur combien de plantes ?": "منذ متى تلاحظ هذه الأعراض، وعلى كم نبتة؟",
    "Les symptômes sont-ils plutôt sur les vieilles feuilles ou sur les jeunes ?":
        "هل تظهر الأعراض أكثر على الأوراق القديمة أم على الأوراق الفتية؟",
    "Les symptômes sont-ils surtout sur les bourgeons et jeunes feuilles ?":
        "هل تظهر الأعراض خاصة على البراعم والأوراق الفتية؟",
    "Les symptômes sont-ils surtout sur les jeunes feuilles ?": "هل تظهر الأعراض خاصة على الأوراق الفتية؟",
    "Les symptômes sont-ils surtout sur les jeunes feuilles et fruits ?":
        "هل تظهر الأعراض خاصة على الأوراق الفتية والثمار؟",
    "Les symptômes sont-ils surtout sur les vieilles feuilles ?": "هل تظهر الأعراض خاصة على الأوراق القديمة؟",
    "Voyez-vous : bords des feuilles qui jaunissent puis brûlent (nécrose marginale) ?":
        "هل تلاحظ اصفرار حواف الأوراق ثم احتراقها (موت الحواف)؟",
    "Voyez-vous : feuilles vert foncé à reflets violacés, plante chétive, retard de floraison ?":
        "هل تلاحظ أوراقًا خضراء داكنة مائلة إلى البنفسجي، ونبتة ضعيفة النمو، وتأخرًا في الإزهار؟",
    "Voyez-vous : jaunissement diffus entre les nervures avec petites taches nécrotiques ?":
        "هل تلاحظ اصفرارًا منتشرًا بين العروق مع بقع صغيرة ميتة؟",
    "Voyez-vous : jaunissement entre les nervures, nervures restant vertes ?":
        "هل تلاحظ اصفرارًا بين العروق مع بقاء العروق خضراء؟",
    "Voyez-vous : jaunissement net entre les nervures des jeunes feuilles, nervures bien vertes ; feuilles presque "
    "blanches si sévère ?":
        "هل تلاحظ اصفرارًا واضحًا بين عروق الأوراق الفتية مع بقاء العروق خضراء، وأوراقًا شبه بيضاء في الحالات الشديدة؟",
    "Voyez-vous : jaunissement uniforme de toute la feuille, en commençant par le bas de la plante ; croissance "
    "ralentie ?":
        "هل تلاحظ اصفرارًا متجانسًا للورقة كلها يبدأ من أسفل النبتة، مع بطء في النمو؟",
    "Voyez-vous : jeunes feuilles déformées, brûlure des pointes ; cul noir des fruits ?":
        "هل تلاحظ تشوه الأوراق الفتية واحتراق أطرافها، واسوداد أسفل الثمار؟",
    "Voyez-vous : petites feuilles étroites en rosette, jaunissement entre les nervures, entre-noeuds courts ?":
        "هل تلاحظ أوراقًا صغيرة ضيقة متجمعة على شكل وردة، واصفرارًا بين العروق، وقصر المسافات بين العقد؟",
    "Voyez-vous : pointes de croissance déformées ou mortes, feuilles épaisses et cassantes ; fruits déformés ou "
    "fendus ?":
        "هل تلاحظ تشوه قمم النمو أو موتها، وأوراقًا سميكة سهلة الكسر، وثمارًا مشوهة أو متشققة؟",
    "vise l'insecte qui transmet le virus, pas le virus lui-même (aucun produit ne guérit une plante virosée)":
        "يستهدف الحشرة الناقلة للفيروس وليس الفيروس نفسه (لا يوجد مبيد يعالج نبتة مصابة بفيروس)",
    "cible proche (mêmes symptômes, autre agent) : seulement après confirmation du diagnostic":
        "هدف قريب (أعراض متشابهة وعامل مختلف): لا يُستعمل إلا بعد تأكيد التشخيص",
    "homologué pour un groupe de cultures qui contient cette culture (par exemple « arboriculture »)":
        "مصادق عليه لمجموعة زراعات تشمل هذه الزراعة (مثلًا «الأشجار المثمرة»)",
    "autorisation provisoire de vente": "ترخيص مؤقت للبيع",
    "délai avant récolte non précisé dans la liste officielle pour certains produits : voir l'étiquette":
        "المدة قبل الجني غير محددة في القائمة الرسمية لبعض المنتجات: راجع الملصق",
    "sur le poivron, une plante saine peut être prise pour une carence en zinc : répondez aux questions avant "
    "d'acheter un engrais":
        "على الفلفل، قد تُعتبر نبتة سليمة مصابة بنقص الزنك: أجب عن الأسئلة قبل شراء أي سماد",
    "hors palmier dattier, la carence en manganèse est souvent mal reconnue sur photo : répondez aux questions "
    "avant d'acheter un engrais":
        "في غير نخيل التمر، كثيرًا ما لا يُتعرّف على نقص المنغنيز من الصورة: أجب عن الأسئلة قبل شراء أي سماد",
}


def fixed_ar(text):
    """Arabic of a fixed sentence, also as "<product> : <sentence>"; None if unknown."""
    if text in FIXED_AR:
        return FIXED_AR[text]
    if " : " in text:
        name, rest = text.split(" : ", 1)
        if rest in FIXED_AR:
            return f"{name}: {FIXED_AR[rest]}"
    return None

GOV_AR = {"Tunis": "تونس", "Ariana": "أريانة", "Ben Arous": "بن عروس", "Manouba": "منوبة", "Nabeul": "نابل",
          "Zaghouan": "زغوان", "Bizerte": "بنزرت", "Béja": "باجة", "Jendouba": "جندوبة", "Le Kef": "الكاف",
          "Siliana": "سليانة", "Sousse": "سوسة", "Monastir": "المنستير", "Mahdia": "المهدية", "Sfax": "صفاقس",
          "Kairouan": "القيروان", "Kasserine": "القصرين", "Sidi Bouzid": "سيدي بوزيد", "Gabès": "قابس",
          "Médenine": "مدنين", "Tataouine": "تطاوين", "Gafsa": "قفصة", "Tozeur": "توزر", "Kébili": "قبلي"}


def gov_label(gov, lang):
    return gov if lang == "fr" else GOV_AR.get(gov, gov)


def _first(cell):
    return str(cell).split("/")[0].split("|")[0].strip() if cell else None


@lru_cache(maxsize=1)
def _arabic_names():
    """model class or crop code -> (Arabic standard, Tunisian Arabic) names from the lexicon."""
    out = {}
    for r in query("SELECT type, lien, ar_msa, ar_tn FROM lexique WHERE lien IS NOT NULL"):
        if r["type"] not in ("culture", "maladie", "ravageur"):
            continue
        msa, tn = _first(r["ar_msa"]), _first(r["ar_tn"])
        if not (msa or tn):
            continue
        for key in str(r["lien"]).split():
            out.setdefault(key, (msa or tn, tn or msa))
    return out


def class_label(cls, french_name, lang):
    """Name of a model class in the language of the answer (French name kept in brackets when translated)."""
    if lang == "fr" or not cls:
        return french_name
    i = 0
    if cls.endswith("_deficiency"):
        sym = cls.split("_")[0]
        return P[lang]["carence"].format(x=NUTRIENTS.get(sym, (sym, sym))[1], sym=sym)
    if cls == "healthy" or cls.endswith("__healthy"):
        crop = _arabic_names().get(cls.split("__")[0]) if "__" in cls else None
        return P[lang]["sain_nom"] + (f" ({crop[i]})" if crop else "")
    names = _arabic_names().get(cls)
    return f"{names[i]} ({french_name})" if names else french_name


def compose(d, lang="fr"):
    """Answer text, in French or Arabic, from the facts `d` gathered by the agents."""
    t = P[lang]

    def free(text):  # fixed sentence: its Arabic from FIXED_AR, else kept in French
        return text if lang == "fr" else fixed_ar(text) or text

    def bullets(lines):
        return "\n".join(f"- {x}" for x in lines if x)

    issue, parts = d["issue"], []
    if issue == "autre_photo":
        parts.append((t["photo_absente"] if d.get("sans_photo") else t["photo_inutile"]) + " " + t["photo_conseil"])
    elif issue == "question":
        parts.append(t["doute"].format(doute=d["doute"]) if d.get("doute") and lang == "fr" else t["doute_court"])
        if d.get("pistes"):
            parts.append(t["pistes"].format(pistes="، ".join(class_label(c, n, lang) for c, n in d["pistes"])
                                             if lang != "fr" else ", ".join(n for _, n in d["pistes"])))
        parts.append(t["questions"] + "\n" + bullets(free(q) for q in d.get("questions", [])))
    elif issue == "crda":
        gov = t["crda_gov"].format(gov=gov_label(d["gouvernorat"], lang)) if d.get("gouvernorat") else t["crda_sans_gov"]
        parts.append(t["crda"].format(gov=gov))
    else:
        diag = d["diagnostic"]
        nom = class_label(diag.get("classe"), diag["nom"], lang)
        if diag.get("sain"):
            parts.append(t["sain"].format(nom=nom, c=diag["confiance"]))
        elif d.get("hypothese"):
            parts.append(t["hypothese"].format(nom=nom, c=diag["confiance"]))
            if d.get("questions"):
                parts.append(t["confirmer"] + "\n" + bullets(free(q) for q in d["questions"]))
        else:
            parts.append(t["diagnostic"].format(nom=nom, c=diag["confiance"]))
        if d.get("produits"):
            parts.append(t["produits"] + "\n" + bullets(
                t["produit"].format(nom=p["nom"], substances=p["substances"], dose=p["dose"],
                                    dar=t["dar_jours"].format(n=p["dar_jours"]) if p["dar_jours"] is not None
                                    else t["dar_inconnu"])
                for p in d["produits"]))
        elif d.get("aucun_produit"):
            parts.append(t["aucun_produit"])
        if d.get("conseils") and lang == "fr":
            parts.append(t["conseils"] + "\n" + bullets(d["conseils"]))
        elif d.get("conseils") and d.get("sources"):
            parts.append(t["sources"] + "\n" + bullets(f"{s['fiche']} : {s['lien']}" for s in d["sources"]))
        if d.get("engrais"):
            parts.append(t["engrais"] + "\n" + bullets(
                f"{e['nom']} ({e['nutriment']} {e['teneur_pct']} %)" if e.get("teneur_pct") else e["nom"]
                for e in d["engrais"]))
        w = d.get("eau")
        if w:
            parts.append(t["eau"].format(mois=MONTHS[lang][w["mois"]], gov=gov_label(w["gouvernorat"], lang), mm=w["mm"], m3=w["m3"],
                                         mmj=w["mmj"]))
        if d.get("avertissements"):
            parts.append(t["a_savoir"] + "\n" + bullets(free(a) for a in d["avertissements"]))
        if not diag.get("sain"):
            parts.append(t["fin"])
    return "\n\n".join(parts)
