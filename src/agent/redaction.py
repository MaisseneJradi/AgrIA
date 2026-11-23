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
from dose_calc import TANK_L, area_text, qty_text
from hazard import LABELS as HAZARD_LABELS
from hazard import SEVERE
from mrl import mrl_number
from treatments import LIST_DATE

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
        "produits": "Produits homologués en Tunisie pour ce cas (liste DGSVCIA du {date}) :",
        "produit": "{nom} ({substances}) : dose {dose} ; délai avant récolte : {dar}",
        "dar_jours": "{n} jours", "dar_jour": "{n} jour", "dar_inconnu": "DAR non indiqué : vérifiez l'étiquette",
        "dar_complete": "{v} (complété d'après {source})",
        "aucun_produit": "Aucun produit n'est homologué en Tunisie contre ce problème (liste DGSVCIA du {date}).",
        "orientation": "Pour un examen sur place et des mesures adaptées à votre parcelle, contactez le CRDA{gov}.",
        "prevention": "Mesures de prévention :",
        "conseils": "Extraits des fiches :",
        "sources": "Pour en savoir plus :",
        "engrais": "Engrais correcteurs disponibles :",
        "eau": "Irrigation en {mois} à {gov} : besoin moyen d'environ {mm} mm ({m3} m³/ha), soit {mmj} mm par jour "
               "après la pluie.",
        "a_savoir": "À savoir :",
        "fin": "Respectez la dose et le délai avant récolte indiqués sur l'étiquette. En cas de doute, contactez le "
               "CRDA.",
        "sain_nom": "plante saine", "carence": "carence en {x} ({sym})",
        # step 3 of the phyto plan: why each product, products set aside for the situation, context questions
        "pourquoi": "Pourquoi : ", "sep": " ; ",
        "r_direct": "homologué contre ce problème sur votre culture",
        "r_vecteur": "vise l'insecte qui transmet la maladie",
        "r_groupe": "homologué pour un groupe de cultures qui contient la vôtre",
        "r_proche": "cible proche, seulement après confirmation du diagnostic",
        "r_bio_debut": "substances autorisées en agriculture biologique, à privilégier en début d'attaque",
        "r_bio": "substances autorisées en agriculture biologique",
        "r_toxicite": "classe de toxicité OMS {c} ({label})",
        # step 6: applicator and bee safety, weather (no verb of treatment: rule 9 reads these lines)
        "securite": "Sécurité :",
        "epi": "Protection : gants, bottes, lunettes, masque et vêtements qui couvrent bras et jambes pendant la "
               "préparation et l'application ; ne mangez, ne buvez et ne fumez pas ; lavez-vous et lavez vos vêtements "
               "après.",
        "tres_dangereux": "{nom} : classe OMS {c} ({label}) : jamais sans l'équipement complet indiqué sur "
                          "l'étiquette ; gardez les enfants et les animaux à l'écart.",
        "abeilles": "{nom} : très toxique pour les abeilles : n'appliquez pas pendant la floraison ni quand les abeilles "
                    "butinent ; appliquez tôt le matin ou le soir, loin des ruches.",
        "meteo_pluie": "Météo : pluie prévue dans les 24 heures ({mm} mm, probabilité jusqu'à {p} %) : attendez une "
                       "période sèche pour appliquer le produit, sinon il sera lessivé.",
        "meteo_vent": "Météo : vent jusqu'à {v} km/h dans les 12 prochaines heures : n'appliquez pas quand le vent "
                      "dépasse 15 km/h (le produit dérive vers les voisins, les ruches et l'eau).",
        "r_dar": "délai avant récolte de {dar} {j}",
        "r_dar_dth": "délai avant récolte de {dar} {j}, compatible avec votre récolte dans {dth} jours",
        "r_ue": "substances approuvées dans l'Union européenne",
        "r_rotation": "groupe {g}, différent de votre dernier traitement ({last})",
        "r_groupe": "groupe {g}",
        "r_groupe_faible_risque": "groupe {g} ; {shared} déjà utilisé, mais à faible risque de résistance",
        # step 5: practical dose (dose_calc.py); "L" of the sprayer in capital, quantities in g, kg, ml, l
        "lmr": "LMR de {nom} ({source}, {marche}) : ", "marche_local": "marché local",
        "marche_export": "export vers l'Union européenne",
        "lmr_absente": "{s} : LMR non trouvée, vérifiez auprès de l'acheteur ou du CRDA",
        "lmr_non_requise": "{s} : pas de LMR requise dans l'UE (annexe IV)",
        "dp": "Dose pratique : ", "dp_tank": "{q} pour un pulvérisateur de {l} L", "dp_area": "{q} pour vos {a} ha",
        "dp_tank_absent": "pour le pulvérisateur, la quantité dépend du volume de mélange par hectare : voir "
                          "l'étiquette",
        "dp_area_absent": "pour vos {a} ha, la quantité dépend du volume de mélange par hectare : voir l'étiquette",
        "c_meme_groupe": "même groupe que votre dernier traitement ({last}) : {n} produit(s)",
        "rotation": "Alternez les groupes de mode d'action (code FRAC ou IRAC indiqué sur l'étiquette) d'un traitement "
                    "à l'autre : répéter le même groupe favorise la résistance de la maladie ou du ravageur.",
        "rotation_impossible": "Aucun autre groupe que celui de votre dernier traitement ({last}) n'est homologué pour ce "
                               "cas : demandez conseil au CRDA avant de le répéter.",
        "ecartes": "Produits homologués écartés pour votre situation :",
        "aucun_adapte": "Aucun des {n} produits homologués contre ce problème (liste DGSVCIA du {date}) ne convient à "
                        "votre situation :",
        "c_dar_long": "délai avant récolte plus long que les {dth} jours avant votre récolte : {n} produit(s)",
        "c_non_ue": "substance non approuvée dans l'Union européenne (export) : {n} produit(s)",
        "c_ue_inconnu": "statut inconnu dans l'Union européenne (export) : {n} produit(s)",
        "c_non_bio": "non autorisé en agriculture biologique : {n} produit(s)",
        "verifier_dar": "Délai avant récolte non précisé dans la liste officielle pour certains produits : vérifiez sur "
                        "l'étiquette qu'il est inférieur aux {dth} jours qui restent avant votre récolte.",
        "bio_etiquette": "En agriculture biologique, vérifiez aussi que l'étiquette porte la mention « utilisable en "
                         "agriculture biologique ».",
        "affiner": "Pour affiner ma réponse, dites-moi :",
        "q_days_to_harvest": "Dans combien de jours pensez-vous récolter ?",
        "q_market": "Votre récolte part-elle à l'export (Union européenne) ou sur le marché local ?",
        "q_organic": "Votre parcelle est-elle en agriculture biologique ?",
        "q_stage": "Le problème commence-t-il (premières taches ou premiers dégâts, quelques plantes) ou est-il déjà "
                   "étendu ?",
        "q_last_treatment_group": "Quel produit avez-vous utilisé à votre dernier traitement ?",
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
        "produits": "المبيدات المصادق عليها في تونس لهذه الحالة (قائمة DGSVCIA بتاريخ {date}):",
        "produit": "{nom} ({substances}): الجرعة {dose}؛ المدة قبل الجني: {dar}",
        "dar_jours": "{n} أيام", "dar_inconnu": "غير مذكورة في القائمة: تحقق من الملصق",
        "dar_complete": "{v} (أُكملت حسب {source})",
        "aucun_produit": "لا يوجد أي مبيد مصادق عليه في تونس ضد هذه المشكلة (قائمة DGSVCIA بتاريخ {date}).",
        "orientation": "لفحص النبتة في المكان واتخاذ الإجراءات المناسبة لقطعتك، اتصل بالمندوبية الجهوية للتنمية "
                       "الفلاحية (CRDA){gov}.",
        "prevention": "إجراءات وقائية:",
        "conseils": "نصائح من البطاقات التقنية:",
        "sources": "مزيد من المعلومات (بالفرنسية أو بالإنجليزية):",
        "engrais": "أسمدة تصحيحية متوفرة:",
        "eau": "الري في {mois} بـ{gov}: حاجة متوسطة تقارب {mm} مم ({m3} م³/هكتار)، أي {mmj} مم في اليوم بعد "
               "احتساب الأمطار.",
        "a_savoir": "معلومات مهمة:",
        "fin": "احترم الجرعة والمدة قبل الجني المذكورتين على الملصق. في حالة الشك، اتصل بالـCRDA.",
        "sain_nom": "نبتة سليمة", "carence": "نقص {x} ({sym})",
        "pourquoi": "لماذا: ", "sep": "؛ ",
        "r_direct": "مصادق عليه ضد هذه المشكلة على زراعتك",
        "r_vecteur": "يستهدف الحشرة الناقلة للمرض",
        "r_groupe": "مصادق عليه لمجموعة زراعات تشمل زراعتك",
        "r_proche": "هدف قريب، لا يُستعمل إلا بعد تأكيد التشخيص",
        "r_bio_debut": "مواد فعالة مسموح بها في الفلاحة البيولوجية، تُفضَّل في بداية الإصابة",
        "r_bio": "مواد فعالة مسموح بها في الفلاحة البيولوجية",
        "r_toxicite": "صنف السمية {c} حسب منظمة الصحة العالمية ({label})",
        "securite": "السلامة:",
        "epi": "الوقاية: قفازات وأحذية طويلة ونظارات وكمامة وملابس تغطي الذراعين والساقين أثناء التحضير والاستعمال؛ لا "
               "تأكل ولا تشرب ولا تدخّن؛ اغتسل واغسل ملابسك بعد ذلك.",
        "tres_dangereux": "{nom}: صنف {c} حسب منظمة الصحة العالمية ({label}): لا يُستعمل أبدًا دون المعدات الكاملة "
                          "المذكورة على الملصق؛ أبعد الأطفال والحيوانات.",
        "abeilles": "{nom}: شديد السمية للنحل: لا تستعمله أثناء الإزهار ولا عندما يجمع النحل الرحيق؛ استعمله في الصباح "
                    "الباكر أو في المساء، بعيدًا عن الخلايا.",
        "meteo_pluie": "الطقس: أمطار متوقعة خلال 24 ساعة ({mm} مم، احتمال يصل إلى {p} %): انتظر فترة جافة لاستعمال "
                       "المنتج، وإلا سيجرفه المطر.",
        "meteo_vent": "الطقس: رياح تصل إلى {v} كم/س خلال الـ12 ساعة القادمة: لا تستعمل المنتج عندما تتجاوز الرياح 15 "
                      "كم/س (ينجرف نحو الجيران والخلايا والماء).",
        "r_dar": "مدة قبل الجني {dar} {j}",
        "r_dar_dth": "مدة قبل الجني {dar} {j}، تتوافق مع الجني بعد {dth} يومًا",
        "r_ue": "مواد فعالة مصادق عليها في الاتحاد الأوروبي",
        "r_rotation": "مجموعة {g} مختلفة عن آخر مداواة ({last})",
        "r_groupe": "مجموعة {g}",
        "r_groupe_faible_risque": "مجموعة {g}؛ {shared} مستعملة سابقًا لكن خطر المقاومة فيها ضعيف",
        "lmr": "الحد الأقصى للمتبقيات في {nom} ({source}، {marche}): ", "marche_local": "السوق المحلية",
        "marche_export": "التصدير نحو الاتحاد الأوروبي",
        "lmr_absente": "{s}: غير موجود، تحقق لدى المشتري أو الـCRDA",
        "lmr_non_requise": "{s}: لا يُشترط حد أقصى في الاتحاد الأوروبي (الملحق IV)",
        "dp": "الكمية العملية: ", "dp_tank": "{q} لمرشّة ظهرية سعتها {l} L", "dp_area": "{q} لمساحة {a} هكتار",
        "dp_tank_absent": "بالنسبة للمرشّة، الكمية حسب حجم المحلول في الهكتار: راجع الملصق",
        "dp_area_absent": "بالنسبة لمساحة {a} هكتار، الكمية حسب حجم المحلول في الهكتار: راجع الملصق",
        "c_meme_groupe": "نفس مجموعة آخر مداواة ({last}): {n} منتج",
        "rotation": "غيّر مجموعة طريقة التأثير (رمز FRAC أو IRAC المكتوب على الملصق) من مداواة إلى أخرى: تكرار نفس "
                    "المجموعة يساعد المرض أو الحشرة على اكتساب المقاومة.",
        "rotation_impossible": "لا توجد مجموعة مصادق عليها لهذه الحالة غير مجموعة آخر مداواة ({last}): اطلب نصيحة "
                               "الـCRDA قبل تكرارها.",
        "ecartes": "مبيدات مصادق عليها استُبعدت بسبب وضعيتك:",
        "aucun_adapte": "لا يناسب وضعيتك أيٌّ من المبيدات المصادق عليها ضد هذه المشكلة ({n}، قائمة DGSVCIA بتاريخ "
                        "{date}):",
        "c_dar_long": "مدة قبل الجني أطول من {dth} يومًا المتبقية قبل الجني: {n} منتج",
        "c_non_ue": "مادة فعالة غير مصادق عليها في الاتحاد الأوروبي (تصدير): {n} منتج",
        "c_ue_inconnu": "وضعية غير معروفة في الاتحاد الأوروبي (تصدير): {n} منتج",
        "c_non_bio": "غير مسموح به في الفلاحة البيولوجية: {n} منتج",
        "verifier_dar": "المدة قبل الجني غير محددة في القائمة الرسمية لبعض المنتجات: تأكد من الملصق أنها أقل من {dth} "
                        "يومًا المتبقية قبل الجني.",
        "bio_etiquette": "في الفلاحة البيولوجية، تأكد أيضًا أن الملصق يحمل عبارة «صالح للفلاحة البيولوجية».",
        "affiner": "لأدقّق إجابتي، أخبرني:",
        "q_days_to_harvest": "بعد كم يوم تنوي الجني؟",
        "q_market": "هل محصولك موجّه للتصدير (الاتحاد الأوروبي) أم للسوق المحلية؟",
        "q_organic": "هل قطعتك في الفلاحة البيولوجية؟",
        "q_stage": "هل المشكلة في بدايتها (أولى البقع أو الأضرار، بعض النباتات) أم أنها منتشرة؟",
        "q_last_treatment_group": "ما هو المنتج الذي استعملته في آخر مداواة؟",
    }
}
CAUSES = ("dar_long", "non_ue", "ue_inconnu", "non_bio", "meme_groupe")


def days_word(n, t):
    """French: 'jour' for 0 and 1, else 'jours'. Arabic: يوم (0, 1), يومان (2), أيام (3 to 10), يومًا (11 and more)."""
    if t is P["ar"]:
        return "يوم" if n <= 1 else "يومان" if n == 2 else "أيام" if n <= 10 else "يومًا"
    return t["dar_jours"].format(n="").strip() if n > 1 else t["dar_jour"].format(n="").strip()


def reason_text(r, t):
    """One reason code of ranking.py -> its sentence in the language of `t`."""
    code = r[0]
    if code == "relation":
        return t["r_" + r[1]]
    if code == "toxicite":
        return t["r_toxicite"].format(c=r[1], label=HAZARD_LABELS[r[1]][0 if t is P["fr"] else 1])
    if code == "dar":
        j = days_word(r[1], t)
        return t["r_dar_dth"].format(dar=r[1], j=j, dth=r[2]) if r[2] is not None else t["r_dar"].format(dar=r[1], j=j)
    if code == "rotation":
        return t["r_rotation"].format(g=r[1], last=r[2])
    if code == "groupe":
        return t["r_groupe"].format(g=r[1])
    if code == "groupe_faible_risque":
        return t["r_groupe_faible_risque"].format(g=r[1], shared=r[2])
    return t["r_" + code]


def dar_text(p, t):
    """DAR of a product line: '3 jours'; a validated completion says so ('non requis (DAR absent de la liste, complété
    d'après ...)'); unknown: 'DAR non indiqué : vérifiez l'étiquette'."""
    if p["dar_jours"] is None:
        return t["dar_inconnu"]
    v = p.get("dar_texte") or f"{p['dar_jours']} {days_word(p['dar_jours'], t)}"
    if p.get("dar_source") == "complement":
        return t["dar_complete"].format(v=v, source=p.get("dar_source_detail") or "")
    return v


def mrl_line(p, t, ctx):
    """'LMR de X (Codex, marché local) : Azoxystrobin 3 mg/kg (Tomatoes (subgroup)) ; ...' - the product name is on the
    line (the substances are chemistry: rule 9 reads only the lines without a product)."""
    items = []
    for m in p["lmr_marche"]:
        if m["valeur"] is None and m.get("non_requise"):
            items.append(t["lmr_non_requise"].format(s=m["substance"]))
        elif m["valeur"] is None:
            items.append(t["lmr_absente"].format(s=m["substance"]))
        else:
            items.append(f"{m['substance']} {mrl_number(m['valeur'])} mg/kg"
                         + (f" ({m['denree']})" if m.get("denree") else ""))
    market = t["marche_" + ctx.get("market", "local")]
    return t["lmr"].format(nom=p["nom"], source=p["lmr_marche"][0]["source"], marche=market) + t["sep"].join(items)


def number(x):
    """3.2 -> '3,2'; 22.0 -> '22'."""
    return f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def safety_lines(d, t, lang):
    """Protective equipment (always with a pesticide), very hazardous products (WHO Ia, Ib), products highly toxic to
    bees, weather of the next hours: all from validated data or the forecast, written by code."""
    lab = 0 if lang == "fr" else 1
    out = [t["epi"]]
    for p in d["produits"]:
        if p.get("classe_oms") in SEVERE:
            out.append(t["tres_dangereux"].format(nom=p["nom"], c=p["classe_oms"],
                                                  label=HAZARD_LABELS[p["classe_oms"]][lab]))
        if p.get("abeilles"):
            out.append(t["abeilles"].format(nom=p["nom"]))
    m = d.get("meteo") or {}
    if m.get("pluie"):
        out.append(t["meteo_pluie"].format(mm=number(m["pluie_mm"]), p=m.get("pluie_proba") or 0))
    if m.get("vent"):
        out.append(t["meteo_vent"].format(v=number(m["vent_max_kmh"])))
    return out


def practical_line(dp, t, lang):
    """dose_calc.practical_dose(...) -> 'Dose pratique : 48 g pour un pulvérisateur de 16 L ; 1,5 kg pour vos 0,5 ha'.
    The quantities are formatted by dose_calc (the Vérificateur checks them against the official dose)."""
    parts = []
    tank, area = dp.get("pulverisateur"), dp.get("surface")
    if tank:
        parts.append(t["dp_tank"].format(q=qty_text(tank["min"], tank["max"], tank["base"], lang),
                                         l=dp.get("reservoir_l", TANK_L)))
    elif dp.get("pulverisateur_absent"):
        parts.append(t["dp_tank_absent"])
    if area:
        parts.append(t["dp_area"].format(q=qty_text(area["min"], area["max"], area["base"], lang),
                                         a=area_text(area["ha"])))
    elif dp.get("surface_absente"):
        parts.append(t["dp_area_absent"].format(a=area_text(dp.get("ha_demandes")) if dp.get("ha_demandes") else ""))
    return t["dp"] + t["sep"].join(parts)


def set_aside_lines(ecartes, ctx, t, last=""):
    """Products set aside -> one line per cause with how many products (no name: they do not fit this case)."""
    counts = {c: sum(c in e["raisons"] for e in ecartes) for c in CAUSES}
    return [t["c_" + c].format(n=n, dth=ctx.get("days_to_harvest"), last=last) for c, n in counts.items() if n]
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
        ctx = d.get("contexte") or {}
        if d.get("produits"):
            parts.append(t["produits"].format(date=LIST_DATE) + "\n" + bullets(
                t["produit"].format(nom=p["nom"], substances=p["substances"], dose=p["dose"],
                                    dar=dar_text(p, t))
                # the reasons go on their own line: the product line keeps exactly its registered dose (rule 8)
                + (("\n  " + practical_line(p["dose_pratique"], t, lang)) if p.get("dose_pratique") else "")
                + (("\n  " + mrl_line(p, t, ctx)) if p.get("lmr_marche") else "")
                + ("\n  " + t["pourquoi"] + t["sep"].join(reason_text(r, t) for r in p["raisons"])
                   if p.get("raisons") else "")
                for p in d["produits"]))
            last = " + ".join(d.get("dernier_groupe") or [])
            if d.get("ecartes"):
                parts.append(t["ecartes"] + "\n" + bullets(set_aside_lines(d["ecartes"], ctx, t, last)))
            if d.get("rotation_impossible"):
                parts.append(t["rotation_impossible"].format(last=last))
            if d.get("rotation_conseil"):
                parts.append(t["rotation"])
            parts.append(t["securite"] + "\n" + bullets(safety_lines(d, t, lang)))
            if d.get("verifier_dar") is not None:
                parts.append(t["verifier_dar"].format(dth=d["verifier_dar"]))
            if ctx.get("organic") == "y":
                parts.append(t["bio_etiquette"])
        elif d.get("aucun_adapte"):
            parts.append(t["aucun_adapte"].format(n=d.get("n_candidats", 0), date=LIST_DATE) + "\n"
                         + bullets(set_aside_lines(d.get("ecartes", []), ctx, t,
                                                   " + ".join(d.get("dernier_groupe") or []))))
        elif d.get("aucun_produit"):
            parts.append(t["aucun_produit"].format(date=LIST_DATE))
        if d.get("questions_contexte"):
            parts.append(t["affiner"] + "\n" + bullets(t["q_" + q] for q in d["questions_contexte"]))
        if d.get("prevention"):  # validated rows of docs/conseils_prevention.csv, in the language of the answer
            parts.append(t["prevention"] + "\n" + bullets(p[lang] for p in d["prevention"]))
        if d.get("conseils") and lang == "fr":
            parts.append(t["conseils"] + "\n" + bullets(d["conseils"]))
        elif d.get("sources"):  # Arabic answer, or no French sentence to quote: the links of the sheets
            parts.append(t["sources"] + "\n" + bullets(f"{s['fiche']} : {s['lien']}" for s in d["sources"]))
        if d.get("orientation_crda"):  # nothing registered: a technician, never a product
            gov = t["crda_gov"].format(gov=gov_label(d["gouvernorat"], lang)) if d.get("gouvernorat") \
                else t["crda_sans_gov"]
            parts.append(t["orientation"].format(gov=gov))
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
        if not diag.get("sain") and not d.get("orientation_crda"):
            parts.append(t["fin"])
    return "\n\n".join(parts)
