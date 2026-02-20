# src/perception/laneAssist/processLaneAssist.py

from src.templates.workerprocess import WorkerProcess
from src.perception.laneAssist.threads.threadLaneAssist import threadLaneAssist


class processLaneAssist(WorkerProcess):
    """
    Runs Lane Assist (lane detection + lane keeping) in parallel with other BFMC processes.

    IMPORTANT:
    - We only output an RGBA PNG "mask" (base64) to be overlaid on top of the live serialCamera feed.
    - The dashboard video stays smooth (serialCamera at full FPS). This worker runs at lower FPS.
    """

    def __init__(
        self,
        queueList,
        logging,
        ready_event=None,
        debugging=False,
        input_message="serialCamera",
        target_fps=5.0,
        camera_type="455",
        dashboard_size=(512, 270),
    ):
        self._queueList = queueList
        self._logging = logging
        self._ready_event = ready_event
        self._debugging = debugging

        self._input_message = input_message
        self._target_fps = float(target_fps)
        self._camera_type = str(camera_type)
        self._dashboard_size = tuple(dashboard_size)

        super().__init__(queueList, ready_event, debugging)

    def _init_threads(self):
        self.threads.append(
            threadLaneAssist(
                queuesList=self._queueList,
                logger=self._logging,
                input_message=self._input_message,
                target_fps=self._target_fps,
                camera_type=self._camera_type,
                dashboard_size=self._dashboard_size,
            )
        )
