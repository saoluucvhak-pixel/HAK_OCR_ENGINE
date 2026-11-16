"""Optional local TrOCR for handwriting *candidates*, never auto-approved.
Do not claim Vietnamese handwriting support for an English TrOCR checkpoint.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image
from .advanced_engines import prevent_remote_model_resolution,required_model_dir,OfflineModelError


class HandwritingLocal:
    def __init__(self,base:Path|None=None,processor_factory=None,model_factory=None):
        prevent_remote_model_resolution()
        path=required_model_dir('handwriting',base)
        if not (path/'config.json').is_file():
            raise OfflineModelError('Model chữ viết tay cần config.json và trọng số đầy đủ tại '+str(path))
        if processor_factory is None or model_factory is None:
            try:
                from transformers import AutoProcessor,VisionEncoderDecoderModel
                import torch
            except ImportError as e:raise OfflineModelError('Chưa cài transformers/torch offline') from e
            processor_factory=processor_factory or AutoProcessor
            model_factory=model_factory or VisionEncoderDecoderModel
        self.processor=processor_factory.from_pretrained(str(path),local_files_only=True)
        self.model=model_factory.from_pretrained(str(path),local_files_only=True)
        self.model.eval()

    def recognize(self, crop: Image.Image) -> dict:
        if min(crop.size)<12:raise ValueError('Vùng chữ viết tay quá nhỏ')
        import torch
        inputs=self.processor(images=crop.convert('RGB'),return_tensors='pt').pixel_values
        with torch.inference_mode():
            ids=self.model.generate(inputs,max_new_tokens=96,num_beams=2)
        text=self.processor.batch_decode(ids,skip_special_tokens=True)[0].strip()
        return {'text':text,'engine':'trocr-local','status':'CANDIDATE','verified':False,
                'confidence':None,'warning':'Mô hình chỉ tạo ứng viên. Phải kiểm tra dấu tiếng Việt, tên và số liệu.'}
