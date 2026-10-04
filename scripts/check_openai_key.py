"""List the OpenAI models this key can use. Never prints the key; only its shape if something looks wrong."""

import json
import os
import urllib.error
import urllib.request

raw = os.environ.get("OPENAI_API_KEY", "")
key = raw.strip().strip('"').strip("'")
print(f"key: starts with {key[:7]!r}, length {len(key)}, "
      f"had quotes/spaces around it: {raw != key}")
if not key:
    raise SystemExit("OPENAI_API_KEY is empty after loading .env")

req = urllib.request.Request("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        ids = sorted(m["id"] for m in json.load(r)["data"])
    print("\n".join(i for i in ids if i.startswith(("gpt", "o"))))
except urllib.error.HTTPError as e:
    err = json.loads(e.read() or b"{}").get("error", {})
    print("ERROR", e.code, err.get("code"), err.get("type"))
