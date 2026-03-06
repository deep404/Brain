# src/utils/config.py
# ============================================================================
# Centralised configuration reader for the BFMC Brain.
#
# Reads variables from the .env file at the project root.
# Usage:
#     from src.utils.config import cfg
#     if cfg.USE_LIVE_CAMERA:
#         ...
#     model = load(cfg.TSD_WEIGHTS)
#
# The module exposes a single `cfg` singleton of type `BFMCConfig`.
# All values are typed (bool / int / float / str / list[int]) and fall back
# to sensible defaults if the .env file is missing or a key is absent.
# ============================================================================

import os
from pathlib import Path


def _find_env_file() -> str:
    """Walk up from this file's directory to find the .env file."""
    d = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = d / ".env"
        if candidate.is_file():
            return str(candidate)
        d = d.parent
    # Fallback: project root next to main.py
    return str(Path(__file__).resolve().parent.parent.parent / ".env")


def _parse_env_file(path: str) -> dict:
    """Parse a simple KEY=VALUE .env file. Ignores comments and blank lines."""
    data: dict = {}
    if not os.path.isfile(path):
        return data
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove surrounding quotes if present
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            data[key] = value
    return data


class BFMCConfig:
    """
    Typed accessor for BFMC environment variables.

    Resolution order (highest priority first):
        1. OS environment variable  (allows runtime override)
        2. .env file value
        3. Hardcoded default
    """

    def __init__(self):
        self._env_path = _find_env_file()
        self._data = _parse_env_file(self._env_path)

    # ── helpers ──────────────────────────────────────────────────────────

    def _get(self, key: str, default: str = "") -> str:
        """Fetch a raw string value: OS env > .env file > default."""
        return os.environ.get(key, self._data.get(key, default))

    def _bool(self, key: str, default: bool = False) -> bool:
        raw = self._get(key, str(default))
        return raw.strip().lower() in ("true", "1", "yes")

    def _int(self, key: str, default: int = 0) -> int:
        try:
            return int(self._get(key, str(default)))
        except ValueError:
            return default

    def _float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self._get(key, str(default)))
        except ValueError:
            return default

    def _int_list(self, key: str, default: str = "") -> list:
        raw = self._get(key, default).strip()
        if not raw:
            return []
        return [int(x.strip()) for x in raw.split(",") if x.strip()]

    # ── Camera & Video ───────────────────────────────────────────────────

    @property
    def USE_LIVE_CAMERA(self) -> bool:
        """Use live USB camera feed (True) or a recorded video file (False)."""
        return self._bool("BFMC_USE_LIVE_CAMERA", False)

    @property
    def VIDEO_PATH(self) -> str:
        """Path to the playback video file (relative to Brain/)."""
        return self._get("BFMC_VIDEO_PATH", "raw_data/bfmc2020_online_2.mp4")

    @property
    def LOOP_VIDEO(self) -> bool:
        """Loop video file when it reaches the end."""
        return self._bool("BFMC_LOOP_VIDEO", True)

    @property
    def CAMERA_FPS(self) -> float:
        """Target FPS for the camera / video thread."""
        return self._float("BFMC_CAMERA_FPS", 20.0)

    @property
    def CAMERA_TYPE(self) -> str:
        """Camera model identifier ('455' or '405')."""
        return self._get("BFMC_CAMERA_TYPE", "455")

    @property
    def CAMERA_MAIN_WIDTH(self) -> int:
        return self._int("BFMC_CAMERA_MAIN_WIDTH", 2048)

    @property
    def CAMERA_MAIN_HEIGHT(self) -> int:
        return self._int("BFMC_CAMERA_MAIN_HEIGHT", 1080)

    @property
    def CAMERA_LORES_WIDTH(self) -> int:
        return self._int("BFMC_CAMERA_LORES_WIDTH", 512)

    @property
    def CAMERA_LORES_HEIGHT(self) -> int:
        return self._int("BFMC_CAMERA_LORES_HEIGHT", 270)

    @property
    def CAMERA_BRIGHTNESS(self) -> float:
        return self._float("BFMC_CAMERA_BRIGHTNESS", 0.5)

    @property
    def CAMERA_CONTRAST(self) -> float:
        return self._float("BFMC_CAMERA_CONTRAST", 16.0)

    # ── Traffic-Sign Detection ───────────────────────────────────────────

    @property
    def TSD_WEIGHTS(self) -> str:
        """Path to YOLOv8 weights file for traffic-sign detection."""
        return self._get("BFMC_TSD_WEIGHTS", "traffic-sign-detection-model/traffic-sign-yolo26n-bfmc.pt")

    @property
    def TSD_CONFIDENCE(self) -> float:
        """Minimum YOLO confidence threshold [0.0–1.0]."""
        return self._float("BFMC_TSD_CONFIDENCE", 0.25)

    @property
    def TSD_IMGSZ(self) -> int:
        """YOLO inference image size."""
        return self._int("BFMC_TSD_IMGSZ", 640)

    @property
    def TSD_FPS(self) -> float:
        """Target FPS for the traffic-sign detection thread. 0 = no rate limit."""
        return self._float("BFMC_TSD_FPS", 0.0)

    @property
    def TSD_INPUT_MESSAGE(self) -> str:
        """Camera message to subscribe to for TSD input."""
        return self._get("BFMC_TSD_INPUT_MESSAGE", "mainCamera")

    @property
    def SIGN_TRACK_CONFIDENCE(self) -> float:
        """Min confidence to count a traffic sign for position tracking."""
        return self._float("BFMC_SIGN_TRACK_CONFIDENCE", 0.5)

    @property
    def SIGN_ROI_MIN_RATIO(self) -> float:
        """Min bbox-area / frame-area ratio for a sign to be considered 'near'."""
        return self._float("BFMC_SIGN_ROI_MIN_RATIO", 0.005)

    @property
    def SIGN_MATCH_WINDOW(self) -> int:
        """Route-node indices ahead of current position to search for sign matches."""
        return self._int("BFMC_SIGN_MATCH_WINDOW", 60)

    @property
    def SIGN_MATCH_BEHIND(self) -> int:
        """Route-node indices behind current position still valid for matching."""
        return self._int("BFMC_SIGN_MATCH_BEHIND", 10)

    @property
    def TSD_DEBUG(self) -> bool:
        return self._bool("BFMC_TSD_DEBUG", False)

    # ── Near-field Region of Interest (ROI) ──────────────────────────────

    @property
    def ROI_Y_START(self) -> float:
        """Vertical start of the ROI as fraction of frame height (0=top, 1=bottom)."""
        return self._float("BFMC_ROI_Y_START", 0.4)

    @property
    def ROI_Y_END(self) -> float:
        """Vertical end of the ROI."""
        return self._float("BFMC_ROI_Y_END", 1.0)

    @property
    def ROI_X_START(self) -> float:
        """Horizontal start of the ROI."""
        return self._float("BFMC_ROI_X_START", 0.0)

    @property
    def ROI_X_END(self) -> float:
        """Horizontal end of the ROI."""
        return self._float("BFMC_ROI_X_END", 1.0)

    @property
    def STOP_LINE_MIN_DISTANCE(self) -> float:
        """Min stop_line_distance ratio for a stop-line event (higher = closer to car)."""
        return self._float("BFMC_STOP_LINE_MIN_DISTANCE", 0.5)

    # ── Lane Assist / Lane Detection ─────────────────────────────────────

    @property
    def LA_FPS(self) -> float:
        """Target FPS for the lane-assist thread. 0 = process every available frame."""
        return self._float("BFMC_LA_FPS", 0.0)

    @property
    def LA_INPUT_MESSAGE(self) -> str:
        """Camera message to subscribe to for lane assist."""
        return self._get("BFMC_LA_INPUT_MESSAGE", "serialCamera")

    @property
    def LA_DEBUG(self) -> bool:
        return self._bool("BFMC_LA_DEBUG", False)

    @property
    def MAX_LK_STEER(self) -> int:
        """Max steering angle for lane-keeping PID."""
        return self._int("BFMC_MAX_LK_STEER", 25)

    @property
    def LANE_CONFIG(self) -> str:
        """Optional path to a lane-detection INI config file."""
        return self._get("BFMC_LANE_CONFIG", "")

    # ── Route Planning ───────────────────────────────────────────────────

    @property
    def GRAPHML_PATH(self) -> str:
        """Path to the competition track GraphML file."""
        return self._get("BFMC_GRAPHML_PATH", "competition_graph.graphml")

    @property
    def ROUTE_START(self) -> int:
        """Start node ID for route planning."""
        return self._int("BFMC_ROUTE_START", 86)

    @property
    def ROUTE_FINISH(self) -> int:
        """Finish node ID for route planning."""
        return self._int("BFMC_ROUTE_FINISH", 85)

    @property
    def ROUTE_CHECKPOINTS(self) -> list:
        """List of must-pass node IDs (comma-separated in .env)."""
        return self._int_list("BFMC_ROUTE_CHECKPOINTS", "87,90,303,135,318,406,178,132")

    @property
    def ROUTE_VISIT_IN_ORDER(self) -> bool:
        """Visit checkpoints in listed order (True) or find optimal permutation (False)."""
        return self._bool("BFMC_ROUTE_VISIT_IN_ORDER", False)

    @property
    def ROUTE_FORWARD_DEG(self) -> float:
        """Angle threshold for classifying turns as 'forward'."""
        return self._float("BFMC_ROUTE_FORWARD_DEG", 35.0)

    @property
    def ROUTE_LANE_WEIGHT_SCALE(self) -> float:
        """Right-hand lane heuristic weight."""
        return self._float("BFMC_ROUTE_LANE_WEIGHT_SCALE", 0.35)

    # ── Serial Communication ─────────────────────────────────────────────

    @property
    def TRAFFIC_COM_DEVICE_ID(self) -> int:
        """V2X / traffic communication device ID."""
        return self._int("BFMC_TRAFFIC_COM_DEVICE_ID", 3)

    @property
    def SERIAL_DEVICE_PATTERN(self) -> str:
        """Regex for auto-detecting the serial port."""
        return self._get("BFMC_SERIAL_DEVICE_PATTERN", r"/dev/ttyACM\d+")

    @property
    def SERIAL_BAUD_RATE(self) -> int:
        return self._int("BFMC_SERIAL_BAUD_RATE", 115200)

    @property
    def SERIAL_TIMEOUT(self) -> float:
        return self._float("BFMC_SERIAL_TIMEOUT", 0.1)

    @property
    def SERIAL_LOG_FILE(self) -> str:
        return self._get("BFMC_SERIAL_LOG_FILE", "temp/serial_history.log")

    @property
    def SERIAL_DEBUG(self) -> bool:
        return self._bool("BFMC_SERIAL_DEBUG", False)

    # ── Dashboard ────────────────────────────────────────────────────────

    @property
    def DASHBOARD_HOST(self) -> str:
        return self._get("BFMC_DASHBOARD_HOST", "0.0.0.0")

    @property
    def DASHBOARD_PORT(self) -> int:
        return self._int("BFMC_DASHBOARD_PORT", 5005)

    @property
    def CORS_ORIGINS(self) -> str:
        return self._get("BFMC_CORS_ORIGINS", "*")

    @property
    def DASHBOARD_WIDTH(self) -> int:
        return self._int("BFMC_DASHBOARD_WIDTH", 512)

    @property
    def DASHBOARD_HEIGHT(self) -> int:
        return self._int("BFMC_DASHBOARD_HEIGHT", 270)

    @property
    def DASHBOARD_SIZE(self) -> tuple:
        """Dashboard preview image size as (width, height) tuple."""
        return (self.DASHBOARD_WIDTH, self.DASHBOARD_HEIGHT)

    @property
    def DASHBOARD_DEBUG(self) -> bool:
        return self._bool("BFMC_DASHBOARD_DEBUG", False)

    @property
    def HEARTBEAT_MAX_RETRIES(self) -> int:
        return self._int("BFMC_HEARTBEAT_MAX_RETRIES", 3)

    @property
    def HEARTBEAT_INTERVAL(self) -> int:
        return self._int("BFMC_HEARTBEAT_INTERVAL", 20)

    @property
    def HEARTBEAT_RETRY_INTERVAL(self) -> int:
        return self._int("BFMC_HEARTBEAT_RETRY_INTERVAL", 5)

    # ── Recording ────────────────────────────────────────────────────────

    @property
    def RECORDING_FPS(self) -> int:
        return self._int("BFMC_RECORDING_FPS", 5)

    @property
    def RECORDING_CODEC(self) -> str:
        return self._get("BFMC_RECORDING_CODEC", "XVID")

    # ── Debug Flags ──────────────────────────────────────────────────────

    @property
    def CAMERA_DEBUG(self) -> bool:
        return self._bool("BFMC_CAMERA_DEBUG", False)

    @property
    def SEMAPHORE_DEBUG(self) -> bool:
        return self._bool("BFMC_SEMAPHORE_DEBUG", False)

    @property
    def TRAFFIC_COM_DEBUG(self) -> bool:
        return self._bool("BFMC_TRAFFIC_COM_DEBUG", False)

    # ── System ───────────────────────────────────────────────────────────

    @property
    def STARTUP_DELAY(self) -> int:
        """Seconds to wait after spawning all processes before they begin."""
        return self._int("BFMC_STARTUP_DELAY", 10)

    @property
    def SHUTDOWN_TIMEOUT(self) -> int:
        """Timeout in seconds when joining processes during shutdown."""
        return self._int("BFMC_SHUTDOWN_TIMEOUT", 1)


# ── Module-level singleton ───────────────────────────────────────────────────
cfg = BFMCConfig()
