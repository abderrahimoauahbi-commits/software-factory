# core

Services permanents du Factory Core (Playbook §2.3).

| Élément | Statut |
|---|---|
| `schemas/` — Executable Schemas v1.0 : énumérations, cycles de vie (tables de transitions), 29 schémas d'objets | **implémenté** (lus et appliqués par le Bootstrap) |
| `noyau/` — cœur partagé : périmètre de lecture, exécuteur sous liste blanche, registre, constats et preuves, masquage (ADR-0003) | **implémenté** ; tests dans `tests/` |
| `noyau/validation.py` — moteur de validation : VALID, INVALID, REJECTED ; règles déclarées par les schémas (ADR-0004) | **implémenté** ; `tests/test_validation.py` |
| `schemas/relations.yaml` — modèle de données (42 relations) ; `schemas/trust.yaml` — identité, confiance, invariants (ADR-0005) | **implémenté** ; `tests/test_modeles_securite.py` |
| `noyau/politique.py` — Policy Engine v1 ; `noyau/approbation.py` — approbations liées au contexte ; `noyau/sauvegarde.py` — sauvegarde vérifiée (ADR-0006) | **implémenté** ; `tests/test_politique.py`, `tests/test_sauvegarde.py` |
| `noyau/etats.py`, `noyau/audit.py`, `noyau/preuves.py`, `noyau/portes.py` — moteur d'états, journal chaîné, preuves, portes humaines (ADR-0007) | **implémenté** ; `tests/test_etats.py`, `tests/test_audit_preuves.py` |
| `noyau/contexte.py` — assemblage du Policy Engine et du moteur d'états depuis la Factory (CLI, future garde de l'agent) | **implémenté** ; `tests/test_cli.py` |
| `noyau/execution.py` — plateforme d'exécution v1 : espace isolé, non-débordement, gates prouvés (ADR-0009) | **implémenté** ; `tests/test_execution.py` |
| Orchestrator, Ticket Factory, Quality Gate Manager, services de gouvernance et de pilotage | cible — non implémenté (Playbook §17.2 règle 4) |

Les extensions des schémas propres à la Factory sont listées dans l'ADR-0002 (à ratifier en v1.1).
