# src/LaneKeeping/lane_config.py
"""
Lane Assist configuration loader.

The provided LaneDetection/LaneKeeping code expects a config.ini with multiple sections.
In BFMC Brain, we want the lane module to be plug-and-play:
- If no config file exists, we use sane defaults so the code runs.
- If a config is provided, it can override defaults.

Override order (last wins):
1) Defaults (in this file)
2) File path from env var BFMC_LANE_CONFIG (if set and exists)
3) ./config.ini from current working directory (if exists)
4) src/LaneKeeping/config.ini (if exists)
"""

from __future__ import annotations

import configparser
import os
from typing import Optional, Sequence


DEFAULTS = {
    "PARAMS": {"max_lk_steer": "25"},
    "LANE_DETECT": {
        "custom_find_peaks": "False",
        "slices": "15",
        "bottom_offset": "0",
        "print_lanes": "False",
        "print_peaks": "False",
        "print_lane_certainty": "False",
        "print_if_dashed": "False",
        "print_stop_line": "False",
        "optimal_peak_perc": "0.55",
        "min_lane_dist_perc": "0.20",
        "max_lane_dist_perc": "0.90",
        "allowed_certainty_perc_dif": "0.35",
        "certainty_perc_from_peaks": "0.60",
        "min_peaks_for_lane": "4",
        "extreme_coef_second_deg": "0.003",
        "extreme_coef_first_deg": "3.0",
        "min_single_lane_certainty": "20",
        "min_dual_lane_certainty": "30",
        "square_pulses_min_height": "120",
        "square_pulses_pix_dif": "4",
        "square_pulses_min_height_dif": "25",
        "square_pulses_allowed_peaks_width_error": "12",
        "max_allowed_width_perc": "0.15",
        "weight_for_width_distance": "0.4",
        "weight_for_expected_value_distance": "0.6",
        "stop_line_min_consecutive": "2",
        "stop_line_max_allowed_slope": "0.25",
        "bottom_perc_405": "0.62",
        "peaks_min_width_405": "2",
        "peaks_max_width_405": "40",
        "bottom_perc_455": "0.62",
        "peaks_min_width_455": "2",
        "peaks_max_width_455": "40",
        "dashed_max_dash_points_perc": "0.65",
        "dashed_min_dash_points_perc": "0.15",
        "dashed_min_space_points_perc": "0.12",
        "dashed_min_count_of_dashed_lanes": "0.35",
    },
    "LANE_KEEPING": {
        "median_constant": "5",
        "print_desire_lane": "False",
        "max_coef_of_sharp_turn": "0.0025",
        "min_coef_of_sharp_turn": "0.0008",
        "sharp_turning_factor": "1.5",
        "min_smoothing_factor": "0.25",
        "max_smoothing_factor": "0.85",
        "mu": "0.5",
        "sigma": "0.4",
        "bottom_width_455": "160",
        "top_width_455": "130",
        "bottom_width_405": "170",
        "top_width_405": "140",
    },
    "CHANGE_LANE": {
        "max_smoothing_iterations": "20",
        "threshold": "50",
        "count": "8",
        "dif_from_mid_multiplier_static": "1.0",
        "dif_from_mid_multiplier_dynamic": "1.0",
        "max_lane_changing_tries_static": "25",
        "max_lane_changing_tries_dynamic": "25",
    },
}


def load_lane_config(extra_paths: Optional[Sequence[str]] = None) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read_dict(DEFAULTS)

    candidates = []

    env_path = os.environ.get("BFMC_LANE_CONFIG", "").strip()
    if env_path:
        candidates.append(env_path)

    candidates.append(os.path.join(os.getcwd(), "config.ini"))

    here = os.path.dirname(__file__)
    candidates.append(os.path.join(here, "config.ini"))

    if extra_paths:
        candidates.extend([p for p in extra_paths if p])

    for p in candidates:
        try:
            if p and os.path.exists(p):
                cfg.read(p)
        except Exception:
            continue

    return cfg
