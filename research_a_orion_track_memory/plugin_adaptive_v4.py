"""Drop-in adapter for the shared three-track candidate interface.

The default callable is propose. make_proposer lets a combined solver disable
families it already supplies elsewhere without editing public ORION modules.
"""
from __future__ import annotations

from dataclasses import replace
from .coherent_v4 import (
    VERSION,
    Options,
    assess,
    candidate_advice,
    propose as _default_propose,
    propose_with_options,
    retain_best,
)


def propose(g, n, cfg, q, incumbent=None, feedback=None, deadline=None):
    yield from _default_propose(g, n, cfg, q, incumbent, feedback, deadline)


def make_proposer(options: Options | None = None, **overrides):
    """Return a COMMON-compatible proposer with immutable local options."""
    base = options or Options()
    configured = replace(base, **overrides) if overrides else base

    def configured_propose(g, n, cfg, q, incumbent=None, feedback=None, deadline=None):
        yield from propose_with_options(
            g, n, cfg, q, incumbent, feedback, deadline, configured
        )

    configured_propose.options = configured
    configured_propose.version = VERSION
    return configured_propose


__all__ = [
    "VERSION",
    "Options",
    "assess",
    "candidate_advice",
    "retain_best",
    "propose",
    "make_proposer",
]
