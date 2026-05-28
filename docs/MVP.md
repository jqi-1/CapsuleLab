# CapsuleLab MVP Validation

CapsuleLab's first supported golden path is a local Windows workstation running Docker Desktop. DGX/Linux support follows after the Windows path is reliable.

## Golden Path

```bash
cap init demo --template python-basic
cd demo
cap doctor
cap build
cap start
cap app start jupyter
cap app open jupyter
cap stop
```

## Current Target Platforms

- Windows 11 with Docker Desktop and WSL 2 enabled
- Linux workstation or DGX host with Docker Engine and NVIDIA Container Toolkit

Docker-dependent validation should be marked separately from pure configuration tests so CI can run fast checks without requiring a Docker daemon.
