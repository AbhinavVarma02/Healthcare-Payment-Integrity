"""Train-only lookup, sparse feature encoding and calibrated scorecards."""

from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from .cohorts import FEATURES

MIN_GROUP = 20
EPSILON = 1e-6


def feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Project an allowlist and validate structural invariants."""
    features = frame.loc[:, list(FEATURES)].copy()
    if (features.isna().any().any() or not features["part"].isin(["Part B", "DME"]).all()
            or (features["visible_lines"] < 1).any() or (features["provider_types"] < 1).any()
            or (features["provider_types"] > features["visible_lines"]).any()):
        raise ValueError("Invalid claim features.")
    return features


def line_band(lines):
    return np.digitize(lines, [2, 4, 7])


def concentration(groups, rate: float) -> float:
    supported = [(total, errors / total) for total, errors in groups if total >= MIN_GROUP]
    if len(supported) < 2:
        return 20.0
    totals, observed = np.asarray(supported).T
    sampling = np.mean(rate * (1 - rate) / totals)
    between = np.var(observed, ddof=1) - sampling
    if between <= 0:
        return 20.0
    return float(np.clip(rate * (1 - rate) / between - 1, 2, 100))


@dataclass
class Lookup:
    rate: float
    strength: float
    parts: dict
    providers: dict
    bands: dict
    historical: dict
    kind: str = "lookup"

    def predict(self, frame):
        if self.kind == "global":
            return np.full(len(frame), self.rate)
        result = np.empty(len(frame))
        for index, (part, provider, band) in enumerate(zip(
            frame["part"], frame["provider_type"], line_band(frame["visible_lines"]), strict=True
        )):
            part_rate = self.parts.get(part, self.rate)
            key = (part, provider)
            if self.kind == "historical":
                result[index] = self.historical.get(key, part_rate)
            else:
                provider_rate = self.providers.get(key, part_rate)
                result[index] = self.bands.get((*key, int(band)), provider_rate)
        return result


def fit_lookup(frame, labels, kind="lookup") -> Lookup:
    sample = frame.loc[:, ["part", "provider_type"]].assign(
        band=line_band(frame["visible_lines"]), target=np.asarray(labels))
    rate = (sample["target"].sum() + 1) / (len(sample) + 2)
    provider_counts = sample.groupby(["part", "provider_type"])["target"].agg(["size", "sum"])
    strength = concentration(provider_counts.itertuples(index=False, name=None), rate)
    parts, providers, bands, historical = {}, {}, {}, {}
    for part, group in sample.groupby("part")["target"]:
        parts[part] = float((group.sum() + strength * rate) / (len(group) + strength))
    for key, (total, errors) in zip(provider_counts.index,
                                    provider_counts.itertuples(index=False, name=None), strict=True):
        historical[key] = float(errors / total)
        if total >= MIN_GROUP:
            providers[key] = float((errors + strength * parts[key[0]]) / (total + strength))
    for key, group in sample.groupby(["part", "provider_type", "band"])["target"]:
        if len(group) >= MIN_GROUP:
            parent = providers.get(key[:2], parts[key[0]])
            bands[key] = float((group.sum() + strength * parent) / (len(group) + strength))
    return Lookup(float(rate), strength, parts, providers, bands, historical, kind)


@dataclass
class Encoder:
    providers: tuple[str, ...]
    counts: bool = True

    @classmethod
    def fit(cls, frame, counts=True):
        observed = Counter(frame["provider_type"])
        return cls(tuple(sorted(k for k, n in observed.items() if n >= MIN_GROUP)), counts)

    @property
    def feature_names(self):
        features = ["part: DME", "part: Part B", "provider category: other"]
        features.extend(f"provider category: {name}" for name in self.providers)
        if self.counts:
            features.extend(["log visible lines", "visible provider categories"])
        return features

    def transform(self, frame):
        n = len(frame)
        mapping = {provider: i for i, provider in enumerate(self.providers, 3)}
        part_index = np.where(frame["part"].eq("DME"), 0, 1)
        provider_index = np.fromiter((mapping.get(k, 2) for k in frame["provider_type"]),
                                     dtype=np.int32, count=n)
        indices = np.concatenate([part_index, provider_index])
        rows = np.tile(np.arange(n), 2)
        matrix = sparse.csr_matrix((np.ones(2*n), (rows, indices)), shape=(n, len(mapping) + 3))
        if not self.counts:
            return matrix
        counts = np.column_stack([np.log1p(frame["visible_lines"]), frame["provider_types"]])
        return sparse.hstack([matrix, sparse.csr_matrix(counts)], format="csr")


@dataclass
class ML:
    encoder: Encoder
    kind: str
    coefficients: np.ndarray | None = None
    intercept: float = 0.0
    booster: XGBClassifier | None = None

    def predict(self, frame):
        matrix = self.encoder.transform(frame)
        if self.booster is not None:
            return self.booster.predict_proba(matrix)[:, 1]
        if self.coefficients is None:
            raise ValueError("Logistic coefficient state unavailable.")
        return expit(matrix @ self.coefficients + self.intercept)


def fit_ml(frame, labels, kind: str, parameter, seed: int, counts=True) -> ML:
    encoder = Encoder.fit(frame, counts)
    design = encoder.transform(frame)
    if kind == "logistic":
        model = LogisticRegression(C=parameter, max_iter=500, solver="lbfgs").fit(design, labels)
        return ML(encoder, kind, model.coef_[0], float(model.intercept_[0]))
    booster = XGBClassifier(n_estimators=120, max_depth=parameter, learning_rate=0.08,
                            min_child_weight=10, n_jobs=1, random_state=seed,
                            tree_method="hist", device="cpu")
    booster.fit(design, labels)
    return ML(encoder, kind, booster=booster)


@dataclass(frozen=True)
class Sigmoid:
    intercept: float = 0.0
    slope: float = 1.0

    def predict(self, risk):
        return expit(self.intercept + self.slope * logit(np.clip(risk, EPSILON, 1 - EPSILON)))


def calibration_coefficients(risk, outcomes):
    logits = logit(np.clip(risk, EPSILON, 1 - EPSILON))
    if np.unique(outcomes).size < 2 or np.ptp(logits) <= 1e-12:
        return None
    model = LogisticRegression(C=1e4, max_iter=300).fit(logits.reshape(-1, 1), outcomes)
    return Sigmoid(float(model.intercept_[0]), float(model.coef_[0, 0]))


def calibrate(risk, outcomes) -> Sigmoid:
    fit = calibration_coefficients(risk, outcomes)
    return fit if fit is not None and fit.slope > 0 else Sigmoid()
