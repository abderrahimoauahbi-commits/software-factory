"""Adaptateurs du Bootstrap : seul endroit où un outil précis est connu (Executable Schemas §20, §36).

Chaque fiche du registre désigne son adaptateur par nom (`detection.adapter`, `inventory.adapter`,
`verification.adapter`). Un adaptateur est en LECTURE SEULE et rend une observation, jamais une décision :
    {"present": bool | None, "version": str | None, "nature": VERIFIED | DECLARED | UNVERIFIABLE,
     "detail": str, "donnees": dict}
"""
from . import generiques, ide_vscode, paquets, runtime_claude_code, vcs_git

ADAPTATEURS = {
    "command_version": generiques.command_version,
    "executable_present": generiques.executable_present,
    "file_present": generiques.file_present,
    "python_runtime": generiques.python_runtime,
    "python_module": generiques.python_module,
    "node_package": paquets.node_package,
    "cargo_dependency": paquets.cargo_dependency,
    "git_repository": vcs_git.git_repository,
    "git_worktree": vcs_git.git_worktree,
    "git_files": vcs_git.git_files,
    "claude_code_config": runtime_claude_code.inventaire,
    "vscode_config": ide_vscode.inventaire,
}


def observation(present=None, version=None, nature="VERIFIED", detail="", **donnees) -> dict:
    return {"present": present, "version": version, "nature": nature, "detail": detail, "donnees": donnees}
