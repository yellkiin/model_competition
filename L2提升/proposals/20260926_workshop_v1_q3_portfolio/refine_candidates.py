"""Finer-band Q3 candidates, separate from the frozen first-stage generator.

These four additional scales are proposed by a pilot, not assumed improvements.
The official evaluator must establish execution validity and makespan.
"""

from __future__ import annotations

from band_candidates import (
    _settings,
    _signature,
    _views,
    _weighted_plan,
    original_band_plan,
)


def generate_candidates(graph, num_cores, baseline_plan, cache_config=None):
    """Yield distinct original/pipe-byte band candidates at 32 and 64 bands.

    The baseline and duplicates within this four-candidate family are skipped.
    Plan builders call the official basic plan validator; dynamic execution
    validation remains the responsibility of the official Q3 evaluator.
    """
    if not 1 <= num_cores <= 5:
        raise ValueError("num_cores must be in 1..5")
    if num_cores == 1:
        return
    seen = {_signature(baseline_plan)} if baseline_plan else set()
    for bands in (32, 64):
        plan, metadata = original_band_plan(graph, num_cores, target_bands=bands)
        signature = _signature(plan)
        if signature not in seen:
            seen.add(signature)
            metadata = dict(metadata, candidate_family="refined_original_band_scale")
            yield f"bands{bands}_scale", plan, metadata
    settings = _settings(cache_config)
    views = _views(graph)
    for bands in (32, 64):
        plan, metadata = _weighted_plan(graph, num_cores, bands, 0.25, settings, views)
        signature = _signature(plan)
        if signature not in seen:
            seen.add(signature)
            metadata = dict(metadata, candidate_family="refined_pipe_byte_bands")
            yield f"bands{bands}_pipebytes_w25", plan, metadata
