"""Serialize typed scorecards without pickle, with version and digest checks."""

from pathlib import Path
from typing import Any

import numpy as np
from xgboost import XGBClassifier

from .models import ML, Encoder, Lookup, Sigmoid
from .storage import atomic_bytes, read_json, sha256, write_json


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
    source = folder / "scorecard.json"
    if sha256(source) != expected_hash:
        raise ValueError("Scorecard integrity verification failed.")
    value = read_json(source)
    kind = value["kind"]
    model: Lookup | ML
    if kind in {"lookup", "global", "historical"}:
        model = Lookup(
            value["rate"], value["strength"], value["parts"],
            {tuple(key): risk for key, risk in value["providers"]},
            {tuple(key): risk for key, risk in value["bands"]},
            {tuple(key): risk for key, risk in value["historical"]}, kind,
        )
    elif kind in {"logistic", "xgb"}:
        encoder = Encoder(tuple(value["encoder"]["providers"]), value["encoder"]["counts"])
        model = ML(encoder, kind, intercept=value["intercept"])
        if kind == "xgb":
            source = folder / "booster.json"
            if sha256(source) != value["booster_sha256"]:
                raise ValueError("Tree artifact integrity verification failed.")
            model.booster = XGBClassifier(n_jobs=1)
            model.booster.load_model(source)
        else:
            model.coefficients = np.asarray(value["coefficients"], dtype=float)
            if model.coefficients.shape != (len(encoder.feature_names),):
                raise ValueError("Unexpected logistic model shape.")
    else:
        raise ValueError("Unrecognized model kind.")
    curve = Sigmoid(**value["calibration"])
    return model, curve
