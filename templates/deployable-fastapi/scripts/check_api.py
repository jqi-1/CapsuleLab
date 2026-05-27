import json
import sys
from urllib.request import urlopen


def main(base_url: str = "http://localhost:8000") -> int:
    with urlopen(f"{base_url.rstrip('/')}/health", timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "healthy":
        print(f"unexpected health payload: {payload}")
        return 1
    print("api health ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"))
