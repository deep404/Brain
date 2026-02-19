# src/perception/trafficSignDetection/processTrafficSignDetection.py

from src.templates.workerprocess import WorkerProcess
from src.perception.trafficSignDetection.threads.threadTrafficSignDetection import threadTrafficSignDetection


class processTrafficSignDetection(WorkerProcess):
    """
    Runs YOLO traffic-sign inference in parallel with other BFMC processes.

    Outputs:
      - Terminal logs (via Log queue) with detections
      - TrafficSignMask: transparent PNG mask (base64) to overlay on the live dashboard stream
    """

    def __init__(
        self,
        queueList,
        logging,
        ready_event=None,
        debugging=False,
        weights_path=None,
        input_message="mainCamera",   # or "serialCamera"
        target_fps=3.0,               # recommended 2 3 for inference
        conf=0.25,
        imgsz=640,
        dashboard_size=(512, 270),    # should match serialCamera display size
    ):
        self.queuesList = queueList
        self.logger = logging
        self.debugging = debugging

        self.weights_path = weights_path
        self.input_message = input_message
        self.target_fps = float(target_fps)
        self.conf = float(conf)
        self.imgsz = int(imgsz)
        self.dashboard_size = dashboard_size

        super().__init__(self.queuesList, ready_event)

    def _init_threads(self):
        th = threadTrafficSignDetection(
            self.queuesList,
            self.logger,
            weights_path=self.weights_path,
            input_message=self.input_message,
            target_fps=self.target_fps,
            conf=self.conf,
            imgsz=self.imgsz,
            dashboard_size=self.dashboard_size,
        )
        self.threads.append(th)
