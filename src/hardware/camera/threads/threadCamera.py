import cv2
import threading
import base64
try:
    import picamera2
except Exception:
    picamera2 = None
import time

from src.utils.messages.allMessages import (
    mainCamera,
    serialCamera,
    Recording,
    Record,
    Brightness,
    Contrast,
)
from src.utils.messages.messageHandlerSender import messageHandlerSender
from src.utils.messages.messageHandlerSubscriber import messageHandlerSubscriber
from src.templates.threadwithstop import ThreadWithStop
from src.utils.messages.allMessages import StateChange
from src.statemachine.systemMode import SystemMode


class threadCamera(ThreadWithStop):
    """
    Camera thread that can stream either:
      - Live Raspberry Pi camera (picamera2)  OR
      - A recorded MP4 in infinite loop (OpenCV VideoCapture)

    It still publishes mainCamera + serialCamera so all other components keep working unchanged.
    """

    def __init__(
        self,
        queuesList,
        logger,
        debugger,
        use_live_camera: bool = True,
        video_path: str = "raw_data/bfmc2020_online_2.mp4",
        loop_video: bool = True,
        target_fps: float = 20.0,   # throttle to reduce CPU
    ):
        pause = 1.0 / max(1.0, float(target_fps))
        super(threadCamera, self).__init__(pause=pause)

        self.queuesList = queuesList
        self.logger = logger
        self.debugger = debugger

        # --- new: mode switch ---
        self.use_live_camera = bool(use_live_camera)
        self.video_path = video_path
        self.loop_video = bool(loop_video)

        self.frame_rate = 5
        self.recording = False

        self.video_writer = None  # was "" -> causes release() issues
        self.camera = None
        self.cap = None  # cv2.VideoCapture for mp4 mode

        # For video mode brightness/contrast (to mimic UI sliders)
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

    def queue_sending(self):
        if self._blocker.is_set():
            return
        self.recordingSender.send(self.recording)
        threading.Timer(1, self.queue_sending).start()

    # -------------------- source init --------------------
    def _init_source(self):
        if self.use_live_camera:
            self._init_camera()
        else:
            self._init_video()

    def _init_camera(self):
        if picamera2 is None:
            print("[ Camera Thread] INFO - picamera2/libcamera not available; camera disabled.")
            self.camera = None
            return

        try:
            if len(picamera2.Picamera2.global_camera_info()) == 0:
                print(f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;91mERROR\033[0m - No camera detected. Camera functionality will be disabled.")
                self.camera = None
                return

            self.camera = picamera2.Picamera2()
            config = self.camera.create_preview_configuration(
                buffer_count=1,
                queue=False,
                main={"format": "RGB888", "size": (2048, 1080)},
                lores={"size": (512, 270)},
                encode="lores",
            )
            self.camera.configure(config)  # type: ignore
            self.camera.start()
            print(f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;92mINFO\033[0m - Camera initialized successfully")
        except Exception as e:
            print(f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;91mERROR\033[0m - Failed to initialize camera: {e}")
            self.camera = None

    def _init_video(self):
        self.cap = cv2.VideoCapture(self.video_path)  # OpenCV reads video files via VideoCapture() :contentReference[oaicite:0]{index=0}
        if not self.cap.isOpened():
            print(f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;91mERROR\033[0m - Cannot open video: {self.video_path}")
            self.cap = None
            return

        print(f"\033[1;97m[ Camera Thread ] :\033[0m \033[1;92mINFO\033[0m - Video mode initialized: {self.video_path}")

    # -------------------- video processing helpers --------------------
    def _apply_brightness_contrast(self, img_bgr):
        # Basic linear transform: out = alpha * img + beta :contentReference[oaicite:1]{index=1}
        alpha = max(0.0, float(self._contrast) / 16.0)        # 16 -> 1.0
        beta = int((float(self._brightness) - 0.5) * 255.0)   # 0.5 -> 0
        return cv2.convertScaleAbs(img_bgr, alpha=alpha, beta=beta)

    # ================================ RUN ================================================
    def thread_work(self):
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
            if self.use_live_camera:
                if self.camera is None:
                    time.sleep(0.1)
                    return

                mainRequest = self.camera.capture_array("main")
                serialRequest = self.camera.capture_array("lores")
                serialRequest = cv2.cvtColor(serialRequest, cv2.COLOR_YUV2BGR_I420)

            else:
                if self.cap is None:
                    time.sleep(0.1)
                    return

                ok, frame = self.cap.read()
                if not ok:
                    # loop forever by rewinding to frame 0 (CAP_PROP_POS_FRAMES is next frame index) :contentReference[oaicite:2]{index=2}
                    if self.loop_video:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # :contentReference[oaicite:3]{index=3}
                        ok, frame = self.cap.read()

                if not ok:
                    time.sleep(0.05)
                    return

                # apply slider-like settings in video mode
                frame = self._apply_brightness_contrast(frame)

                # match BFMC sizes
                # main stream should be 2048x1080, serial should be 512x270
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
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

        if self.cap is not None:
            self.cap.release()
            self.cap = None

        if self.camera is not None:
            try:
                self.camera.stop()
            except Exception:
                pass
            self.camera = None

        super(threadCamera, self).stop()

    # =============================== CONFIG ==============================================
    def configs(self):
        if self._blocker.is_set():
            return

        # Brightness
        if self.brightnessSubscriber.is_data_in_pipe():
            message = self.brightnessSubscriber.receive()
            val = max(0.0, min(1.0, float(message)))

            if self.use_live_camera:
                if self.camera is not None:
                    self.camera.set_controls(
                        {"AeEnable": False, "AwbEnable": False, "Brightness": val}
                    )
            else:
                self._brightness = val

        # Contrast
        if self.contrastSubscriber.is_data_in_pipe():
            message = self.contrastSubscriber.receive()
            val = max(0.0, min(32.0, float(message)))

            if self.use_live_camera:
                if self.camera is not None:
                    self.camera.set_controls(
                        {"AeEnable": False, "AwbEnable": False, "Contrast": val}
                    )
            else:
                self._contrast = val

        threading.Timer(1, self.configs).start()
