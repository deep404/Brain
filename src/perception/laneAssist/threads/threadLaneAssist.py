# src/perception/laneAssist/threads/threadLaneAssist.py

import base64
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from src.templates.threadwithstop import ThreadWithStop
from src.utils.messages import allMessages
from src.utils.messages.allMessages import LaneAssistMask
from src.utils.messages.messageHandlerSubscriber import messageHandlerSubscriber
from src.utils.messages.messageHandlerSender import messageHandlerSender


class threadLaneAssist(ThreadWithStop):
    """
    Lane Assist worker thread:
    - Subscribes to a camera stream (default serialCamera) using lastOnly -> no backlog.
    - Runs lane detection / lane keeping when ready (rate-limited by target_fps).
    - Outputs a transparent PNG mask (RGBA, base64) that can be overlaid on the live camera feed.
    """

    def __init__(
        self,
        queuesList,
        logger,
        input_message: str = "serialCamera",
        target_fps: float = 5.0,
        camera_type: str = "455",
        dashboard_size: Tuple[int, int] = (512, 270),
    ):
        super().__init__(pause=0.01)

        self.queuesList = queuesList
        self.logger = logger

        self.input_message_name = input_message
        self.target_fps = max(0.05, float(target_fps))
        self.min_period_s = 1.0 / self.target_fps
        self.camera_type = str(camera_type)

        self.dashboard_w, self.dashboard_h = int(dashboard_size[0]), int(dashboard_size[1])

        input_enum = getattr(allMessages, self.input_message_name)
        self.frame_sub = messageHandlerSubscriber(self.queuesList, input_enum, "lastOnly", True)

        self.mask_sender = messageHandlerSender(self.queuesList, LaneAssistMask)

        self._last_run_t = 0.0
        self._lk = None
        self._ld = None

        self._dash_log(
            "INFO",
            f"LaneAssist thread initialized. input={input_message} fps={self.target_fps} camera={self.camera_type}",
        )

    # ----------------------- helpers -----------------------

    def _dash_log(self, level: str, msg: str):
        q = self.queuesList.get("Log", None)
        if q is None:
            return
        level = (level or "INFO").upper()
        level_color = {
            "INFO": "\033[1;92mINFO\033[0m",
            "WARNING": "\033[1;93mWARNING\033[0m",
            "ERROR": "\033[1;91mERROR\033[0m",
            "DEBUG": "\033[1;94mDEBUG\033[0m",
        }.get(level, level)
        prefix = "\033[1;97m[ LaneAssist ] :\033[0m"
        q.put(f"{prefix} {level_color} - {msg}")

    def _decode_b64_jpeg(self, b64_str: str) -> Optional[np.ndarray]:
        try:
            img_bytes = base64.b64decode(b64_str)
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None

    def _encode_b64_png_rgba(self, rgba_img: np.ndarray) -> str:
        ok, buf = cv2.imencode(".png", rgba_img)
        if not ok:
            raise RuntimeError("cv2.imencode(.png) failed")
        return base64.b64encode(buf.tobytes()).decode("utf-8")

    def _blank_mask_b64(self) -> str:
        rgba = np.zeros((self.dashboard_h, self.dashboard_w, 4), dtype=np.uint8)
        return self._encode_b64_png_rgba(rgba)

    def _ensure_models(self, width: int, height: int):
        if self._lk is not None and self._ld is not None:
            return

        # Lazy import: your module files must exist in repo:
        #   src/LaneKeeping/lanekeeping.py
        #   src/LaneDetection/detect.py
        from src.LaneKeeping.lanekeeping import LaneKeeping
        from src.LaneDetection.detect import LaneDetection

        self._lk = LaneKeeping(width=width, height=height, logger=self.logger, camera=self.camera_type)
        self._ld = LaneDetection(width=width, height=height, camera=self.camera_type, lk=self._lk)

        self._dash_log("INFO", f"LaneAssist models created for {width}x{height} camera={self.camera_type}")

    def _build_lane_mask(self, lane_det_results: dict) -> str:
        """
        Build an RGBA PNG overlay mask using the SAME HUD-style visualization
        methods from LaneDetection + LaneKeeping (like your screenshot).

        - zone layer: filled polygon between lanes (low alpha)
        - lines layer: neon lanes, peak dots, desired lane, stop line + HUD (high alpha)
        """

        h, w = self.dashboard_h, self.dashboard_w

        # Layers
        zone = np.zeros((h, w, 3), dtype=np.uint8)
        lines = np.zeros((h, w, 3), dtype=np.uint8)

        left = lane_det_results.get("left", [])
        right = lane_det_results.get("right", [])
        left_coef = lane_det_results.get("left_coef", None)
        right_coef = lane_det_results.get("right_coef", None)

        l_perc = float(lane_det_results.get("l_perc", 0.0) or 0.0)
        r_perc = float(lane_det_results.get("r_perc", 0.0) or 0.0)

        dashed_left = bool(lane_det_results.get("dashed_left", False))
        dashed_right = bool(lane_det_results.get("dashed_right", False))

        stop_line_detected = bool(lane_det_results.get("stop_line_detected", False))
        stop_line_segment = lane_det_results.get("stop_line_segment", None)
        stop_line_distance = lane_det_results.get("stop_line_distance", None)

        # -------------------------
        # 1) Lane zone (GREEN floor area)
        # -------------------------
        if left_coef is not None and right_coef is not None:
            # draw pure polygon into zone (alpha applied later)
            self._ld.visualize_lane_zone(left_coef, right_coef, zone, bgr_colour=(0, 200, 100), alpha=1.0)

        # -------------------------
        # 2) Neon lanes + peak dots (BLUE/ORANGE with circles)
        # -------------------------
        if left_coef is not None:
            self._ld.visualize_lane(left_coef, lines, bgr_colour=(255, 165, 0))   # left = orange
        if right_coef is not None:
            self._ld.visualize_lane(right_coef, lines, bgr_colour=(0, 165, 255))  # right = blue

        if left or right:
            self._ld.visualize_peaks(lines, left, right)

        # -------------------------
        # 3) Desired lane (NEON GREEN)
        # -------------------------
        try:
            if left_coef is not None or right_coef is not None:
                desire = self._lk.desired_lane(left_coef, right_coef)
                if desire is not None and len(desire) > 1:
                    self._lk.visualize_desire_lane(lines, desire, bgr_colour=(50, 205, 50))
        except Exception:
            pass

        # -------------------------
        # 4) Dashed badges (optional, like module)
        # -------------------------
        try:
            if dashed_left:
                # matches LaneDetection._draw_badge placement
                self._ld._draw_badge(lines, "DASHED", int(0.2 * w), int(h * 0.28), (180, 120, 0))
            if dashed_right:
                self._ld._draw_badge(lines, "DASHED", int(0.8 * w), int(h * 0.28), (0, 120, 180))
        except Exception:
            pass

        # -------------------------
        # 5) Stop line (orange glow + STOP LINE panel)
        # -------------------------
        if stop_line_detected and stop_line_segment is not None:
            try:
                self._ld.visualize_horizontal_line(lines, stop_line_segment, None)
            except Exception:
                pass

            # panel (copied from detect_stop_line, drawn onto overlay layer)
            try:
                if isinstance(stop_line_distance, (int, float)):
                    panel_w, panel_h = 200, 40
                    px, py = w - panel_w - 10, 10
                    overlay = lines.copy()
                    cv2.rectangle(overlay, (px, py), (px + panel_w, py + panel_h), (0, 0, 60), -1)
                    cv2.addWeighted(overlay, 0.7, lines, 0.3, 0, lines)
                    cv2.rectangle(lines, (px, py), (px + panel_w, py + panel_h), (0, 0, 200), 2)
                    cv2.putText(lines, "STOP LINE", (px + 8, py + 16),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 100, 255), 1, cv2.LINE_AA)
                    # distance bar
                    bar_x, bar_y = px + 8, py + 24
                    bar_w = panel_w - 16
                    dist_fill = int(bar_w * max(0.0, min(1.0, float(stop_line_distance))))
                    cv2.rectangle(lines, (bar_x, bar_y), (bar_x + bar_w, bar_y + 8), (40, 40, 40), -1)
                    cv2.rectangle(lines, (bar_x, bar_y), (bar_x + dist_fill, bar_y + 8), (0, 140, 255), -1)
                    cv2.rectangle(lines, (bar_x, bar_y), (bar_x + bar_w, bar_y + 8), (80, 80, 80), 1)
                    cv2.putText(lines, f"{float(stop_line_distance):.0%}", (bar_x + bar_w + 4, bar_y + 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.28, (180, 180, 180), 1, cv2.LINE_AA)
            except Exception:
                pass

        # -------------------------
        # 6) Certainty bars (L/R % at bottom)
        # -------------------------
        try:
            self._ld.visualize_lane_certainty(lines, l_perc, r_perc)
        except Exception:
            pass

        # -------------------------
        # Compose RGBA with correct transparency:
        # - zone: low alpha
        # - lines/hud: high alpha
        # -------------------------
        rgba = np.zeros((h, w, 4), dtype=np.uint8)

        zone_mask = np.any(zone != 0, axis=2)
        line_mask = np.any(lines != 0, axis=2)

        # zone first (semi-transparent)
        rgba[zone_mask, 0:3] = zone[zone_mask]
        rgba[zone_mask, 3] = 70   # tweak 50..110 to match your preference

        # lines/hud on top (opaque)
        rgba[line_mask, 0:3] = lines[line_mask]
        rgba[line_mask, 3] = 255

        return self._encode_b64_png_rgba(rgba)


    # ----------------------- main loop -----------------------

    def thread_work(self):
        now = time.time()
        if (now - self._last_run_t) < self.min_period_s:
            return

        msg = self.frame_sub.receive()
        if msg is None:
            return

        frame = self._decode_b64_jpeg(msg)
        if frame is None:
            return

        # Ensure processing resolution matches the overlay resolution
        if frame.shape[1] != self.dashboard_w or frame.shape[0] != self.dashboard_h:
            frame = cv2.resize(frame, (self.dashboard_w, self.dashboard_h), interpolation=cv2.INTER_AREA)

        self._ensure_models(width=self.dashboard_w, height=self.dashboard_h)

        try:
            results = self._ld.lanes_detection(frame.copy())
            angle, _ = self._lk.lane_keeping(results)

            dashed_left = results.get("dashed_left")
            dashed_right = results.get("dashed_right")
            stop_line = results.get("stop_line_detected")
            dist = results.get("stop_line_distance")

            self._dash_log(
                "INFO",
                f"angle={angle:.2f} deg | dashed(L,R)=({dashed_left},{dashed_right}) | stop_line={stop_line} dist={dist}",
            )

            mask_b64 = self._build_lane_mask(results)
            self.mask_sender.send(mask_b64)

            self._last_run_t = now

        except Exception as e:
            self._dash_log("ERROR", f"LaneAssist error: {e}")
            try:
                self.mask_sender.send(self._blank_mask_b64())
            except Exception:
                pass
