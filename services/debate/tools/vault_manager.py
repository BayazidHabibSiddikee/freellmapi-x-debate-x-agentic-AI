import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UNIQUE_DIR = BASE_DIR / "unique"

def manage_vault(agent, action, filename=None, content=None, category="misc"):
    """
    Manage agent-specific vaults in unique/
    agent: 'bayazid' or 'marin'
    action: 'write', 'read', 'list', 'delete'
    """
    vault_name = "bayazid_vault" if agent == "bayazid" else "limoni_vault"
    vault_path = UNIQUE_DIR / vault_name / category
    vault_path.mkdir(parents=True, exist_ok=True)

    if action == "list":
        # List all files across all categories in the agent's vault
        root_vault = UNIQUE_DIR / vault_name
        results = {}
        for root, dirs, files in os.walk(root_vault):
            rel_path = os.path.relpath(root, root_vault)
            if files:
                results[rel_path] = files
        return results

    if not filename:
        return {"error": "filename required for this action"}

    # Security: prevent directory traversal
    filename = os.path.basename(filename)
    file_path = vault_path / filename

    if action == "write":
        if not content: return {"error": "content required for write"}
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "success", "path": str(file_path.relative_to(BASE_DIR))}

    if action == "read":
        if not file_path.exists(): return {"error": "file not found"}
        with open(file_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}

    if action == "delete":
        if not file_path.exists(): return {"error": "file not found"}
        file_path.unlink()
        return {"status": "deleted"}

    return {"error": "invalid action"}

if __name__ == "__main__":
    # Test
    print(manage_vault("bayazid", "write", "test.txt", "Hello Vault", "technical_logs"))
    print(manage_vault("bayazid", "list"))
