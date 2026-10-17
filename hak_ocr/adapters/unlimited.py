"""Explicit local SGLang-compatible endpoint; never use remote arbitrary URLs."""
import base64
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from ..core import OCRPage

class UnlimitedAdapter:
    name = "unlimited"
    def __init__(self, endpoint="http://127.0.0.1:10000", *, timeout=180, model="Unlimited-OCR"):
        parsed = urlsplit(endpoint)
        if parsed.scheme != "http" or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("Only local HTTP OCR endpoints are allowed")
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
        except ValueError as exc:
            raise ValueError("Endpoint must be an explicit loopback IP address") from exc
        if not address.is_loopback:
            raise ValueError("Remote endpoints are disabled")
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self.model = model
    def recognize(self, image_paths: list[Path]) -> list[OCRPage]:
        opener = build_opener(ProxyHandler({}))
        result = []
        for i, path in enumerate(image_paths, 1):
            extension = path.suffix.lower()
            mime = "image/jpeg" if extension in (".jpeg", ".jpg") else "image/png" if extension == ".png" else "image/webp" if extension == ".webp" else "image/bmp"
            img = base64.b64encode(path.read_bytes()).decode("ascii")
            payload = {"model": self.model, "messages": [{"role": "user", "content": [
                {"type": "text", "text": "document parsing."},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img}"}}
            ]}], "temperature": 0, "stream": False, "skip_special_tokens": False,
                "images_config": {"image_mode": "base"}}
            request = Request(self.endpoint + "/v1/chat/completions", data=json.dumps(payload).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
            with opener.open(request, timeout=self.timeout) as response:
                data = json.load(response)
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise RuntimeError("Unsupported OCR response format")
            result.append(OCRPage(number=i, text=content))
        return result
