# Copyright (c) 2019, Bosch Engineering Center Cluj and BFMC orginazers
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.

# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# To start the project: 
#
#       chmod +x setup.sh
#       ./setup.sh
#       cd src/dashboard/frontend
#       npm start
#       answer "y" to the popup
#       close the frontend (CTRL + C)
#       cd ../..
#
# ===================================== GENERAL IMPORTS ==================================

import sys
import time
import os
import psutil

import multiprocessing as mp
# Brain code keeps thread locks / open files inside Process objects -> needs fork (no pickling)
if "fork" in mp.get_all_start_methods():
    mp.set_start_method("fork", force = True)

# Pin to CPU cores 0–3
available_cores = list(range(psutil.cpu_count()))
psutil.Process(os.getpid()).cpu_affinity(available_cores)

sys.path.append(".")
from multiprocessing import Queue, Event
from src.utils.bigPrintMessages import BigPrint
from src.utils.outputWriters import QueueWriter, MultiWriter
import logging
import logging.handlers

logging.basicConfig(level=logging.INFO)

# ===================================== PROCESS IMPORTS ==================================

from src.gateway.processGateway import processGateway as ProcessGateway
from src.dashboard.processDashboard import processDashboard as ProcessDashboard
from src.hardware.camera.processCamera import processCamera as ProcessCamera
from src.hardware.serialhandler.processSerialHandler import processSerialHandler as ProcessSerialHandler
from src.data.Semaphores.processSemaphores import processSemaphores as ProcessSemaphores
from src.data.TrafficCommunication.processTrafficCommunication import processTrafficCommunication as ProcessTrafficCommunication
from src.utils.messages.messageHandlerSubscriber import messageHandlerSubscriber
from src.utils.messages.allMessages import StateChange
from src.statemachine.stateMachine import StateMachine
from src.statemachine.systemMode import SystemMode

# ------ New component imports starts here ------#
from src.perception.trafficSignDetection.processTrafficSignDetection import processTrafficSignDetection
from src.perception.trafficSignDetection.processTrafficSignDetection import processTrafficSignDetection
from src.perception.laneAssist.processLaneAssist import processLaneAssist


# ------ New component imports ends here ------#

# ===================================== SHUTDOWN PROCESS ====================================

def shutdown_process(process, timeout=1):
    """Helper function to gracefully shutdown a process."""
    process.join(timeout)
    if process.is_alive():
        print(f"The process {process} cannot normally stop, it's blocked somewhere! Terminate it!")
        process.terminate()  # force terminate if it won't stop
        process.join(timeout)  # give it a moment to terminate
        if process.is_alive():
            print(f"The process {process} is still alive after terminate, killing it!")
            process.kill()  # last resort
    print(f"The process {process} stopped")

# ===================================== PROCESS MANAGEMENT ==================================

def manage_process_life(process_class, process_instance, process_args, enabled, allProcesses):
    """Start or stop a process based on the enabled flag."""
    if enabled:
        if process_instance is None:
            process_instance = process_class(*process_args)
            allProcesses.append(process_instance)
            process_instance.start()
    else:
        if process_instance is not None and process_instance.is_alive():
            shutdown_process(process_instance)
            allProcesses.remove(process_instance)
            process_instance = None
    return process_instance 

# ======================================== SETTING UP ====================================
USE_LIVE_CAMERA = False   # True = picamera2, False = loop mp4
VIDEO_PATH = "raw_data/bfmc2020_online_2.mp4"

def _run():
    global logging
    print(BigPrint.PLEASE_WAIT.value)
    allProcesses = list()
    allEvents = list()

    queueList = {
        "Critical": Queue(),
        "Warning": Queue(),
        "General": Queue(),
        "Config": Queue(),
        "Log": Queue(),
    }
    logging = logging.getLogger()

    original_stdout = sys.stdout
    original_stderr = sys.stderr

    queue_writer = QueueWriter(queueList["Log"])
    sys.stdout = MultiWriter(original_stdout, queue_writer)
    sys.stderr = MultiWriter(original_stderr, queue_writer)

    # ===================================== INITIALIZE ==================================

    stateChangeSubscriber = messageHandlerSubscriber(queueList, StateChange, "lastOnly", True)
    StateMachine.initialize_shared_state(queueList)

    # Initializing gateway
    processGateway = ProcessGateway(queueList, logging)
    processGateway.start()

    # ===================================== INITIALIZE PROCESSES ==================================

    # Initializing dashboard
    dashboard_ready = Event()
    processDashboard = ProcessDashboard(queueList, logging, dashboard_ready, debugging = False)

    # Initializing camera
    camera_ready = Event()
    processCamera = ProcessCamera(
        queueList, logging, camera_ready, debugging=False,
        use_live_camera=USE_LIVE_CAMERA,
        video_path=VIDEO_PATH,
        loop_video=True,
        target_fps=20.0,
    )

    # Initializing semaphores
    semaphore_ready = Event()
    processSemaphore = ProcessSemaphores(queueList, logging, semaphore_ready, debugging = False)

    # Initializing GPS
    traffic_com_ready = Event()
    processTrafficCom = ProcessTrafficCommunication(queueList, logging, 3, traffic_com_ready, debugging = False)

    # Initializing serial connection NUCLEO - > PI
    serial_handler_ready = Event()
    processSerialHandler = ProcessSerialHandler(queueList, logging, serial_handler_ready, dashboard_ready, debugging = False)

    # Adding all processes to the list
    allProcesses.extend([processCamera, processSemaphore, processTrafficCom, processSerialHandler, processDashboard])
    allEvents.extend([camera_ready, semaphore_ready, traffic_com_ready, serial_handler_ready, dashboard_ready])

    # ------ New component initialize starts here ------#
    # Initializing traffic sign detection
    tsd_ready = Event()
    processTSD = processTrafficSignDetection(
        queueList,
        logging,
        tsd_ready,
        debugging=False,
        weights_path="traffic-sign-detection-model/traffic-sign-yolo26n-bfmc.pt",  # adjust to your repo paths
        input_message="mainCamera",  # or "serialCamera"
        target_fps=10.0,              # can be lower (0.5 etc.)
        conf=0.25,
        imgsz=640,
    )
    allProcesses.append(processTSD)
    allEvents.append(tsd_ready)


    # Initializing lane assist
    la_ready = Event()
    processLA = processLaneAssist(
        queueList,
        logging,
        la_ready,
        debugging=False,
        input_message="serialCamera",   # IMPORTANT: overlay matches dashboard live stream
        target_fps=5.0,
        camera_type="455",
        dashboard_size=(512, 270),
    )
    allProcesses.append(processLA)
    allEvents.append(la_ready)


    # ------ New component initialize ends here ------#

    # ===================================== START PROCESSES ==================================

    for process in allProcesses:
        process.daemon = True
        process.start()

    # ===================================== STAYING ALIVE ====================================

    blocker = Event()
    try:
        # wait for all events to be set
        for event in allEvents:
            event.wait()

        # apply starting mode
        StateMachine.initialize_starting_mode()

        time.sleep(10)
        print(BigPrint.C4_BOMB.value)
        print(BigPrint.PRESS_CTRL_C.value)

        while True:
            message = stateChangeSubscriber.receive()
            if message is not None:
                modeDictSemaphore = SystemMode[message].value["semaphore"]["process"]
                modeDictTrafficCom = SystemMode[message].value["traffic_com"]["process"]

                processSemaphore = manage_process_life(ProcessSemaphores, processSemaphore, [queueList, logging, semaphore_ready, False], modeDictSemaphore["enabled"], allProcesses)
                processTrafficCom = manage_process_life(ProcessTrafficCommunication, processTrafficCom, [queueList, logging, 3, traffic_com_ready, False], modeDictTrafficCom["enabled"], allProcesses)

            blocker.wait(0.1)

    except KeyboardInterrupt:
        print("\nCatching a KeyboardInterruption exception! Shutdown all processes.\n")

        for proc in reversed(allProcesses):
            proc.stop()
        processGateway.stop()

        # wait for all processes to finish before exiting
        for proc in reversed(allProcesses):
            shutdown_process(proc)
        shutdown_process(processGateway)

if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support() # safe no-op on Linux; required on Windows style start methods
    # Optional but recommended: match the older Linux behavior (what BFMC originally assumed)
    try:
        mp.set_start_method("fork")
    except RuntimeError:
        pass
    _run()
