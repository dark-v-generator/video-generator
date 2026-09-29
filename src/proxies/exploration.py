"""The exploration grade's answer, checked the same way whichever model gave it.

A grade that names an experiment the model was not given, or that is off the
scale, raises: recorded, it would count a video for a question nobody asked.
"""

from typing import Sequence

from ..entities.tuning import Experiment


def normalize_exploration(data: dict, experiments: Sequence[Experiment]) -> dict:
    """``{"experiment": id or None, "fit": 0-100, "reason": text}``; no
    experiment is a fit of 0."""
    reason = str(data.get("reason") or "")
    experiment = data.get("experiment")
    if experiment in (None, "", "null"):
        return {"experiment": None, "fit": 0.0, "reason": reason}
    given = [e.id for e in experiments]
    if experiment not in given:
        raise ValueError(
            f"exploration grade names experiment {experiment!r},"
            f" which is not one of {', '.join(given) or 'none'}"
        )
    fit = data.get("fit")
    if (
        isinstance(fit, bool)
        or not isinstance(fit, (int, float))
        or not 0 <= fit <= 100
    ):
        raise ValueError(f"exploration grade fit {fit!r} is not a number from 0 to 100")
    return {"experiment": experiment, "fit": float(fit), "reason": reason}
