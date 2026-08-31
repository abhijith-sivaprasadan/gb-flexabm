"""Auditable capacity-target grid search with training-only table access.

The historical predictor/institutional model is still pending. A caller-supplied
predictor must use TrainingView; Python callbacks are not sandboxed. Passing a
linear sensitivity screen is not enough to issue a scientific parameter lock.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .provenance import canonical_hash, code_state
from .research_metrics import capacity_metrics, sensitivity_screen
from .study import REQUIRED_ROLES, StudyBundle


class TrainingView:
    def __init__(self, bundle: StudyBundle):
        self._bundle = bundle
        self.years = tuple(bundle.protocol.record["splits"]["train"])

    def read(self, role: str, year: int):
        return self._bundle.read(role, year, "train")


def fit_capacity_grid(
    bundle: StudyBundle,
    candidates: list[dict[str, float]],
    seeds: list[int],
    technologies: tuple[str, ...],
    predict: Callable[[dict[str, float], int, TrainingView], np.ndarray],
    output: Path,
) -> dict:
    if bundle.protocol.record["status"] != "frozen":
        raise ValueError("Freeze the study protocol before calibration")
    search = bundle.protocol.record.get("calibration", {})
    if (
        search.get("candidates") != candidates
        or search.get("seeds") != seeds
        or search.get("technologies") != list(technologies)
    ):
        raise ValueError(
            "Search space, common seeds and target categories must be frozen in the protocol"
        )
    if (
        not candidates
        or not candidates[0]
        or not seeds
        or len(seeds) != len(set(seeds))
        or any(type(s) is not int or s < 0 for s in seeds)
    ):
        raise ValueError("Nonempty candidates and distinct nonnegative integer seeds required")
    names = sorted(candidates[0])
    if any(sorted(c) != names or not np.isfinite(list(c.values())).all() for c in candidates):
        raise ValueError("Candidates must contain the same finite parameters")
    if not technologies or len(set(technologies)) != len(technologies):
        raise ValueError("Unique target technologies required")
    if not bundle.readiness()["metadata_complete"]:
        raise ValueError("Historical calibration requires every input role for every training year")
    view = TrainingView(bundle)
    targets = []
    for year in view.years:
        tables = {role: view.read(role, year) for role in REQUIRED_ROLES}
        fleet = tables["fleet"]
        if not {"technology", "capacity_mw"}.issubset(fleet):
            raise ValueError("Fleet targets require technology and capacity_mw")
        if set(fleet.technology) != set(technologies) or (fleet.capacity_mw < 0).any():
            raise ValueError("Fleet target categories must exactly match the frozen categories")
        targets.append(
            fleet.groupby("technology").capacity_mw.sum().reindex(technologies).to_numpy()
        )
    observed = np.asarray(targets, dtype=float)
    capacity_metrics(observed, observed)
    output.mkdir(parents=True, exist_ok=False)
    trial_path = output / "trials.jsonl"
    successes: list[dict[str, Any]] = []
    responses = []
    # Flush every trial, including failed seeds. Interrupted/failed searches remain visible.
    with trial_path.open("x", encoding="utf-8") as stream:
        for index, parameters in enumerate(candidates):
            predictions = []
            for seed in seeds:
                row = {"candidate": index, "parameters": parameters, "seed": seed}
                try:
                    prediction = np.asarray(predict(parameters.copy(), seed, view), dtype=float)
                    metrics = capacity_metrics(prediction, observed)
                    predictions.append(prediction)
                    row.update(status="ok", metrics=metrics, prediction_mw=prediction.tolist())
                except Exception as exc:
                    # Do not leak arbitrary callback messages/paths/credentials into public logs.
                    row.update(status="failed", error_type=type(exc).__name__)
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                stream.flush()
            if len(predictions) == len(seeds):
                mean = np.mean(predictions, axis=0)
                successes.append(
                    {
                        "candidate": index,
                        "parameters": parameters,
                        "metrics": capacity_metrics(mean, observed),
                    }
                )
                responses.append(mean.ravel())
    best = min(successes, key=lambda r: r["metrics"]["wmape"]) if successes else None
    screen = (
        sensitivity_screen(
            np.array([[s["parameters"][name] for name in names] for s in successes]),
            np.array(responses),
        )
        if len(successes) >= 2
        else {"passed_linear_screen": False, "reason": "Fewer than two successful candidates"}
    )
    report = {
        "schema_version": 1,
        "protocol_sha256": bundle.protocol.identity,
        "bundle_sha256": bundle.identity,
        "code_sha256": canonical_hash(code_state()),
        "training_years": list(view.years),
        "seeds": seeds,
        "trials_sha256": __import__("hashlib").sha256(trial_path.read_bytes()).hexdigest(),
        "successful_candidates": len(successes),
        "best_candidate": best,
        "sensitivity": screen,
        "parameter_lock_issued": False,
        "note": "Candidate search only. Historical predictor validation, identifiability assessment and explicit parameter lock are still required.",
    }
    (output / "search.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report
