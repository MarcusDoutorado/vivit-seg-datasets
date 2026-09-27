"""Feature-extractor classes for the MSC standalone pipeline.

Ported from vivit-seg's src/preprocess/feature_extractors/{audio,textual,visual}.py,
adapted to take their handful of configuration constants directly (frame
counts, dims, model name) instead of importing setting.Setting.

Kept out of visual.py on purpose (per the scope agreed for this port):
- The "legacy" ViViT classifier-input extraction mode (extract_legacy_classifier_input)
  and its visual_embedding_cache.py companion -- dropped entirely, only the
  "current" per-shot embedding mode is ported.
- Four strategy names vivit-seg lists in VISUAL_EMBEDDING_STRATEGIES but never
  actually implements (attention_pool, cls_residual, multi_layer,
  spatial_temporal -- calling them raises ValueError in the original code).
  Only the strategies with a real implementation are exposed here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class FeatureExtractor(ABC):
    @abstractmethod
    def extract(self, sample) -> np.ndarray:
        """Returns an embedding as a numpy array."""


# ----------------------------------------------------------------------
# Audio: MFCC / LogMel raw feature -> fixed-length, normalized sequence
# ----------------------------------------------------------------------

class AudioExtractor(FeatureExtractor):
    """Turns a raw (F, T) or (T, F) MFCC/LogMel array (as saved by
    04_extract_audio_features.py's --generate-features step) into a
    normalized, fixed-length (MAX_AUDIO_LEN, F) sequence."""

    def __init__(self, feature_type: str, audio_dim: int, max_audio_len: int = 128):
        self.feature_type = feature_type
        self.audio_dim = audio_dim
        self.max_audio_len = max_audio_len

    def extract(self, feature: np.ndarray) -> np.ndarray:
        if feature.ndim == 1:
            if feature.shape[0] != self.audio_dim:
                raise ValueError(f"Invalid feature shape: {feature.shape}")
            feature = feature[:, None]
        elif feature.ndim != 2:
            raise ValueError(f"Invalid feature ndim: {feature.ndim}")

        # (F, T) -> (T, F)
        if feature.shape[0] == self.audio_dim:
            seq = feature.T
        elif feature.shape[1] == self.audio_dim:
            seq = feature
        else:
            raise ValueError(f"Unrecognized feature shape: {feature.shape}")

        seq = (seq - np.mean(seq, axis=0)) / (np.std(seq, axis=0) + 1e-6)

        if seq.shape[0] > self.max_audio_len:
            seq = seq[: self.max_audio_len]
        elif seq.shape[0] < self.max_audio_len:
            pad = np.zeros((self.max_audio_len - seq.shape[0], seq.shape[1]), dtype=np.float32)
            seq = np.vstack([seq, pad])

        return seq.astype(np.float32)


# ----------------------------------------------------------------------
# Textual: sentence-transformers embedding of a shot's (Whisper) transcript
# ----------------------------------------------------------------------

class TextualExtractor(FeatureExtractor):
    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_dim: int = 384,
        device: str | None = None,
    ):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device=device)
        self.embedding_dim = embedding_dim

    def extract(self, sample) -> np.ndarray:
        if isinstance(sample, (list, tuple)):
            sample = " ".join(sample)
        if sample is None:
            sample = ""

        embedding = self.model.encode(
            sample,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embedding.astype(np.float32)


# ----------------------------------------------------------------------
# Visual: ViViT ("current" per-shot embedding mode only)
# ----------------------------------------------------------------------

# Only the strategies with a real implementation in strategy_extractors below
# are exposed. vivit-seg's feature_extractors/visual.py additionally lists
# attention_pool / cls_residual / multi_layer / spatial_temporal, but calling
# any of those in the original code raises ValueError -- dropped here rather
# than shipped as a confusing dead option.
VISUAL_EMBEDDING_STRATEGIES = (
    "temporal_mean",
    "cls",
    "cls_temporal",
    "temporal_max",
    "temporal_mean_std",
    "temporal_mean_max",
    "temporal_attention",
)
# "temporal_mean_std" is listed in vivit-seg's STRATEGIES tuple too, but like
# the four dropped above it has no entry in strategy_extractors and would
# raise ValueError if selected -- excluded here for the same reason.
VISUAL_EMBEDDING_STRATEGIES = tuple(
    s for s in VISUAL_EMBEDDING_STRATEGIES if s != "temporal_mean_std"
)

DEFAULT_VISUAL_EMBEDDING_STRATEGY = "temporal_mean"


class ViViTExtractor(FeatureExtractor):
    """"Current" per-shot ViViT embedding extractor: one forward pass per
    shot's frames_per_shot key-frames, pooled per `strategy` into a single
    (frames_per_shot, hidden) or (hidden,) embedding."""

    STRATEGIES = VISUAL_EMBEDDING_STRATEGIES

    def __init__(
        self,
        frames_per_shot: int,
        model_name: str = "google/vivit-b-16x2-kinetics400",
        device: str | None = None,
        strategy: str = DEFAULT_VISUAL_EMBEDDING_STRATEGY,
    ):
        import torch
        from transformers import VivitConfig, VivitForVideoClassification, VivitImageProcessor

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.frames_per_shot = frames_per_shot
        self.model_name = model_name

        config = VivitConfig.from_pretrained(model_name)
        config.num_frames = frames_per_shot

        self.model = VivitForVideoClassification.from_pretrained(
            model_name,
            config=config,
            ignore_mismatched_sizes=True,
            attn_implementation="sdpa",
        ).to(self.device)

        if strategy not in self.STRATEGIES:
            raise ValueError(
                f"Unknown or unimplemented visual embedding strategy: {strategy!r}. "
                f"Available: {self.STRATEGIES}"
            )
        self.strategy = strategy

        self.model.eval()
        self.processor = VivitImageProcessor.from_pretrained(model_name)

    def _preprocess(self, frames):
        inputs = self.processor(frames, return_tensors="pt")
        return inputs["pixel_values"].to(self.device)

    def _forward_tokens(self, frames):
        with self.torch.no_grad():
            pixel_values = self._preprocess(frames)

            if pixel_values.shape[1] != self.frames_per_shot:
                raise RuntimeError(
                    f"Expected {self.frames_per_shot} frames, got tensor shape {pixel_values.shape}"
                )

            outputs = self.model(
                pixel_values=pixel_values,
                output_hidden_states=True,
                return_dict=True,
            )

            hidden = outputs.hidden_states[-1]
            cls = hidden[:, 0]
            tokens = hidden[:, 1:]
            hidden_size = tokens.shape[-1]

            temporal_tokens = tokens.reshape(
                tokens.shape[0], self.frames_per_shot, -1, hidden_size
            )

            return {"cls": cls, "temporal_tokens": temporal_tokens}

    def _extract_temporal_mean(self, features):
        temporal_tokens = features["temporal_tokens"]
        embedding = temporal_tokens.mean(dim=2)
        embedding = embedding / (embedding.norm(dim=-1, keepdim=True) + 1e-8)
        return embedding.squeeze(0)

    def _extract_temporal_mean_max(self, features):
        temporal_tokens = features["temporal_tokens"]
        temporal_mean = temporal_tokens.mean(dim=2)
        temporal_max = temporal_tokens.max(dim=2).values
        embedding = self.torch.cat([temporal_mean, temporal_max], dim=-1)
        embedding = embedding / (embedding.norm(dim=-1, keepdim=True) + 1e-8)
        return embedding.squeeze(0)

    def _extract_temporal_max(self, features):
        temporal_tokens = features["temporal_tokens"]
        embedding = temporal_tokens.max(dim=2).values
        embedding = embedding / (embedding.norm(dim=-1, keepdim=True) + 1e-8)
        return embedding.squeeze(0)

    def _extract_temporal_attention(self, features):
        temporal_tokens = features["temporal_tokens"]
        token_scores = temporal_tokens.norm(dim=-1)
        token_weights = self.torch.softmax(token_scores, dim=2).unsqueeze(-1)
        embedding = (temporal_tokens * token_weights).sum(dim=2)
        embedding = embedding / (embedding.norm(dim=-1, keepdim=True) + 1e-8)
        return embedding.squeeze(0)

    def _extract_cls(self, features):
        cls_embedding = features["cls"]
        cls_embedding = cls_embedding / (cls_embedding.norm(dim=-1, keepdim=True) + 1e-8)
        # Keep output shape compatible with temporal_mean: (frames_per_shot, hidden)
        embedding = cls_embedding.unsqueeze(1).repeat(1, self.frames_per_shot, 1)
        return embedding.squeeze(0)

    def _extract_cls_temporal(self, features):
        temporal_mean = self._extract_temporal_mean(features)
        cls_repeated = self._extract_cls(features)
        embedding = 0.5 * (temporal_mean + cls_repeated)
        embedding = embedding / (embedding.norm(dim=-1, keepdim=True) + 1e-8)
        return embedding.squeeze(0)

    def extract(self, frames) -> np.ndarray:
        features = self._forward_tokens(frames)

        strategy_extractors = {
            "temporal_mean": self._extract_temporal_mean,
            "cls": self._extract_cls,
            "temporal_max": self._extract_temporal_max,
            "temporal_mean_max": self._extract_temporal_mean_max,
            "temporal_attention": self._extract_temporal_attention,
            "cls_temporal": self._extract_cls_temporal,
        }
        embedding = strategy_extractors[self.strategy](features)
        return embedding.cpu().numpy()
