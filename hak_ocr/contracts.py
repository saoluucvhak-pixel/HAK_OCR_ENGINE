"""Versioned JSON contracts and conservative payload checks for HAK clients."""

API_VERSION="1.0"
SUPPORTED_DOCUMENTS=frozenset({
    "generic","bang_cham_cong","phieu_can","hoa_don","hop_dong",
    "chung_tu_thanh_toan","bang_ke","cccd"
})

def validate_request(request):
    if not isinstance(request,dict):
        raise TypeError("Request must be a JSON object")
    required={"api_version","source_path","engine","document_type"}
    missing=required-request.keys()
    if missing:
        raise ValueError("Missing fields: "+",".join(sorted(missing)))
    if request["api_version"] != API_VERSION:
        raise ValueError("Unsupported API version")
    if request["document_type"] not in SUPPORTED_DOCUMENTS:
        raise ValueError("Unsupported document type")
    if not isinstance(request["source_path"],str) or not request["source_path"].strip():
        raise ValueError("Local source_path required")
    if not isinstance(request["engine"],str) or not request["engine"].strip():
        raise ValueError("Explicit OCR engine required")
    if "approved" in request or "payroll_ready" in request:
        raise ValueError("Clients cannot set review/approval state")
    return {"api_version":API_VERSION, "source_path":request["source_path"],
            "engine":request["engine"],"document_type":request["document_type"]}

def run_request(platform, request):
    item=validate_request(request)
    return platform.recognize(item["source_path"],engine=item["engine"],
                              document_type=item["document_type"])
