"""
backend/cnn_module.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

PyTorch-based image feature extraction and classification pipeline. Uses a
pretrained ResNet18 backbone (ImageNet weights) for transfer-learning-grade
feature vectors and top-K classification, run on CPU or CUDA if available.
Designed to be invoked from a Celery worker so inference never blocks the
HTTP request path.
"""
from __future__ import annotations

import io
import logging
import threading
from dataclasses import dataclass, field

import torch
from PIL import Image
from torchvision import models, transforms

logger = logging.getLogger("omniscale.cnn")

_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_model_lock = threading.Lock()
_model: torch.nn.Module | None = None
_labels: list[str] | None = None

_PREPROCESS = transforms.Compose(
    [
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)


def _load_model() -> torch.nn.Module:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                logger.info("Loading ResNet18 backbone on device=%s", _device)
                weights = models.ResNet18_Weights.IMAGENET1K_V1
                net = models.resnet18(weights=weights)
                net.eval()
                net.to(_device)
                _model = net
                global _labels
                _labels = weights.meta["categories"]
    return _model


@dataclass
class CNNPrediction:
    label: str
    confidence: float


@dataclass
class CNNResult:
    predictions: list[CNNPrediction] = field(default_factory=list)
    feature_vector_dim: int = 0
    device: str = str(_device)


def _feature_extractor(model: torch.nn.Module) -> torch.nn.Module:
    """Strips the final FC layer to expose a 512-d spatial feature vector."""
    return torch.nn.Sequential(*list(model.children())[:-1])


@torch.inference_mode()
def run_inference(image_bytes: bytes, top_k: int = 5) -> CNNResult:
    """
    Full spatial processing pipeline: decode -> preprocess -> forward pass ->
    top-K classification + 512-d pooled feature vector for downstream
    similarity search / agent reasoning.
    """
    model = _load_model()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = _PREPROCESS(image).unsqueeze(0).to(_device)

    logits = model(tensor)
    probs = torch.nn.functional.softmax(logits, dim=1)[0]
    top_probs, top_idx = torch.topk(probs, k=min(top_k, probs.shape[0]))

    labels = _labels or [str(i) for i in range(probs.shape[0])]
    predictions = [
        CNNPrediction(label=labels[idx.item()], confidence=round(prob.item(), 4))
        for prob, idx in zip(top_probs, top_idx)
    ]

    extractor = _feature_extractor(model)
    feat = extractor(tensor).flatten(1)  # [1, 512]

    return CNNResult(
        predictions=predictions,
        feature_vector_dim=feat.shape[1],
        device=str(_device),
    )
