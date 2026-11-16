"""Language model used by the agents that write: Coordinateur (compose the answer) and Linguistique (translate).

The LLM only WRITES. The facts it may use (diagnosis, products, doses, DAR, fertilizers, water, passages) are chosen
by code and given in `data`; the Vérificateur checks its text in code afterwards. Backends:

  template (default)  no LLM, no network: fills French templates from the data. Used by the tests and as offline
                      fallback; it cannot translate (the answer stays in French, with "langue": "fr").
  real LLM            to plug in once chosen (API or local Ollama): implement LLM.write() and select it with the
                      environment variable AGRIA_LLM.
"""
import os


class LLM:
    name = "base"

    def write(self, task, data):
        """task: "rediger" (data = case facts, returns French text) or "traduire" (data = {texte, langue})."""
        raise NotImplementedError


class TemplateLLM(LLM):
    name = "template"

    def write(self, task, data):
        if task == "traduire":
            return data["texte"]  # no translation without a language model
        return compose_french(data)


def _bullets(lines):
    return "\n".join(f"- {x}" for x in lines if x)


def compose_french(d):
    """French answer from the facts gathered by the agents (the same facts a real LLM receives)."""
    issue = d["issue"]
    parts = []
    if issue == "autre_photo":
        parts.append(("Pour poser un diagnostic, j'ai besoin d'une photo." if d.get("sans_photo") else
                      "Je ne vois pas de feuille ou de fruit à analyser sur cette photo.")
                     + " Envoyez une photo nette d'une feuille ou d'un fruit atteint, de près et à la lumière du jour.")
    elif issue == "question":
        parts.append(f"Je ne suis pas encore sûr du diagnostic ({d.get('doute', 'confiance faible')}).")
        if d.get("pistes"):
            parts.append("Pistes possibles : " + ", ".join(d["pistes"]) + ".")
        parts.append("Pour vous répondre sans risque, dites-moi :\n" + _bullets(d.get("questions", [])))
    elif issue == "crda":
        parts.append("Je préfère ne pas vous conseiller de produit pour ce cas. Contactez le CRDA"
                     + (f" de {d['gouvernorat']}" if d.get("gouvernorat") else " de votre gouvernorat")
                     + " : un technicien pourra examiner la plante.")
    else:
        diag = d["diagnostic"]
        if diag.get("sain"):
            parts.append(f"Votre plante semble saine ({diag['nom']}, confiance {diag['confiance']} %). "
                         "Aucun traitement n'est nécessaire.")
        elif d.get("hypothese"):
            parts.append(f"Il pourrait s'agir de : {diag['nom']} (confiance {diag['confiance']} %). C'est une "
                         "hypothèse à confirmer : cette carence a été peu observée sur votre culture.")
            if d.get("questions"):
                parts.append("Pour confirmer :\n" + _bullets(d["questions"]))
        else:
            parts.append(f"Diagnostic : {diag['nom']} (confiance {diag['confiance']} %).")
        if d.get("produits"):
            parts.append("Produits homologués en Tunisie pour ce cas :\n" + _bullets(
                f"{p['nom']} ({p['substances']}) : dose {p['dose']} ; délai avant récolte : {p['dar_message']}"
                for p in d["produits"]))
        elif d.get("aucun_produit"):
            parts.append("Aucun produit n'est homologué en Tunisie contre ce problème.")
        if d.get("conseils"):
            parts.append("Conseils tirés des fiches :\n" + _bullets(d["conseils"]))
        if d.get("engrais"):
            parts.append("Engrais correcteurs disponibles :\n" + _bullets(
                f"{e['nom']} ({e['nutriment']} {e['teneur_pct']} %)" if e.get("teneur_pct") else e["nom"]
                for e in d["engrais"]))
        if d.get("eau"):
            parts.append(d["eau"])
        if d.get("avertissements"):
            parts.append("À savoir :\n" + _bullets(d["avertissements"]))
        if not diag.get("sain"):
            parts.append("Respectez la dose et le délai avant récolte indiqués sur l'étiquette. En cas de doute, "
                         "contactez le CRDA.")
    return "\n\n".join(parts)


def get_llm():
    name = os.environ.get("AGRIA_LLM", "template")
    if name == "template":
        return TemplateLLM()
    raise ValueError(f"LLM {name!r} non branché : voir src/agent/llm.py")
