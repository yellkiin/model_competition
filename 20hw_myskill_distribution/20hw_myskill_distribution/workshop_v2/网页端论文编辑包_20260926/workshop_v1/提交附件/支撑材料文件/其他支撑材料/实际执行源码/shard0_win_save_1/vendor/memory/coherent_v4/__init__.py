"""Composable structure-aware memory candidate source."""
from .candidates import (
    VERSION,
    Options,
    assess,
    candidate_advice,
    propose,
    propose_with_options,
    retain_best,
)

__all__ = [
    "VERSION",
    "Options",
    "assess",
    "candidate_advice",
    "propose",
    "propose_with_options",
    "retain_best",
]
