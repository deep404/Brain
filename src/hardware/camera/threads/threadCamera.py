import cv2
import os
import threading
import base64
import time

from src.utils.messages.allMessages import (
    mainCamera,
    serialCamera,
    Recording,
    Record,
    Brightness,
    Contrast,
    CameraReset,
)
from src.utils.messages.messageHandlerSender import messageHandlerSender
from src.utils.messages.messageHandlerSubscriber import messageHandlerSubscriber
from src.templates.threadwithstop import ThreadWithStop
from src.utils.messages.allMessages import StateChange
from src.statemachine.systemMode import SystemMode


class threadCamera(ThreadWithStop):
    """
    Camera thread that can stream either:
      - Live USB camera (OpenCV VideoCapture, auto-detected)  OR
      - A recorded MP4 in infinite loop (OpenCV VideoCapture)

    Publishes mainCamera + serialCamera so all other components keep
    working unchanged.
    """

    def __init__(
        self,
        queuesList,
        logger,
        debugger,
        use_live_camera: bool = True,
        video_path: str = "raw_data/bfmc2020_online_2.mp4",
        loop_video: bool = True,
        target_fps: float = 0.0,   # 0 = max speed, no throttle
    ):
        # No pause: camera runs as fast as possible.
        # For live camera, capture rate is limited by the hardware itself.
        # For video, frames are read at maximum throughput.
        super(threadCamera, self).__init__(pause=0.0)

        self.queuesList = queuesList
        self.logger = logger
        self.debugger = debugger

        # --- new: mode switch ---
        self.use_live_camera = bool(use_live_camera)
        self.video_path = video_path
        self.loop_video = bool(loop_video)

        self.frame_rate = 5
        self.recording = False

        self.video_writer = None
        self.cap = None             # cv2.VideoCapture for USB camera or video file
        self._is_live_cap = False   # True when cap is a live USB camera
        self._cam_index = -1        # device index for auto-reconnect

        # Background reader thread state (live camera only)
        self._reader_thread = None
        self._reader_lock = threading.Lock()
        self._latest_frame = None   # most recent frame from reader
        self._reader_running = False

        # For brightness/contrast sliders
        self._brightness = 0.5  # 0..1, treat 0.5 as neutral
        self._contrast = 16.0   # 0..32, treat 16 as neutral

        self.recordingSender = messageHandlerSender(self.queuesList, Recording)
        self.mainCameraSender = messageHandlerSender(self.queuesList, mainCamera)
        self.serialCameraSender = messageHandlerSender(self.queuesList, serialCamera)

        self.subscribe()
        self._init_source()
        self.queue_sending()
        self.configs()

    def subscribe(self):
        self.recordSubscriber = messageHandlerSubscriber(self.queuesList, Record, "lastOnly", True)
        self.brightnessSubscriber = messageHandlerSubscriber(self.queuesList, Brightness, "lastOnly", True)
        self.contrastSubscriber = messageHandlerSubscriber(self.queuesList, Contrast, "lastOnly", True)
        self.stateChangeSubscriber = messageHandlerSubscriber(self.queuesList, StateChange, "lastOnly", True)
        self.resetSubscriber = messageHandlerSubscriber(self.queuesList, CameraReset, "lastOnly", True)

    def queue_sending(self):
        if self._blocker.is_set():
            return
        self.recordingSender.send(self.recording)
        threading.Timer(1, self.queue_sending).start()

    # -------------------- source init --------------------
    def _init_source(self):
        if self.use_live_camera:
            self._init_live_camera()
        else:
            self._init_video()

    def _init_live_camera(self):
        """
        Auto-detect and open the first available USB camera, then start
        a background reader thread that continuously calls cap.read().

        The reader absorbs V4L2 select() timeouts (~10 s each on WSL2)
        so the main thread_work() never blocks.  Between timeouts the
        reader stores fresh frames at full camera FPS.
        """
        self._is_live_cap = False

        # Find candidate device indices from /dev/video*
        candidates = []
        for i in range(10):
            if os.path.exists(f"/dev/video{i}"):
                candidates.append(i)
        if not candidates:
            candidates = list(range(5))

        print(
            f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;96mINFO\033[0m - "
            f"Searching for USB camera (candidates: {candidates})..."
        )

        for idx in candidates:
            cap = self._try_open_device(idx)
            if cap is not None:
                self.cap = cap
                self._is_live_cap = True
                self._cam_index = idx

                actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
                print(
                    f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;92mINFO\033[0m - "
                    f"USB camera opened at /dev/video{idx} "
                    f"({actual_w}x{actual_h} @ {actual_fps:.0f}fps)"
                )

                # Start background reader
                self._start_reader()
                return

        # Nothing worked
        is_wsl = self._is_wsl()
        err = (
            f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;91mERROR\033[0m - "
            f"No USB camera found (tried {candidates}). Camera disabled."
        )
        if is_wsl:
            err += (
                "\n\033[1;93m  WSL2 detected — USB devices need usbipd-win:\033[0m"
                "\n\033[1;93m    (admin PowerShell) usbipd list\033[0m"
                "\n\033[1;93m    (admin PowerShell) usbipd bind --busid <BUS>  &&  usbipd attach --wsl --busid <BUS>\033[0m"
                "\n\033[1;93m    (WSL)  sudo apt install linux-tools-virtual hwdata  &&  ls /dev/video*\033[0m"
            )
        print(err)

    # ---- background reader ------------------------------------------------
    def _start_reader(self):
        """Launch daemon thread that continuously grabs frames from cap."""
        self._reader_running = True
        self._latest_frame = None
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True, name="CameraReader"
        )
        self._reader_thread.start()

    def _stop_reader(self):
        self._reader_running = False
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=12)  # slightly above V4L2 timeout
            self._reader_thread = None

    def _reader_loop(self):
        """
        Continuously read frames.  V4L2 select() timeouts block this
        thread for ~10 s but do NOT block the main thread.
        After a timeout, the next read usually succeeds immediately.
        """
        consecutive_fails = 0
        while self._reader_running and self.cap is not None:
            try:
                ok, frame = self.cap.read()
            except Exception:
                ok, frame = False, None

            if ok and frame is not None:
                with self._reader_lock:
                    self._latest_frame = frame
                consecutive_fails = 0
            else:
                consecutive_fails += 1
                if consecutive_fails >= 10:
                    # Camera is truly gone — try to reopen
                    print(
                        "\033[1;97m[ Camera Thread ] :\033[0m \033[1;93mWARNING\033[0m - "
                        f"{consecutive_fails} consecutive read failures, "
                        f"reopening /dev/video{self._cam_index}..."
                    )
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                    time.sleep(2.0)
                    cap = self._try_open_device(self._cam_index)
                    if cap is not None:
                        self.cap = cap
                        consecutive_fails = 0
                        print(
                            "\033[1;97m[ Camera Thread ] :\033[0m \033[1;92mINFO\033[0m - "
                            "Camera reconnected successfully"
                        )
                    else:
                        print(
                            "\033[1;97m[ Camera Thread ] :\033[0m \033[1;91mERROR\033[0m - "
                            "Camera reconnect failed. Stopping reader."
                        )
                        self._reader_running = False

    # ---- open helper (no blocking warmup reads) ----------------------------
    @staticmethod
    def _try_open_device(idx):
        """
        Try to open a camera device at the given index.
        Sets MJPG fourcc and buffer size 1 for compatibility.
        Does NOT attempt a blocking read (the reader thread handles that).
        Returns the cv2.VideoCapture if opened, else None.
        """
        for backend in [cv2.CAP_V4L2, cv2.CAP_ANY]:
            try:
                cap = cv2.VideoCapture(idx, backend)
                if not cap.isOpened():
                    continue

                # MJPG is broadly supported and avoids raw-format issues
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                return cap
            except Exception:
                pass
        return None

    @staticmethod
    def _is_wsl():
        try:
            with open("/proc/version", "r") as f:
                return "microsoft" in f.read().lower()
        except Exception:
            return False

    def _init_video(self):
        self.cap = cv2.VideoCapture(self.video_path)  # OpenCV reads video files via VideoCapture() :contentReference[oaicite:0]{index=0}
        if not self.cap.isOpened():
            print(f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;91mERROR\033[0m - Cannot open video: {self.video_path}")
            self.cap = None
            return

        # Pace video playback to its native FPS so we don't flood the pipe
        native_fps = self.cap.get(cv2.CAP_PROP_FPS), 30.0
        self._video_fps = native_fps[0] if native_fps[0] > 0 else native_fps[1]
        self._video_frame_delay = 1.0 / self._video_fps
        self._last_video_frame_t = 0.0

        print(
            f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;92mINFO\033[0m - "
            f"Video mode initialized ({self._video_fps:.1f} fps): {self.video_path}"
        )

    # -------------------- video processing helpers --------------------
    def _apply_brightness_contrast(self, img_bgr):
        # Basic linear transform: out = alpha * img + beta :contentReference[oaicite:1]{index=1}
        alpha = max(0.0, float(self._contrast) / 16.0)        # 16 -> 1.0
        beta = int((float(self._brightness) - 0.5) * 255.0)   # 0.5 -> 0
        return cv2.convertScaleAbs(img_bgr, alpha=alpha, beta=beta)

    # ================================ RUN ================================================
    def thread_work(self):
        # --- camera reset (seek video to frame 0, only for pre-recorded) ---
        try:
            resetRecv = self.resetSubscriber.receive()
            if resetRecv is not None and self.cap is not None and not self._is_live_cap:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self._last_video_frame_t = 0.0
                print(
                    "\033[1;97m[ Camera Thread ] :\033[0m \033[1;92mINFO\033[0m - "
                    "Video reset to frame 0 (dashboard reset)"
                )
        except Exception:
            pass

        # --- recording toggle ---
        try:
            recordRecv = self.recordSubscriber.receive()
            if recordRecv is not None:
                self.recording = bool(recordRecv)

                if not self.recording:
                    if self.video_writer is not None:
                        self.video_writer.release()
                        self.video_writer = None
                else:
                    fourcc = cv2.VideoWriter_fourcc(*"XVID")
                    self.video_writer = cv2.VideoWriter(
                        "output_video" + str(time.time()) + ".avi",
                        fourcc,
                        self.frame_rate,
                        (2048, 1080),
                    )
        except Exception as e:
            print(f"\033[1;97m[ Camera ] :\033[0m \033[1;91mERROR\033[0m - {e}")

        # --- get frame from selected source ---
        try:
            if self.cap is None:
                time.sleep(0.1)
                return

            if self._is_live_cap:
                # ── Live USB camera — grab latest frame from reader ──────
                with self._reader_lock:
                    frame = self._latest_frame
                    self._latest_frame = None  # consume it

                if frame is None:
                    # Reader hasn't produced a frame yet (warmup or timeout)
                    time.sleep(0.03)
                    return

                mainRequest = cv2.resize(frame, (2048, 1080), interpolation=cv2.INTER_AREA)
                serialRequest = cv2.resize(frame, (512, 270), interpolation=cv2.INTER_AREA)

            else:
                # ── Pre-recorded video ───────────────────────────────────
                now = time.time()
                elapsed = now - self._last_video_frame_t
                if elapsed < self._video_frame_delay:
                    time.sleep(self._video_frame_delay - elapsed)
                self._last_video_frame_t = time.time()

                ok, frame = self.cap.read()
                if not ok:
                    if self.loop_video:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok, frame = self.cap.read()
                if not ok:
                    time.sleep(0.05)
                    return

                frame = self._apply_brightness_contrast(frame)
                mainRequest = cv2.resize(frame, (2048, 1080), interpolation=cv2.INTER_AREA)
                serialRequest = cv2.resize(frame, (512, 270), interpolation=cv2.INTER_AREA)

            # --- optional recording ---
            if self.recording and self.video_writer is not None:
                self.video_writer.write(mainRequest)

            # --- encode + publish ---
            _, mainEncodedImg = cv2.imencode(".jpg", mainRequest)
            _, serialEncodedImg = cv2.imencode(".jpg", serialRequest)

            mainEncodedImageData = base64.b64encode(mainEncodedImg).decode("utf-8")
            serialEncodedImageData = base64.b64encode(serialEncodedImg).decode("utf-8")

            if self._blocker.is_set():
                return

            self.mainCameraSender.send(mainEncodedImageData)
            self.serialCameraSender.send(serialEncodedImageData)

        except Exception as e:
            print(f"\033[1;97m[ Camera ] :\033[0m \033[1;91mERROR\033[0m - {e}")

    # ================================ STATE CHANGE HANDLER ========================================
    def state_change_handler(self):
        message = self.stateChangeSubscriber.receive()
        if message is not None:
            modeDict = SystemMode[message].value["camera"]["thread"]
            if "resolution" in modeDict:
                print(f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;92mINFO\033[0m - Resolution changed to {modeDict['resolution']}")

    # =============================== STOP ================================================
    def stop(self):
        # Stop background reader first (so it doesn't use cap after release)
        self._stop_reader()

        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

        if self.cap is not None:
            self.cap.release()
            self.cap = None

        super(threadCamera, self).stop()

    # =============================== CONFIG ==============================================
    def configs(self):
        if self._blocker.is_set():
            return

        # Brightness
        if self.brightnessSubscriber.is_data_in_pipe():
            message = self.brightnessSubscriber.receive()
            val = max(0.0, min(1.0, float(message)))
            self._brightness = val

        # Contrast
        if self.contrastSubscriber.is_data_in_pipe():
            message = self.contrastSubscriber.receive()
            val = max(0.0, min(32.0, float(message)))
            self._contrast = val

        threading.Timer(1, self.configs).start()
