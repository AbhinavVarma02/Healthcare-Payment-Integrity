import csv

import pandas as pd
import pytest

from payment_integrity.cohorts import HEADER, development_outcomes, project_csv, read_parquet, write_parquet


def test_repeats_mixed_decisions_and_unknown_do_not_modify_features(tmp_path):
    path = tmp_path / "source.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADER)
        writer.writerows([
            ("a", "1. Part B", "", "fictional", "Lab", "", "Agree", ""),
            ("a", "1. Part B", "", "fictional", "Lab", "", "Agree", ""),
            ("a", "1. Part B", "", "other", "Lab", "", "Disagree", ""),
            ("b", "2. DME MAC", "", "fictional", "", "", "", ""),
            ("c", "2. DME MAC", "", "fictional", "Supply", "", "Agree", ""),
            ("c", "1. Part B", "", "fictional", "Supply", "", "Agree", ""),
            ("", "1. Part B", "", "fictional", "Supply", "", "Agree", ""),
        ])
    features, outcomes, counts, quarantine = project_csv(path, 2023, True)
    sealed, hidden, structural_counts, _ = project_csv(path, 2024, False)
    assert list(features["visible_lines"]) == list(sealed["visible_lines"]) == [3, 1]
    assert hidden is None and "disagreement_groups" not in structural_counts
    assert outcomes["disagreement"].iloc[0] == 1
    assert outcomes["disagreement"].isna().sum() == 1
    assert counts["quarantined_groups"] == 1
    assert len(quarantine) == 1 and counts["rows"] == 7
    assert not {"disagreement", "procedure", "error_code"} & set(features)


def test_holdout_blocked_by_development_reader(tmp_path):
    with pytest.raises(ValueError, match="development outcomes only"):
        development_outcomes(tmp_path, 2024)


def test_parquet_schema_does_not_infer_directory_columns(tmp_path):
    path = tmp_path / "ry=2025" / "features.parquet"
    write_parquet(path, pd.DataFrame({"visible_lines": [2]}))
    assert list(read_parquet(path).columns) == ["visible_lines"]
