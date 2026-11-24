"""Train and score a miniature fictional cohort without reading CMS files."""

import csv
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from payment_integrity.cohorts import HEADER, project_csv  # noqa: E402
from payment_integrity.model_io import load_scorecard, save_scorecard  # noqa: E402
from payment_integrity.models import calibrate, fit_lookup  # noqa: E402
from payment_integrity.sampling import estimate, select  # noqa: E402
from payment_integrity.storage import sha256  # noqa: E402


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        snapshots = []
        for year in (2020, 2021, 2022):
            source = root / f"{year}.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(HEADER)
                for i in range(80):
                    part = "1. Part B" if i < 40 else "2. DME MAC"
                    provider = "Synthetic clinic" if i < 40 else "Synthetic equipment"
                    disagree = i % (4 if i < 40 else 2) == 0
                    writer.writerow((f"fixture-{i}", part, "", "", provider, "",
                                     "Disagree" if disagree else "Agree", ""))
            frame, outcomes, _, _ = project_csv(source, year, True)
            if outcomes is None:
                raise ValueError("Fictional outcomes were not available.")
            snapshots.append((frame, outcomes["disagreement"].to_numpy(dtype=int)))
        (train, y_train), (cal, y_cal), (test, y_test) = snapshots
        model = fit_lookup(train, y_train)
        curve = calibrate(model.predict(cal), y_cal)
        directory_path = root / "scorecard"
        save_scorecard(directory_path, model, curve)
        loaded, calibrated = load_scorecard(directory_path, sha256(directory_path / "scorecard.json"))
        p = calibrated.predict(loaded.predict(test))
        sample = select(p, test["claim_key"].to_numpy(), 20, "hybrid-10", np.random.default_rng(24))
        value = estimate(y_test[sample.indices], sample.strata)
        if len(sample.indices) != 20 or value["ht"] is None:
            raise ValueError("Fictional smoke sample did not meet configured budget or positivity.")
        print(f"Synthetic fixture only: 3 partitions, {len(y_test)} test groups, "
              f"{len(sample.indices)} reviews and a design-aware estimate.")


if __name__ == "__main__":
    main()
