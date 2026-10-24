# HAK OCR CENTER — Shared API contract v1.0

This is a **library API**, not an always-on network server. Applications may
adopt it individually when they are ready. No other HAK repository is modified.

## Intended consumers

| System | OCR use | Integration state |
| --- | --- | --- |
| LUONG_HAK / HAK_LUONG_OFFLINE | Attendance tables, signatures and staff documents | Not connected |
| HAK_KHO_OFFLINE | Woodchip weighbridge tickets | Not connected |
| HAK_HDMB | Contracts, CCCD and supporting documents | Not connected |
| hosovay_hak | Loan documents and bank forms | Not connected |
| HAK_WEBAPP_DNTT_DRAFT | Payment requests and weighbridge tickets | Not connected |

## Python example (only an installed local engine)

```python
from hak_ocr.platform import HAKOCRPlatform,PlatformConfig
from hak_ocr.adapters import PaddleAdapter
from hak_ocr.contracts import run_request

platform=HAKOCRPlatform({"paddle":PaddleAdapter()},PlatformConfig(default_engine="paddle"))
request={"api_version":"1.0","source_path":"C:/HAK/scans/phieu_can.png",
         "engine":"paddle","document_type":"phieu_can"}
response=run_request(platform,request)
# response["status"] is always NEEDS_REVIEW.
```

## Contract
Request: `api_version`, `source_path` (local only), `engine` (explicit), `document_type`.
Response: `api_version`, `document_type`, `status`, `approved`, `payroll_ready`, `ocr`.

- `status="NEEDS_REVIEW"` and `approved=false` are enforced.
- OCR results are proposals, never bank/payment/payroll authorization.
- Engines must be registered explicitly; no network downloads or fallback inside the facade.
- `health()` reports registration only. Actual engine readiness requires an independent smoke test.
- Do not use input file paths provided by untrusted remote callers without directory sandboxing.
- A future LAN/HTTP service requires authentication, RBAC, TLS, audit, rate limiting and strict path isolation before release.
- Keep training samples without real CCCD, payroll, or bank details in public CI.

## Compatibility and rollout
The existing `OCRService`, `hak-ocr` CLI and engine adapters remain unchanged.
Apps may migrate gradually through a versioned adapter (e.g. Python subprocess or IPC).
No automatic pushes to other repos, no writeback, no auto-approval.
