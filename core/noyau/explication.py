"""Explication en clair d'une demande de décision humaine (Playbook v3.3 ; ADR-0017 R12, TCB d'affichage).

Le texte est ENGENDRÉ PAR LE CODE à partir des faits de la demande (son contexte haché) et, pour un épinglage, de la
comparaison avec la dernière référence approuvée. Il n'emprunte rien au récit libre de l'agent (`purpose`), qui
reste affiché à part et signalé comme tel : un agent ne doit pas pouvoir convaincre l'humain par un beau texte.

Chaque explication répond à quatre questions : ce que vous approuvez · ce que cela permet · ce que cela ne permet
pas · comment revenir en arrière.
"""
from __future__ import annotations

def role_fichier(chemin: str, roles: dict | None = None) -> str:
    """Rôle d'un fichier couvert, d'après la table de la politique d'épinglage (préfixe le plus long d'abord)."""
    for prefixe in sorted(roles or {}, key=len, reverse=True):
        if chemin == prefixe or chemin.startswith(prefixe):
            return str(roles[prefixe])
    return "fichier de gouvernance"


def _bloc(approuver: str, permet: list[str], ne_permet_pas: list[str], retour: str, details: list[str] = ()) -> str:
    lignes = ["CE QUE VOUS APPROUVEZ", f"  {approuver}"]
    if details:
        lignes += ["DÉTAIL"] + [f"  {d}" for d in details]
    lignes += ["CE QUE CELA PERMET"] + [f"  - {p}" for p in permet]
    lignes += ["CE QUE CELA NE PERMET PAS"] + [f"  - {p}" for p in ne_permet_pas]
    lignes += ["POUR REVENIR EN ARRIÈRE", f"  {retour}"]
    return "\n".join(lignes)


def _epinglage(ctx: dict, reference: dict | None, roles: dict | None) -> str:
    fichiers = ctx.get("files") or {}
    details = []
    if reference is None:
        details.append(f"première référence : {len(fichiers)} fichiers deviennent la version de confiance")
    else:
        avant = reference.get("files") or {}
        modifies = sorted(f for f in fichiers if f in avant and avant[f] != fichiers[f])
        ajoutes = sorted(f for f in fichiers if f not in avant)
        retires = sorted(f for f in avant if f not in fichiers)
        if not (modifies or ajoutes or retires):
            details.append("aucun fichier n'a changé depuis la dernière référence approuvée")
        details += [f"modifié : {f} — {role_fichier(f, roles)}" for f in modifies]
        details += [f"ajouté à la surveillance : {f} — {role_fichier(f, roles)}" for f in ajoutes]
        details += [f"retiré de la surveillance : {f} — {role_fichier(f, roles)}" for f in retires]
    return _bloc(f"la version actuelle de {len(fichiers)} fichiers de gouvernance devient la version de confiance",
                 ["la Factory redevient READY : missions et campagnes peuvent de nouveau être lancées",
                  "toute modification FUTURE de ces fichiers sera de nouveau signalée et bloquera les lancements"],
                 ["aucun droit nouveau n'est donné à un agent par cette approbation elle-même",
                  "les fichiers ne sont pas modifiés : vous validez leur état présent"],
                 "remettre les fichiers dans leur état précédent (gestion de versions), puis approuver une nouvelle référence",
                 details)


def _habilitation_provisoire(ctx: dict) -> str:
    return _bloc(f"l'agent « {ctx.get('agent')} » peut exécuter des tickets jusqu'à la criticité "
                 f"{ctx.get('max_criticality')}, sur {', '.join(ctx.get('projects') or [])}, du "
                 f"{ctx.get('requested_at')} au {ctx.get('expires_at')}",
                 ["l'agent travaille dans des copies isolées du projet, jamais dans le dossier de travail",
                  "chaque fichier écrit doit rester dans le périmètre du ticket (contrôlé avant et après)",
                  "il peut servir à mener sa campagne d'évaluation"],
                 [f"aucune action au-delà de {ctx.get('max_criticality')} (C3 et C4 : jamais)",
                  "aucune fusion dans le projet sans votre revue de code",
                  "aucun accès à la production ni à une base réelle"],
                 "elle expire seule à la date indiquée ; pour l'arrêter plus tôt, retirer le bloc "
                 "provisional_habilitation de la fiche de l'agent")


def _habilitation(ctx: dict) -> str:
    ev = ctx.get("evaluation") or {}
    return _bloc(f"l'agent « {ctx.get('agent')} » est HABILITÉ jusqu'à {ctx.get('max_criticality')} sur "
                 f"{', '.join(ctx.get('projects') or [])} avec le modèle {ctx.get('model')}, du "
                 f"{ctx.get('granted_at')} au {ctx.get('expires_at')}",
                 ["l'agent est considéré comme évalué : il n'a plus besoin d'habilitation provisoire",
                  "décision fondée sur le rapport d'évaluation dont l'empreinte est indiquée"],
                 ["un autre modèle, un autre projet ou une criticité supérieure exigent une nouvelle évaluation",
                  "aucune fusion sans votre revue de code"],
                 "elle expire seule ; un changement de modèle, de consigne ou de suite impose une réévaluation",
                 [f"rapport d'évaluation : {str(ev.get('report_sha256'))[:12]}",
                  f"suite d'évaluation : {str(ev.get('suite_sha256'))[:12]}"])


def _exception(ctx: dict) -> str:
    p = ctx.get("scope") or {}
    return _bloc(f"la règle {ctx.get('rule')} est levée pour UNE action précise, {ctx.get('max_uses')} fois au plus, "
                 f"pendant {ctx.get('duration_hours')} h",
                 [f"l'action exacte : {p.get('action')} par {((p.get('actor') or {}).get('id'))} sur "
                  f"{(p.get('resource') or {}).get('path') or (p.get('resource') or {}).get('id')}",
                  "toutes les autres règles continuent de s'appliquer"],
                 ["aucune autre action, aucun autre fichier, aucun autre agent", "aucune prolongation automatique"],
                 "« python -P factory.py exception revoke " + str(ctx.get("exception_id")) + " --motif … »",
                 [f"motif déclaré : {ctx.get('reason')}"])


def _plan(ctx: dict) -> str:
    etapes = [f"étape {i} : dans {s.get('cwd')}, lancer « {' '.join(s.get('argv') or [])} »"
              for i, s in enumerate(ctx.get("steps") or [], 1)]
    return _bloc(f"vous exécuterez vous-même le plan « {ctx.get('title')} » ({len(etapes)} étape(s)), une seule fois",
                 ["seules les étapes listées seront lancées, exactement comme écrites", "chaque étape est tracée"],
                 ["aucune étape ajoutée ou modifiée après votre approbation", "aucune exécution par un agent"],
                 "une étape déjà lancée ne s'annule pas : relisez chaque commande avant d'approuver", etapes)


def _revue(ctx: dict) -> str:
    return _bloc(f"la revue de code du ticket {ctx.get('ticket_id')} ({ctx.get('ticket_criticality')}) : le diff "
                 f"affiché est accepté tel quel",
                 ["le ticket peut avancer vers la fusion"], ["aucune modification après la revue n'est couverte"],
                 "« REFUSE » demande des modifications ; un code modifié après approbation exige une nouvelle revue",
                 [f"fichiers : {', '.join(ctx.get('changes') or [])}"])


def _decision(ctx: dict) -> str:
    reponse = ctx.get("proposed_answer")
    return _bloc(f"la décision {ctx.get('decision_id')} du projet {ctx.get('project_id')} : {ctx.get('question')}"
                 + (f" — réponse : {reponse}" if reponse else ""),
                 ["les tickets du projet qui citent cette décision (dependencies.decisions) cessent d'être bloqués par "
                  "elle ; ils restent soumis à tous leurs autres contrôles"],
                 ["aucune exécution, aucune installation, aucun droit nouveau pour un agent"],
                 "« REFUSE » laisse ces tickets bloqués ; une décision se révise par une nouvelle demande, jamais en "
                 "modifiant celle-ci")


def expliquer(ctx: dict, reference_epinglage: dict | None = None, roles_fichiers: dict | None = None) -> str:
    """Texte en clair d'une demande, engendré à partir de son contexte (faits hachés), jamais du récit de l'agent."""
    genre = (ctx or {}).get("kind")
    if genre == "PIN_REFERENCE":
        return _epinglage(ctx, reference_epinglage, roles_fichiers)
    if genre == "AGENT_PROVISIONAL_HABILITATION":
        return _habilitation_provisoire(ctx)
    if genre == "AGENT_HABILITATION":
        return _habilitation(ctx)
    if genre == "POLICY_EXCEPTION":
        return _exception(ctx)
    if genre == "HUMAN_EXECUTION_PLAN":
        return _plan(ctx)
    if genre == "CODE_REVIEW":
        return _revue(ctx)
    if genre == "HUMAN_DECISION":
        return _decision(ctx)
    return _bloc(f"une demande de type {genre or 'inconnu'}",
                 ["voir le contexte exact affiché"], ["aucune explication automatique pour ce type"],
                 "refuser en cas de doute : l'absence de réponse n'est jamais un accord")
