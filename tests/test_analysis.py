import unittest

import pandas as pd

from analysis import (
    association_summary,
    parse_csv_bytes,
    prepare_analysis_data,
    summarize_numeric,
)


class CsvAndAnalysisTests(unittest.TestCase):
    def test_valid_csv_produces_temperature_observations(self):
        raw = parse_csv_bytes(b"lst\n29.5\n31.0\n")
        frame, derived, quality = prepare_analysis_data(raw, {"temperature": "lst"})
        self.assertEqual(quality["temperature_usable"], 2)
        self.assertEqual(frame[derived["temperature"]].tolist(), [29.5, 31.0])

    def test_empty_csv_is_reported(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            parse_csv_bytes(b"")
        empty_dataset = parse_csv_bytes(b"lst,date\n")
        self.assertTrue(empty_dataset.empty)
        summary = summarize_numeric(pd.Series(dtype="float64"))
        self.assertEqual(summary["count"], 0)
        self.assertIsNone(summary["mean"])

    def test_missing_selected_column_is_reported(self):
        raw = pd.DataFrame({"other": [1]})
        with self.assertRaisesRegex(ValueError, "not present"):
            prepare_analysis_data(raw, {"temperature": "lst"})

    def test_missing_and_non_numeric_temperatures_are_counted(self):
        raw = pd.DataFrame({"lst": [30, None, "cloud", float("inf")]})
        frame, derived, quality = prepare_analysis_data(raw, {"temperature": "lst"})
        self.assertEqual(quality["temperature_missing"], 1)
        self.assertEqual(quality["temperature_invalid"], 2)
        self.assertEqual(quality["temperature_usable"], 1)
        self.assertEqual(int(frame[derived["temperature"]].notna().sum()), 1)

    def test_invalid_date_values_are_counted(self):
        raw = pd.DataFrame({"lst": [30, 31], "when": ["2025-01-02", "not-a-date"]})
        _, _, quality = prepare_analysis_data(
            raw, {"temperature": "lst", "date": "when"}
        )
        self.assertEqual(quality["date_invalid"], 1)
        self.assertEqual(quality["date_usable"], 1)

    def test_day_first_dates_can_be_parsed_explicitly(self):
        raw = pd.DataFrame({"when": ["02/01/2025"]})
        frame, derived, _ = prepare_analysis_data(
            raw, {"date": "when", "date_dayfirst": True}
        )
        self.assertEqual(frame[derived["date"]].iloc[0].date().isoformat(), "2025-01-02")
        self.assertEqual(raw["when"].iloc[0], "02/01/2025")

    def test_invalid_geographic_coordinates_are_counted(self):
        raw = pd.DataFrame(
            {
                "lat": [19.0, 91.0, "bad", None],
                "lon": [72.8, 72.8, 72.8, 72.8],
            }
        )
        frame, derived, quality = prepare_analysis_data(
            raw, {"latitude": "lat", "longitude": "lon"}
        )
        self.assertEqual(quality["coordinates_usable"], 1)
        self.assertEqual(quality["coordinates_invalid"], 3)
        self.assertEqual(frame[derived["latitude"]].notna().sum(), 1)

    def test_missing_vegetation_column_does_not_block_temperature_analysis(self):
        raw = pd.DataFrame({"lst": [28, 29]})
        frame, derived, _ = prepare_analysis_data(raw, {"temperature": "lst"})
        self.assertIn("temperature", derived)
        self.assertNotIn("vegetation", derived)
        self.assertEqual(len(frame), 2)

    def test_statistics_use_valid_observations(self):
        summary = summarize_numeric(pd.Series([2, 4, 6, None, "bad"]))
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["mean"], 4)
        self.assertEqual(summary["median"], 4)
        self.assertEqual(summary["min"], 2)
        self.assertEqual(summary["max"], 6)

    def test_ndvi_outside_documented_range_is_invalid_not_rescaled(self):
        raw = pd.DataFrame({"lst": [30, 31], "ndvi": [0.4, 4000]})
        _, _, quality = prepare_analysis_data(
            raw,
            {"temperature": "lst", "vegetation": "ndvi", "vegetation_type": "NDVI"},
        )
        self.assertEqual(quality["vegetation_usable"], 1)
        self.assertEqual(quality["vegetation_invalid"], 1)

    def test_correlation_requires_three_varying_pairs(self):
        result = association_summary(
            pd.Series([0.1, 0.3, 0.5, None]),
            pd.Series([20, 25, 30, 40]),
            method="pearson",
        )
        self.assertEqual(result["n"], 3)
        self.assertEqual(result["missing_pairs"], 1)
        self.assertAlmostEqual(result["correlation"], 1.0)


if __name__ == "__main__":
    unittest.main()
