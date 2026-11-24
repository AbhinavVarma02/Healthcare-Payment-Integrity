"""Serialize typed scorecards without pickle, with version and digest checks."""

import hashlib
import json
from math import isfinite
from pathlib import Path
from typing import Any

import numpy as np
from xgboost import XGBClassifier

from .models import ML, Encoder, Lookup, Sigmoid
from .storage import atomic_bytes, sha256, write_json


def save_scorecard(folder: Path, model: Lookup | ML, curve: Sigmoid):
    value: dict[str, Any] = {"calibration": vars(curve), "kind": model.kind}
    if isinstance(model, Lookup):
        value.update(
            rate=model.rate, strength=model.strength, parts=model.parts,
            providers=[[list(key), risk] for key, risk in model.providers.items()],
            bands=[[list(key), risk] for key, risk in model.bands.items()],
            historical=[[list(key), risk] for key, risk in model.historical.items()],
        )
    else:
        value.update(encoder=vars(model.encoder), intercept=model.intercept)
        if model.booster is None:
            if model.coefficients is None:
                raise ValueError("Missing logistic coefficients.")
            value["coefficients"] = model.coefficients.tolist()
        else:
            destination = folder / "booster.json"
            atomic_bytes(destination, bytes(model.booster.get_booster().save_raw(raw_format="json")))
            value["booster_sha256"] = sha256(destination)
    write_json(folder / "scorecard.json", value)


def load_scorecard(folder: Path, expected_hash: str):
    source = (folder / "scorecard.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != expected_hash:
        raise ValueError("Scorecard integrity verification failed.")
    value = json.loads(source)
    kind = value["kind"]
    model: Lookup | ML
    if kind in {"lookup", "global", "historical"}:
        model = Lookup(
            value["rate"], value["strength"], value["parts"],
            {tuple(key): risk for key, risk in value["providers"]},
            {tuple(key): risk for key, risk in value["bands"]},
            {tuple(key): risk for key, risk in value["historical"]}, kind,
        )
        probabilities = [model.rate, *model.parts.values(), *model.providers.values(),
                         *model.bands.values(), *model.historical.values()]
        if any(not 0 <= risk <= 1 for risk in probabilities) or not 0 < model.strength < float("inf"):
            raise ValueError("Lookup scorecard has invalid fitted parameters.")
    elif kind in {"logistic", "xgb"}:
        encoder = Encoder(tuple(value["encoder"]["providers"]), value["encoder"]["counts"])
        model = ML(encoder, kind, intercept=value["intercept"])
        if kind == "xgb":
            source = (folder / "booster.json").read_bytes()
            if hashlib.sha256(source).hexdigest() != value["booster_sha256"]:
                raise ValueError("Tree artifact integrity verification failed.")
            model.booster = XGBClassifier(n_jobs=1)
            model.booster.load_model(bytearray(source))
        else:
            model.coefficients = np.asarray(value["coefficients"], dtype=float)
            if model.coefficients.shape != (len(encoder.feature_names),):
                raise ValueError("Unexpected logistic model shape.")
            if not np.isfinite(model.coefficients).all() or not isfinite(model.intercept):
                raise ValueError("Logistic scorecard has nonfinite fitted parameters.")
    else:
        raise ValueError("Unrecognized model kind.")
    curve = Sigmoid(**value["calibration"])
    if not isfinite(curve.intercept) or not isfinite(curve.slope) or curve.slope <= 0:
        raise ValueError("Calibrator has invalid fitted parameters.")
    return model, curve
