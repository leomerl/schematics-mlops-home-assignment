import base64
import os
import subprocess
import tempfile
import yaml

REPO_URL = os.environ.get("GITOPS_REPO_URL")
TOKEN = os.environ.get("GITOPS_TOKEN")
BRANCH = os.environ.get("GITOPS_BRANCH", "main")
MODELS_FILE = os.environ.get("GITOPS_MODELS_FILE", "09-gitops/deploy/charts/bl-ranker/models.yaml")
AUTHOR = ["-c", "user.name=bl-ranker-gates", "-c", "user.email=bl-ranker-gates@users.noreply.github.com"]
PUSH_ATTEMPTS = 3
MODELS_KEY = "models"
NO_MODEL = "none"


class Slot:
    CHAMPION = "champion"
    CHALLENGER = "challenger"


def git_env() -> dict:
    env = dict(os.environ)
    if TOKEN:
        credentials = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader", GIT_CONFIG_VALUE_0=f"Authorization: Basic {credentials}")
    return env


def git(*args: str, cwd: str | None = None) -> None:
    subprocess.run(["git", *AUTHOR, *args], cwd=cwd, env=git_env(), check=True, capture_output=True, text=True)


def update_models_file(path: str, changes: dict[str, str]) -> bool:
    with open(path) as f:
        content = yaml.safe_load(f)
    if all(content[MODELS_KEY].get(slot) == version for slot, version in changes.items()):
        return False
    content[MODELS_KEY].update(changes)
    with open(path, "w") as f:
        yaml.safe_dump(content, f, sort_keys=False)
    return True


def write_models(changes: dict[str, str], message: str) -> None:
    if not REPO_URL:
        print(f"GITOPS_REPO_URL not set, {MODELS_FILE} not updated: {changes}")
        return
    for attempt in range(1, PUSH_ATTEMPTS + 1):
        with tempfile.TemporaryDirectory() as workdir:
            git("clone", "--depth", "1", "--branch", BRANCH, REPO_URL, workdir)
            if not update_models_file(os.path.join(workdir, MODELS_FILE), changes):
                print(f"{MODELS_FILE} already has {changes}")
                return
            git("commit", "-am", message, cwd=workdir)
            try:
                git("push", "origin", f"HEAD:{BRANCH}", cwd=workdir)
            except subprocess.CalledProcessError as error:
                print(f"push attempt {attempt} rejected: {error.stderr.strip()}")
                continue
            print(f"committed to {BRANCH}: {message}")
            return
    raise RuntimeError(f"could not push {changes} to {BRANCH} after {PUSH_ATTEMPTS} attempts")
