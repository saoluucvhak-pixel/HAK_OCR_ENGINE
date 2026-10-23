#!/bin/bash
# Chuyển model nhận dạng PaddleOCR (thư mục export: inference.json + inference.pdiparams + inference.yml) → ONNX cho js/main/paddle-rec.js.
# Chạy trên Linux / WSL: paddle2onnx 2.x bản Windows lỗi nạp DLL ("procedure could not be found") với paddlepaddle 3.3.1.
#
# Chuẩn bị 1 lần (không cần sudo):
#   uv python install 3.12 && uv venv -p 3.12 ~/p2o
#   uv pip install -p ~/p2o/bin/python paddlepaddle==3.3.1 paddle2onnx==2.1.0 packaging onnx onnx_graphsurgeon onnxruntime pyyaml
#   thiếu libgomp: (cd ~/libs && apt-get download libgomp1 && dpkg -x libgomp1_*.deb root)
#
# Dùng: bash convert.sh <thư mục model Paddle> <thư mục ra>   → inference.onnx, inference.yml, dict.json (character_dict của model)
set -euo pipefail
PY="${P2O_PY:-$HOME/p2o/bin/python}"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:$HOME/libs/root/usr/lib/x86_64-linux-gnu"
M="$1"; O="$2"
mkdir -p "$O"
"$(dirname "$PY")/paddle2onnx" --model_dir "$M" --model_filename inference.json --params_filename inference.pdiparams \
  --save_file "$O/inference.onnx" --opset_version 14 --enable_onnx_checker True 2>&1 | grep -vE "^\s*$|ccache|warnings.warn" | tail -4
cp "$M/inference.yml" "$O/"
"$PY" - "$O" <<'EOF'
import json, sys, yaml, onnx, onnxruntime as ort, numpy as np
o = sys.argv[1]
d = yaml.safe_load(open(o + "/inference.yml", encoding="utf-8"))["PostProcess"]["character_dict"]
json.dump(d, open(o + "/dict.json", "w", encoding="utf-8"), ensure_ascii=False)
m = onnx.load(o + "/inference.onnx"); onnx.checker.check_model(m)
s = ort.InferenceSession(o + "/inference.onnx", providers=["CPUExecutionProvider"])
C = s.run(None, {s.get_inputs()[0].name: np.zeros((1, 3, 48, 320), np.float32)})[0].shape[-1]
print("ONNX opset", [x.version for x in m.opset_import], "| lớp đầu ra", C, "| bộ ký tự", len(d), "+ dấu cách + blank =", len(d) + 2)
if C != len(d) + 2: sys.exit("Model và bộ ký tự không khớp")
EOF
ls -la "$O"
