from pathlib import Path


BASE_IMAGES = {
    "python": {
        "image": "python:3.12-slim",
        "gpu": False,
        "description": "Small CPU Python base image.",
    },
    "pytorch-cuda": {
        "image": "pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime",
        "gpu": True,
        "description": "PyTorch runtime with CUDA support.",
    },
    "tensorflow-cuda": {
        "image": "tensorflow/tensorflow:2.16.1-gpu",
        "gpu": True,
        "description": "TensorFlow GPU runtime.",
    },
}


def catalog() -> dict:
    return BASE_IMAGES


def dockerfile_preview(project_path: str, dockerfile: str = "Dockerfile") -> dict:
    path = Path(project_path) / dockerfile
    if not path.exists():
        return {"exists": False, "dockerfile": dockerfile, "content": ""}
    return {"exists": True, "dockerfile": dockerfile, "content": path.read_text()}


def byoc_checks(project_path: str, dockerfile: str = "Dockerfile") -> list[dict]:
    preview = dockerfile_preview(project_path, dockerfile)
    if not preview["exists"]:
        return [{"label": "Dockerfile", "ok": False, "detail": f"{dockerfile} missing"}]
    content = preview["content"]
    return [
        {"label": "Base image", "ok": "FROM " in content, "detail": "FROM present" if "FROM " in content else "Missing FROM"},
        {"label": "Python availability", "ok": "python" in content.lower() or "pip" in content.lower(), "detail": "Python/pip mentioned" if ("python" in content.lower() or "pip" in content.lower()) else "Not detected"},
        {"label": "Workspace", "ok": "WORKDIR" in content, "detail": "WORKDIR present" if "WORKDIR" in content else "Missing WORKDIR"},
    ]
