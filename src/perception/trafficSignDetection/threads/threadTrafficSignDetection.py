# src/perception/trafficSignDetection/threads/threadTrafficSignDetection.py

import os
import time
import base64

import cv2
import numpy as np

from src.templates.threadwithstop import ThreadWithStop
from src.utils.messages import allMessages
from src.utils.messages.messageHandlerSubscriber import messageHandlerSubscriber
from src.utils.messages.messageHandlerSender import messageHandlerSender
from src.utils.messages.allMessages import TrafficSignMask


class threadTrafficSignDetection(ThreadWithStop):
    def __init__(
        self,
        queuesList,
        logger,
        weights_path=None,
        input_message="mainCamera",
        target_fps=2.0,
        conf=0.25,
        imgsz=640,
        dashboard_size=(512, 270),
    ):
        super().__init__(pause=0.01)
        self.queuesList = queuesList
        self.logger = logger

        self._dash_log("INFO", "TSD thread initialized (mask mode).")

        self.weights_path = weights_path or os.environ.get("BFMC_TSD_WEIGHTS", "")
        self.input_message_name = input_message

        # inference rate only (video stays smooth via serialCamera pipeline)
        self.target_fps = max(0.05, float(target_fps))
        self.min_period_s = 1.0 / self.target_fps

        self.conf = float(conf)
        self.imgsz = int(imgsz)

        self.dashboard_w, self.dashboard_h = int(dashboard_size[0]), int(dashboard_size[1])

        # Subscribe to a camera stream (lastOnly -> no backlog)
        input_enum = getattr(allMessages, self.input_message_name)
        self.frame_sub = messageHandlerSubscriber(self.queuesList, input_enum, "lastOnly", True)

        # Send PNG overlay mask to dashboard
        self.mask_sender = messageHandlerSender(self.queuesList, TrafficSignMask)

        self._last_infer_t = 0.0
        self._model = None
        self._device = None

        self._load_model()

    def _pick_default_weights(self) -> str:
        candidates = [
            self.weights_path,
            "traffic-sign-detection-model/nano.pt",
            "traffic-sign-detection-model/small.pt",
            "traffic-sign-detection-model/nano/best.pt",
            "traffic-sign-detection-model/small/best.pt",
        ]
        for p in candidates:
            if p and os.path.exists(p):
                return p
        return self.weights_path

    def _load_model(self):
        try:
            from ultralytics import YOLO
            import torch

            self._dash_log("INFO", f"Starting TSD. target_fps={self.target_fps}, conf={self.conf}, imgsz={self.imgsz}")

            weights = self._pick_default_weights()
            if not weights or not os.path.exists(weights):
                self._dash_log("WARNING", f"Weights not found. Set BFMC_TSD_WEIGHTS or pass weights_path. Tried: {weights}")
                self._model = None
                return

            self._device = 0 if torch.cuda.is_available() else "cpu"
            self._model = YOLO(weights)
            self._dash_log("INFO", f"Loaded model weights={weights} device={self._device}")
        except Exception as e:
            self._dash_log("ERROR", f"Failed to load YOLO model: {e}")
            self._model = None

    def _decode_b64_jpeg(self, b64_str: str):
        img_bytes = base64.b64decode(b64_str)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _encode_b64_png_rgba(self, rgba_img) -> str:
        ok, buf = cv2.imencode(".png", rgba_img)
        if not ok:
            raise RuntimeError("cv2.imencode(.png) failed")
        return base64.b64encode(buf.tobytes()).decode("utf-8")

    def _blank_mask_b64(self) -> str:
        rgba = np.zeros((self.dashboard_h, self.dashboard_w, 4), dtype=np.uint8)
        return self._encode_b64_png_rgba(rgba)

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

        prefix = "\033[1;97m[ TrafficSignDetection ] :\033[0m"
        q.put(f"{prefix} {level_color} - {msg}")

    def _log_detections(self, det_strings):
        if not det_strings:
            self._dash_log("INFO", "detections: none")
        else:
            self._dash_log("INFO", "detections: " + ", ".join(det_strings))

    def _build_mask_from_boxes(self, orig_w, orig_h, boxes_xyxy, labels, confs) -> str:
        """
        Build transparent PNG mask (RGBA) sized to dashboard_w/dashboard_h.
        Draw boxes+text in green, background fully transparent.
        """
        bgr = np.zeros((self.dashboard_h, self.dashboard_w, 3), dtype=np.uint8)

        sx = self.dashboard_w / max(1.0, float(orig_w))
        sy = self.dashboard_h / max(1.0, float(orig_h))

        for (x1, y1, x2, y2), lab, cf in zip(boxes_xyxy, labels, confs):
            x1 = int(max(0, min(self.dashboard_w - 1, x1 * sx)))
            x2 = int(max(0, min(self.dashboard_w - 1, x2 * sx)))
            y1 = int(max(0, min(self.dashboard_h - 1, y1 * sy)))
            y2 = int(max(0, min(self.dashboard_h - 1, y2 * sy)))

            cv2.rectangle(bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                bgr,
                f"{lab} {cf:.2f}",
                (x1, max(15, y1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

        rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        drawn = np.any(bgr != 0, axis=2)
        rgba[..., 3] = 0
        rgba[drawn, 3] = 220  # mostly-opaque overlay pixels

        return self._encode_b64_png_rgba(rgba)

    def thread_work(self):
        if self._model is None:
            self._load_model()
            return

        now = time.time()
        if (now - self._last_infer_t) < self.min_period_s:
            return

        msg = self.frame_sub.receive()
        if msg is None:
            return

        try:
            frame = self._decode_b64_jpeg(msg)
            if frame is None:
                return

            # Inference
            results = self._model.predict(
                source=frame,
                conf=self.conf,
                imgsz=self.imgsz,
                verbose=False,
                device=self._device,
            )
            r = results[0]

            # Extract detections
            boxes = getattr(r, "boxes", None)
            det_strings = []

            if boxes is None or len(boxes) == 0:
                # send blank mask to clear overlay
                self._log_detections([])
                self.mask_sender.send(self._blank_mask_b64())
                self._last_infer_t = now
                return

            names = getattr(r, "names", None) or {}
            cls_ids = boxes.cls.detach().cpu().numpy().astype(int)
            confs = boxes.conf.detach().cpu().numpy()
            xyxy = boxes.xyxy.detach().cpu().numpy()

            labels = []
            conf_list = []
            xyxy_list = []
            for c, p, (x1, y1, x2, y2) in zip(cls_ids, confs, xyxy):
                label = names.get(int(c), str(int(c)))
                labels.append(label)
                conf_list.append(float(p))
                xyxy_list.append((float(x1), float(y1), float(x2), float(y2)))
                det_strings.append(f"{label}:{p:.2f}@[{int(x1)},{int(y1)},{int(x2)},{int(y2)}]")

            self._log_detections(det_strings)

            # r.orig_shape is (h, w)
            orig_h, orig_w = getattr(r, "orig_shape", frame.shape[:2])

            mask_b64 = self._build_mask_from_boxes(
                orig_w=orig_w,
                orig_h=orig_h,
                boxes_xyxy=xyxy_list,
                labels=labels,
                confs=conf_list,
            )
            self.mask_sender.send(mask_b64)

            self._last_infer_t = now

        except Exception as e:
            self._dash_log("ERROR", f"inference error: {e}")
