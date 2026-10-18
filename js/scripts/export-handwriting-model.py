"""Build-time conversion only. Runtime inference has no Python/ONNX dependency."""
from pathlib import Path
import base64, gzip, hashlib, json, sys
import numpy as np
import onnx
from onnx import numpy_helper
import onnxruntime as ort

ROOT = Path(sys.argv[1]).resolve()
model_path = ROOT / 'mnist-12.onnx'
assert hashlib.sha256(model_path.read_bytes()).hexdigest() == '5c688690f8bacf667d4c2074af5ad0646ca328d7ab03eccf944a65b320171bdd'
dataset = ROOT / 'mnist.npz'
assert hashlib.sha256(dataset.read_bytes()).hexdigest() == '731c5ac602752760c8e48fbffcf8c3b850d9dc2a2aedcf2cc48468fc17b673d1'
graph = onnx.load(model_path)
arrays = {t.name: numpy_helper.to_array(t) for t in graph.graph.initializer}
weights = {}
for key in ['Parameter5', 'Parameter6', 'Parameter87', 'Parameter88', 'Parameter193', 'Parameter194']:
    a = arrays[key].astype('<f4')
    weights[key] = {'shape': list(a.shape), 'data': base64.b64encode(a.tobytes()).decode()}
out = {'id': 'hak-mnist-cnn-onnx12-v1', 'upstreamSha256': hashlib.sha256(model_path.read_bytes()).hexdigest(), 'inputShape': [1, 1, 28, 28], 'classes': list('0123456789'), 'weights': weights}
(ROOT / 'mnist-cnn.json').write_text(json.dumps(out, separators=(',', ':')) + '\n', encoding='utf-8')
with np.load(dataset, allow_pickle=False) as data:
    images, labels = data['x_test'], data['y_test']
assert images.shape == (10000, 28, 28)
options = ort.SessionOptions(); options.intra_op_num_threads = 1
session = ort.InferenceSession(str(model_path), options, providers=['CPUExecutionProvider'])
samples = []
indices = [int(i) for label in range(10) for i in np.flatnonzero(labels == label)[:10]]
for index in indices:
    image = images[index]
    logits = session.run(None, {session.get_inputs()[0].name: image.astype(np.float32).reshape(1, 1, 28, 28) / 255})[0].reshape(-1)
    samples.append({'index': index, 'label': int(labels[index]), 'pixels': base64.b64encode(image.tobytes()).decode(), 'logits': [float(v) for v in logits]})
fixture = {'dataset': 'MNIST official test split', 'sourceSha256': hashlib.sha256(dataset.read_bytes()).hexdigest(), 'license': 'CC-BY-SA-3.0', 'samples': samples}
with gzip.GzipFile(filename=str(ROOT / 'mnist-test-100.json.gz'), mode='wb', mtime=0) as stream:
    stream.write(json.dumps(fixture, separators=(',', ':')).encode())
with (ROOT / 'mnist-test.bin').open('wb') as stream:
    stream.write(len(labels).to_bytes(4, 'little'))
    for image, label in zip(images, labels): stream.write(bytes([int(label)]) + image.tobytes())
print('Exported fixed ONNX weights, 100 reference vectors, and independent 10000-image test data.')
