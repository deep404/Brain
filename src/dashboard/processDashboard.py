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

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "../../..")

import queue
import psutil
import json
import inspect
import eventlet
import os
import time

from flask import Flask, request
from flask_socketio import SocketIO
from flask_cors import CORS
from enum import Enum

from src.utils.messages.messageHandlerSubscriber import messageHandlerSubscriber
from src.utils.messages.messageHandlerSender import messageHandlerSender
from src.templates.workerprocess import WorkerProcess
from src.utils.messages.allMessages import Semaphores, CameraReset
from src.statemachine.stateMachine import StateMachine
from src.dashboard.components.calibration import Calibration
from src.dashboard.components.ip_manger import IpManager
from src.routePlanning.routePlanner import RoutePlanner
from src.utils.config import cfg

import src.utils.messages.allMessages as allMessages


class processDashboard(WorkerProcess):
    """This process handles the dashboard interactions, updating the UI based on the system's state.
    
    Args:
        queueList (dictionary of multiprocessing.queues.Queue): Dictionary of queues where the ID is the type of messages.
        logging (logging object): Made for debugging.
        debugging (bool): Enable debugging mode.
    """
    # ====================================== INIT ==========================================
    def __init__(self, queueList, logging, ready_event=None, debugging = False):

        self.running = True
        self.queueList = queueList
        self.logger = logging
        self.debugging = debugging
        
        # ip replacement
        IpManager.replace_ip_in_file()

        # state machine
        self.stateMachine = StateMachine.get_instance()

        # message handling
        self.messages = {}
        self.sendMessages = {}
        self.messagesAndVals = {}

        # hardware monitoring
        self.memoryUsage = 0
        self.cpuCoreUsage = 0
        self.cpuTemperature = 0


        # heartbeat
        self.heartbeat_last_sent = time.time()
        self.heartbeat_retries = 0
        self.heartbeat_max_retries = 3
        self.heartbeat_time_between_heartbeats = 20 # seconds
        self.heartbeat_time_between_retries = 5 # seconds # put a higher value if the connection is not stable (e.g. 5 seconds)
        self.heartbeat_received = False

        # session management
        self.sessionActive = False
        self.activeUser = None

        # serial connection state
        self.serialConnected = False

        # configuration
        self.table_state_file = self._get_table_state_path()

        # setup flask and socketio
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='eventlet')
        CORS(self.app, supports_credentials=True)

        # calibration
        self.calibration = Calibration(self.queueList, self.socketio)

        # route planning
        try:
            self.route_planner = RoutePlanner(graphml_path=cfg.GRAPHML_PATH)
            self._route_data = None
            self._current_route_idx = 0
            self._stop_line_counter = 0
            self._last_sign_route_idx = 0          # last position confirmed by a sign
            self._last_sign_label = ""              # last sign label used for jump
            self._sign_lookup = {}                  # sign_type -> [{route_idx, x, y, node}]
            self._stop_line_signs = {}              # stop_line_node -> [sign_types]
            self._instruction_lookup = {}           # stop_line_node -> instruction dict
            # 3-consecutive-frame TSD confirmation
            self._tsd_consec_label = ""
            self._tsd_consec_count = 0
            self._tsd_consec_match = None
            self._tsd_consec_idx = -1
            # AND logic: both stop line + TSD must confirm together
            self._pending_sl_confirmed = False
            self._pending_sl_target = None          # stop line dict {node, route_idx, x, y}
            self._pending_tsd_confirmed = False
            self._pending_tsd_label = ""            # normalized sign label that was confirmed
            self._dash_print("\033[1;97m[ Dashboard ] :\033[0m \033[1;92mINFO\033[0m - Route planner loaded successfully")
        except Exception as e:
            self.route_planner = None
            self._route_data = None
            self._dash_print(f"\033[1;97m[ Dashboard ] :\033[0m \033[1;91mERROR\033[0m - Route planner init failed: {e}")

        # initialize message handling
        self._initialize_messages()
        self._setup_websocket_handlers()
        self._start_background_tasks()

        super(processDashboard, self).__init__(self.queueList, ready_event)
    

    def _get_table_state_path(self):
        """Get the path for table state file."""
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_path, 'src', 'utils', 'table_state.json')

    def _dash_print(self, msg: str):
        """Print to terminal (MultiWriter routes it to both stdout AND Log queue.
        stream_console_logs picks it up from the queue and emits to the frontend console).
        """
        print(msg, flush=True)
    

    def _initialize_messages(self):
        """Initialize message handling systems."""
        self.get_name_and_vals()
        self.messagesAndVals.pop("mainCamera", None)
        self.messagesAndVals.pop("Semaphores", None)
        # Route planning messages are handled internally, not via gateway
        self.messagesAndVals.pop("RoutePlanData", None)
        self.messagesAndVals.pop("CarMapPosition", None)
        self.subscribe()
    

    def _setup_websocket_handlers(self):
        """Setup WebSocket event handlers."""
        self.socketio.on_event('message', self.handle_message)
        self.socketio.on_event('save', self.handle_save_table_state)
        self.socketio.on_event('load', self.handle_load_table_state)
    
    
    def _start_background_tasks(self):
        """Start background monitoring tasks."""
        psutil.cpu_percent(interval=1, percpu=False) # warm up

        eventlet.spawn(self.update_hardware_data)
        eventlet.spawn(self.send_continuous_messages)
        eventlet.spawn(self.send_hardware_data_to_frontend)
        eventlet.spawn(self.send_heartbeat)
        eventlet.spawn(self.stream_console_logs)

    def stream_console_logs(self):
        """Forward Log queue messages to the frontend console.
        
        NOTE: Do NOT print() here! sys.stdout is wrapped by MultiWriter which
        puts every print() back into this same Log queue → infinite loop.
        Terminal output is already handled by MultiWriter (stdout → real terminal).
        """
        log_queue = self.queueList.get("Log")
        if not log_queue:
            return

        while self.running:
            try:
                while not log_queue.empty():
                    msg = log_queue.get_nowait()
                    # Emit to frontend dashboard console only
                    self.socketio.emit('console_log', {'data': msg})
                    eventlet.sleep(0)
                
                eventlet.sleep(0.1)
            except queue.Empty:
                eventlet.sleep(0.1)
            except Exception as e:
                if self.debugging:
                    self.logger.error(f"Error streaming logs: {e}")
                eventlet.sleep(1)


    # ===================================== STOP ==========================================
    def stop(self):
        """Stop the dashboard process."""
        super(processDashboard, self).stop()
        self.running = False


    # ===================================== RUN ==========================================
    def run(self):
        """Apply the initializing method."""
        if self.ready_event:
            self.ready_event.set()

        self.socketio.run(self.app, host='0.0.0.0', port=5005)


    def subscribe(self):
        """Subscribe function. In this function we make all the required subscribe to process gateway."""
        for name, enum in self.messagesAndVals.items():
            if enum["owner"] != "Dashboard":
                subscriber = messageHandlerSubscriber(self.queueList, enum["enum"], "lastOnly", True)
                self.messages[name] = {"obj": subscriber}
            else:
                sender = messageHandlerSender(self.queueList, enum["enum"])
                self.sendMessages[str(name)] = {"obj": sender}

        subscriber = messageHandlerSubscriber(self.queueList, Semaphores, "fifo", True)
        self.messages["Semaphores"] = {"obj": subscriber}


    def get_name_and_vals(self):
        """Extract all message names and values for processing."""
        classes = inspect.getmembers(allMessages, inspect.isclass)
        for name, cls in classes:
            if name != "Enum" and issubclass(cls, Enum):
                self.messagesAndVals[name] = {"enum": cls, "owner": cls.Owner.value} # type: ignore


    def send_message_to_brain(self, dataName, dataDict):
        """Send messages to the backend."""
        if dataName in self.sendMessages:
            self.sendMessages[dataName]["obj"].send(dataDict.get("Value"))


    def handle_message(self, data):
        """Handle incoming WebSocket messages."""
        if self.debugging:
            self.logger.info("Received message: " + str(data))

        try:
            dataDict = json.loads(data)
            dataName = dataDict["Name"]
            socketId = request.sid

            if dataName == "SessionAccess":
                self.handle_single_user_session(socketId)
            elif self.sessionActive and self.activeUser != socketId:
                self._dash_print(f"\033[1;97m[ Dashboard ] :\033[0m \033[1;93mWARNING\033[0m - Message received from unauthorized user \033[94m{socketId}\033[0m")
                return

            if dataName == "Heartbeat":
                self.handle_heartbeat()
            elif dataName == "SessionEnd":
                self.handle_session_end(socketId)
            elif dataName == "DrivingMode":
                self.handle_driving_mode(dataDict)
            elif dataName == "Calibration":
                self.handle_calibration(dataDict, socketId)
            elif dataName == "GetCurrentSerialConnectionState":
                self.handle_get_current_serial_connection_state(socketId)
            elif dataName == "GetMapGraphData":
                self.handle_get_map_graph_data(socketId)
            elif dataName == "DashboardReset":
                self.handle_dashboard_reset(socketId)
            else:
                self.send_message_to_brain(dataName, dataDict)

            self.socketio.emit('response', {'data': 'Message received: ' + str(data)}, room=socketId) # type: ignore
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON message: {e}")
            self.socketio.emit('response', {'error': 'Invalid JSON format'}, room=socketId) # type: ignore


    def handle_heartbeat(self):
        """Handle heartbeat message."""
        self.heartbeat_retries = 0
        self.heartbeat_last_sent = time.time()
        self.heartbeat_received = True


    def handle_driving_mode(self, dataDict):
        """Handle driving mode change."""
        mode = dataDict.get('Value', '').lower()
        self.stateMachine.request_mode(f"dashboard_{mode}_button")

        # Trigger route planning for active driving modes
        if mode in ('manual', 'legacy', 'auto'):
            self._compute_and_emit_route()
        elif mode == 'stop':
            self._route_data = None
            self._current_route_idx = 0
            self._stop_line_counter = 0
            self._last_sign_route_idx = 0
            self._last_sign_label = ""
            self._tsd_consec_label = ""
            self._tsd_consec_count = 0
            self._tsd_consec_match = None
            self._tsd_consec_idx = -1
            self._pending_sl_confirmed = False
            self._pending_sl_target = None
            self._pending_tsd_confirmed = False
            self._pending_tsd_label = ""


    def handle_calibration(self, dataDict, socketId):
        """Handle calibration signals from frontend."""
        self.calibration.handle_calibration_signal(dataDict, socketId)


    def _compute_and_emit_route(self):
        """Compute route and emit to frontend via WebSocket."""
        if self.route_planner is None:
            return

        try:
            self._route_data = self.route_planner.compute_route(
                start_id=cfg.ROUTE_START,
                finish_id=cfg.ROUTE_FINISH,
                must_pass=cfg.ROUTE_CHECKPOINTS,
                visit_in_order=cfg.ROUTE_VISIT_IN_ORDER,
            )
            self._current_route_idx = 0
            self._stop_line_counter = 0
            self._last_sign_route_idx = 0
            self._last_sign_label = ""

            # Pre-build a lookup: sign_type -> list of {route_idx, x, y, node}
            # sorted by nearest_route_idx for efficient searching.
            self._sign_lookup = {}
            for s in self._route_data.get('signs_on_route', []):
                st = s['type']
                if st not in self._sign_lookup:
                    self._sign_lookup[st] = []
                self._sign_lookup[st].append(s)
            for st in self._sign_lookup:
                self._sign_lookup[st].sort(
                    key=lambda e: e.get('nearest_route_idx', e.get('route_idx', 999999))
                )

            # Build cross-reference: stop_line_node -> list of sign types
            # co-located at the same node (used for position validation).
            self._stop_line_signs = {}
            for s in self._route_data.get('signs_on_route', []):
                if s.get('is_stop_line', False):
                    node = s['node']
                    if node not in self._stop_line_signs:
                        self._stop_line_signs[node] = []
                    self._stop_line_signs[node].append(s['type'])

            # Build instruction lookup: stop_line_node -> instruction dict
            # so we can print the maneuver when the car reaches a stop line.
            self._instruction_lookup = {}
            for instr in self._route_data.get('instructions', []):
                sl = instr.get('stop_line')
                if sl is not None:
                    self._instruction_lookup[str(sl)] = instr

            # Reset TSD consecutive counters and AND-logic pending state
            self._tsd_consec_label = ""
            self._tsd_consec_count = 0
            self._tsd_consec_match = None
            self._tsd_consec_idx = -1
            self._pending_sl_confirmed = False
            self._pending_sl_target = None
            self._pending_tsd_confirmed = False
            self._pending_tsd_label = ""

            # Emit route data to frontend
            self.socketio.emit('RoutePlanData', {
                'route_coords': self._route_data['route_coords'],
                'stop_lines': self._route_data['stop_lines_on_route'],
                'signs': self._route_data['signs_on_route'],
                'instructions': self._route_data['instructions'],
            })

            # Emit initial car position (start node)
            if self._route_data['route_coords']:
                start_pos = self._route_data['route_coords'][0]
                self.socketio.emit('CarMapPosition', {
                    'x': start_pos[0],
                    'y': start_pos[1],
                    'route_idx': 0,
                    'total_nodes': len(self._route_data['route_nodes']),
                })

            self._dash_print(f"\033[1;97m[ Dashboard ] :\033[0m \033[1;92mINFO\033[0m - Route computed: {len(self._route_data['route_nodes'])} nodes, {len(self._route_data['stop_lines_on_route'])} stop lines, {len(self._route_data['signs_on_route'])} signs")
        except Exception as e:
            self._dash_print(f"\033[1;97m[ Dashboard ] :\033[0m \033[1;91mERROR\033[0m - Route computation failed: {e}")


    # ─── YOLO label → SIGNS key normalization ───────────────────────────
    # Actual YOLO model class names:
    # ['car', 'crossed_highway_sign', 'green_light', 'highway_sign',
    #  'no_entry_sign', 'one_way_road_sign', 'parking_sign', 'pedestrian',
    #  'pedestrian_sign', 'priority_sign', 'red_light', 'road_blocked_barrier',
    #  'roadblock', 'roundabout_sign', 'signs', 'stop_sign', 'yellow_light']
    _LABEL_ALIASES = {
        # Traffic lights (any colour → traffic_light)
        "green_light":          "traffic_light",
        "red_light":            "traffic_light",
        "yellow_light":         "traffic_light",
        "traffic light":        "traffic_light",
        "trafficlight":         "traffic_light",
        "traffic_light":        "traffic_light",
        "traffic light green":  "traffic_light",
        "traffic light red":    "traffic_light",
        "traffic light yellow": "traffic_light",
        "traffic_light_green":  "traffic_light",
        "traffic_light_red":    "traffic_light",
        "traffic_light_yellow": "traffic_light",
        # Stop
        "stop_sign":      "stop",
        "stopsign":       "stop",
        "stop sign":      "stop",
        "stop":           "stop",
        # Priority
        "priority_sign":  "priority",
        "priority":       "priority",
        "priority road":  "priority",
        # Highway
        "highway_sign":          "highway_entry",
        "highway entry":         "highway_entry",
        "highway_entry":         "highway_entry",
        "crossed_highway_sign":  "highway_exit",
        "highway exit":          "highway_exit",
        "highway_exit":          "highway_exit",
        # Roundabout
        "roundabout_sign": "roundabout",
        "roundabout":      "roundabout",
        # Crosswalk / pedestrian
        "pedestrian":      "crosswalk",
        "pedestrian_sign": "crosswalk",
        "crosswalk":       "crosswalk",
        # No entry
        "no_entry_sign":  "no_entry",
        "no entry":       "no_entry",
        "no_entry":       "no_entry",
        "noentry":        "no_entry",
        # One way
        "one_way_road_sign": "one_way",
        "one way":           "one_way",
        "one_way":           "one_way",
        "oneway":            "one_way",
        # Parking
        "parking_sign":   "parking",
        "parking":        "parking",
    }

    @classmethod
    def _normalize_label(cls, raw: str) -> str:
        """Map a YOLO detection label to the canonical SIGNS key."""
        key = raw.strip().lower()
        # exact alias lookup
        if key in cls._LABEL_ALIASES:
            return cls._LABEL_ALIASES[key]
        # fallback: replace spaces / hyphens with underscores
        key = key.replace(" ", "_").replace("-", "_")
        if key in cls._LABEL_ALIASES:
            return cls._LABEL_ALIASES[key]
        # catch-all: any label containing "light" → traffic_light
        if "light" in key:
            return "traffic_light"
        return key

    # ─── helpers: position tracking ─────────────────────────────────────

    def _advance_position(self, new_route_idx: int, x: float, y: float,
                          source: str, extra: dict = None) -> bool:
        """
        Advance the car position on the route (never backwards).
        Emits CarMapPosition to the frontend.
        Returns True if position was actually advanced.
        """
        if new_route_idx <= self._current_route_idx:
            return False  # prevent backward jumps

        self._current_route_idx = new_route_idx
        payload = {
            'x': x,
            'y': y,
            'route_idx': self._current_route_idx,
            'total_nodes': len(self._route_data['route_nodes']),
            'source': source,
        }
        if extra:
            payload.update(extra)
        self.socketio.emit('CarMapPosition', payload)
        return True

    def _get_next_target_stop_line(self):
        """Return the next stop line dict ahead of current position, or None."""
        if self._route_data is None:
            return None
        for sl in self._route_data.get('stop_lines_on_route', []):
            if sl.get('route_idx', -1) > self._current_route_idx:
                return sl
        return None

    def _clear_pending(self):
        """Clear both pending flags after an intersection is confirmed or rejected."""
        self._pending_sl_confirmed = False
        self._pending_sl_target = None
        self._pending_tsd_confirmed = False
        self._pending_tsd_label = ""

    def _try_confirm_intersection(self):
        """
        Check if BOTH stop-line AND TSD are confirmed for the same target.
        If so, advance position and print a detailed passage log.
        If the target has no expected signs, stop-line alone is sufficient.
        """
        target = self._pending_sl_target
        if target is None:
            return

        instr = self._instruction_lookup.get(str(target['node']))
        expected = instr.get('signs_at_stop', []) if instr else []

        # --- No expected signs → allow stop-line-only confirmation -----------
        if not expected and self._pending_sl_confirmed:
            advanced = self._advance_position(
                target['route_idx'], target['x'], target['y'],
                source='stop_line',
                extra={
                    'at_stop_line': True,
                    'stop_line_node': target['node'],
                    'colocated_signs': [],
                },
            )
            if advanced:
                self._stop_line_counter += 1
                itype = instr['type'].upper() if instr else 'STOP LINE'
                action = instr.get('action', '?') if instr else '?'
                self._dash_print(
                    f"\033[1;97m[ Dashboard ] :\033[0m \033[1;92mINFO\033[0m - "
                    f"#{self._stop_line_counter} {itype} at node {target['node']} was passed "
                    f"(stop line confirmed, no signs expected). Action: {action}"
                )
            self._clear_pending()
            return

        # --- AND logic: both must be confirmed --------------------------------
        if self._pending_sl_confirmed and self._pending_tsd_confirmed:
            advanced = self._advance_position(
                target['route_idx'], target['x'], target['y'],
                source='stop_line+tsd',
                extra={
                    'at_stop_line': True,
                    'stop_line_node': target['node'],
                    'colocated_signs': expected,
                    'confirmed_sign': self._pending_tsd_label,
                },
            )
            if advanced:
                self._stop_line_counter += 1
                itype = instr['type'].upper() if instr else 'STOP LINE'
                action = instr.get('action', '?') if instr else '?'
                sign_display = self._pending_tsd_label.replace('_', ' ').upper()
                self._dash_print(
                    f"\033[1;97m[ Dashboard ] :\033[0m \033[1;92mINFO\033[0m - "
                    f"#{self._stop_line_counter} {itype} at node {target['node']} was passed "
                    f"because STOP LINE at node {target['node']} AND {sign_display} "
                    f"were both confirmed. Action: {action}"
                )
            self._clear_pending()
            return

    def _handle_stop_line_event(self, event):
        """
        Record that a stop line has been confirmed (after LA 3-frame check).
        Does NOT advance position by itself — waits for TSD confirmation
        via _try_confirm_intersection() (AND logic).
        """
        if self._route_data is None:
            return

        target = self._get_next_target_stop_line()
        if target is None:
            return  # no stop line ahead

        # If we already have a pending confirmation for a DIFFERENT target, clear it
        if (self._pending_sl_target is not None and
                self._pending_sl_target['node'] != target['node']):
            self._clear_pending()

        self._pending_sl_confirmed = True
        self._pending_sl_target = target

        # Look up expected signs from the instruction
        instr = self._instruction_lookup.get(str(target['node']))
        expected = instr.get('signs_at_stop', []) if instr else []

        if expected:
            sign_labels = ', '.join(s.replace('_', ' ').upper() for s in expected)
            self._dash_print(
                f"\033[1;97m[ Dashboard ] :\033[0m \033[1;96mINFO\033[0m - "
                f"Stop line at node {target['node']} confirmed. "
                f"Waiting for TSD ({sign_labels})..."
            )
        else:
            self._dash_print(
                f"\033[1;97m[ Dashboard ] :\033[0m \033[1;96mINFO\033[0m - "
                f"Stop line at node {target['node']} confirmed (no signs expected)."
            )

        self._try_confirm_intersection()

    def _handle_traffic_sign_event(self, event):
        """
        Use detected traffic signs with ROI filtering to confirm position.
        Requires 3 consecutive frames with the SAME matching sign before
        considering it confirmed (prevents false positives).

        Does NOT advance position directly — sets the TSD pending flag and
        delegates to _try_confirm_intersection() (AND logic with stop line).

        Pipeline:
        1. Normalize the YOLO label to the canonical SIGNS key.
        2. For each detection compute bbox_area / frame_area (area ratio).
        3. Keep only detections with ratio >= cfg.SIGN_ROI_MIN_RATIO.
        4. Match the label against expected signs for the next target stop line.
        5. If the same match persists for 3 consecutive frames, set pending TSD flag.
        """
        if self._route_data is None:
            return

        detections = event.get('detections', [])
        if not detections:
            self._tsd_consec_count = 0
            self._tsd_consec_label = ""
            return

        frame_w = event.get('frame_w', 1)
        frame_h = event.get('frame_h', 1)
        frame_area = max(frame_w * frame_h, 1)

        min_conf = cfg.SIGN_TRACK_CONFIDENCE
        min_ratio = cfg.SIGN_ROI_MIN_RATIO

        # Determine what signs we expect at the next target
        target = self._pending_sl_target or self._get_next_target_stop_line()
        if target is None:
            return
        instr = self._instruction_lookup.get(str(target['node']))
        expected_signs = instr.get('signs_at_stop', []) if instr else []
        if not expected_signs:
            return  # no signs expected → TSD not needed for this target

        best_label = ""
        best_conf = 0.0

        for det in detections:
            conf = det.get('confidence', 0)
            if conf < min_conf:
                continue

            raw_label = det.get('label', '')
            label = self._normalize_label(raw_label)

            # ROI filter: bbox area ratio
            bbox = det.get('bbox')
            if bbox:
                x1, y1, x2, y2 = bbox
                bbox_area = abs((x2 - x1) * (y2 - y1))
                ratio = bbox_area / frame_area
                if ratio < min_ratio:
                    continue

            # Only accept detections that match expected signs at the next target
            if label in expected_signs and conf > best_conf:
                best_label = label
                best_conf = conf

        # ── 3-consecutive-frame confirmation ─────────────────────────────
        if best_label:
            if best_label == self._tsd_consec_label:
                self._tsd_consec_count += 1
            else:
                self._tsd_consec_label = best_label
                self._tsd_consec_count = 1

            if self._tsd_consec_count >= 3:
                self._pending_tsd_confirmed = True
                self._pending_tsd_label = best_label
                # Ensure the pending target is set even if stop line hasn't fired yet
                if self._pending_sl_target is None:
                    self._pending_sl_target = target

                self._dash_print(
                    f"\033[1;97m[ Dashboard ] :\033[0m \033[1;96mINFO\033[0m - "
                    f"TSD confirmed: {best_label.replace('_', ' ').upper()} "
                    f"(3 frames). "
                    f"{'Stop line already confirmed.' if self._pending_sl_confirmed else 'Waiting for stop line...'}"
                )
                self._tsd_consec_count = 0
                self._tsd_consec_label = ""
                self._try_confirm_intersection()
        else:
            self._tsd_consec_count = 0
            self._tsd_consec_label = ""

        # Always forward high-confidence near-sign detections to frontend
        for det in detections:
            if det.get('confidence', 0) >= min_conf:
                self.socketio.emit('TrafficSignDetected', {
                    'label': self._normalize_label(det.get('label', '')),
                    'confidence': round(det['confidence'], 2),
                })


    def handle_get_current_serial_connection_state(self, socketId):
        """Handle getting the current serial connection state."""
        self.socketio.emit('current_serial_connection_state', {'data': self.serialConnected}, room=socketId)


    def handle_get_map_graph_data(self, socketId):
        """Send the full map graph data (nodes, edges, signs, stop lines) to a client."""
        if self.route_planner is None:
            self.socketio.emit('MapGraphData', {'error': 'Route planner not initialised'}, room=socketId)
            return

        try:
            graph_data = self.route_planner.get_graph_data()
            self.socketio.emit('MapGraphData', graph_data, room=socketId)
            self._dash_print(f"\033[1;97m[ Dashboard ] :\033[0m \033[1;92mINFO\033[0m - Sent map graph data to \033[94m{socketId}\033[0m ({len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges)")
        except Exception as e:
            self._dash_print(f"\033[1;97m[ Dashboard ] :\033[0m \033[1;91mERROR\033[0m - Failed to send graph data: {e}")
            self.socketio.emit('MapGraphData', {'error': str(e)}, room=socketId)


    def handle_dashboard_reset(self, socketId):
        """
        Full dashboard reset:
        - Reset route tracking state
        - Send CameraReset to rewind video to frame 0
        - Emit DashboardReset to frontend (clear console, map, overlays)
        """
        # 1. Reset route tracking state
        self._route_data = None
        self._current_route_idx = 0
        self._stop_line_counter = 0
        self._last_sign_route_idx = 0
        self._last_sign_label = ""
        self._sign_lookup = {}
        self._stop_line_signs = {}
        self._instruction_lookup = {}
        self._tsd_consec_label = ""
        self._tsd_consec_count = 0
        self._tsd_consec_match = None
        self._tsd_consec_idx = -1
        self._pending_sl_confirmed = False
        self._pending_sl_target = None
        self._pending_tsd_confirmed = False
        self._pending_tsd_label = ""

        # 2. Send CameraReset message to camera thread (seek video to frame 0)
        try:
            camera_reset_sender = messageHandlerSender(self.queuesList, CameraReset)
            camera_reset_sender.send({"reset": True})
        except Exception as e:
            self._dash_print(f"\033[1;97m[ Dashboard ] :\033[0m \033[1;93mWARNING\033[0m - CameraReset send failed: {e}")

        # 3. Emit DashboardReset to frontend
        self.socketio.emit('DashboardReset', {'reset': True}, room=socketId)

        self._dash_print(
            f"\033[1;97m[ Dashboard ] :\033[0m \033[1;92mINFO\033[0m - "
            f"Dashboard reset triggered by \033[94m{socketId}\033[0m"
        )


    def handle_single_user_session(self, socketId):
        """Handle session access for a single user."""
        if not self.sessionActive:
            self.sessionActive = True
            self.activeUser = socketId
            self._dash_print(f"\033[1;97m[ Dashboard ] :\033[0m \033[1;92mINFO\033[0m - Session access granted to \033[94m{socketId}\033[0m")
            self.socketio.emit('session_access', {'data': True}, room=socketId)
            self.send_message_to_brain("RequestSteerLimits", {"Value": True})
        elif self.activeUser == socketId:
            self.socketio.emit('session_access', {'data': True}, room=socketId)
            self.send_message_to_brain("RequestSteerLimits", {"Value": True})
        else:
            self._dash_print(f"\033[1;97m[ Dashboard ] :\033[0m \033[1;92mINFO\033[0m - Session access denied to \033[94m{socketId}\033[0m")
            self.socketio.emit('session_access', {'data': False}, room=socketId)


    def handle_session_end(self, socketId):
        """Handle session end for the single user."""
        if self.sessionActive and self.activeUser == socketId:
            self.sessionActive = False
            self.activeUser = None


    def handle_save_table_state(self, data):
        """Handle saving the table state to a JSON file."""
        if self.debugging:
            self.logger.info("Received save message: " + data)

        try:
            dataDict = json.loads(data)
            os.makedirs(os.path.dirname(self.table_state_file), exist_ok=True)
            
            with open(self.table_state_file, 'w') as json_file:
                json.dump(dataDict, json_file, indent=4)
                
            self.socketio.emit('response', {'data': 'Table state saved successfully'})
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON for save: {e}")
            self.socketio.emit('response', {'error': 'Invalid JSON format'})
        except OSError as e:
            self.logger.error(f"Failed to save table state: {e}")
            self.socketio.emit('response', {'error': 'Failed to save table state'})


    def handle_load_table_state(self, data):
        """Handle loading the table state from a JSON file."""
        try:
            with open(self.table_state_file, 'r') as json_file:
                dataDict = json.load(json_file)
            self.socketio.emit('loadBack', {'data': dataDict})
        except FileNotFoundError:
            self.socketio.emit('response', {'error': 'File not found. Please save the table state first.'})
        except json.JSONDecodeError:
            self.socketio.emit('response', {'error': 'Failed to parse JSON data from the file.'})
        except OSError as e:
            self.logger.error(f"Failed to load table state: {e}")
            self.socketio.emit('response', {'error': 'Failed to load table state'})


    def update_hardware_data(self):
        """Monitor and update hardware metrics periodically."""
        self.cpuCoreUsage = psutil.cpu_percent(interval=None, percpu=False)
        self.memoryUsage = psutil.virtual_memory().percent
        temps = psutil.sensors_temperatures(fahrenheit=False) or {}
        entry = None
        for key in ("cpu_thermal", "coretemp", "k10temp", "acpitz"):
            if key in temps and temps[key]:
                entry = temps[key][0]
                break
        # fallback: take the first available sensor entry if any
        if entry is None:
            for entries in temps.values():
                if entries:
                    entry = entries[0]
                    break
        # If WSL / OS exposes no sensors, keep a safe default
        self.cpuTemperature = round(entry.current) if entry is not None else 0

        eventlet.spawn_after(1, self.update_hardware_data)


    def send_heartbeat(self):
        """Send a heartbeat message to the frontend."""
        if not self.running:
            return

        if not self.heartbeat_received and self.sessionActive:
            self.heartbeat_retries += 1
            if self.heartbeat_retries < self.heartbeat_max_retries:
                self.socketio.emit('heartbeat', {'data': 'Heartbeat'})
            else:
                self._dash_print(f"\033[1;97m[ Dashboard ] :\033[0m \033[1;93mWARNING\033[0m - Connection lost with peer \033[94m{self.activeUser}\033[0m")
                self.socketio.emit('heartbeat_disconnect', {'data': 'Heartbeat timeout'})
                self.sessionActive = False
                self.activeUser = None
                self.heartbeat_retries = 0

            eventlet.spawn_after(self.heartbeat_time_between_retries, self.send_heartbeat)
        else:
            self.heartbeat_received = False
            eventlet.spawn_after(self.heartbeat_time_between_heartbeats, self.send_heartbeat)


    def send_continuous_messages(self):
        """Process and send subscriber messages to the frontend."""
        if not self.running:
            return

        for msg, subscriber in self.messages.items():
            resp = subscriber["obj"].receive()
            if resp is not None:
                if msg == "SerialConnectionState":
                    self.serialConnected = resp

                # Handle stop line events for position tracking
                if msg == "StopLineEvent" and isinstance(resp, dict) and resp.get("detected"):
                    self._handle_stop_line_event(resp)
                    # Don't emit raw stop line events to frontend
                elif msg == "TrafficSignEvent" and isinstance(resp, dict):
                    self._handle_traffic_sign_event(resp)
                    # Don't emit raw sign events to frontend
                else:
                    self.socketio.emit(msg, {"value": resp})

                if self.debugging:
                    self.logger.info(f"{msg}: {resp}")

        eventlet.spawn_after(0.033, self.send_continuous_messages)  # ~30fps polling


    def send_hardware_data_to_frontend(self):
        """Send hardware monitoring data to the frontend."""
        if not self.running:
            return

        self.socketio.emit('memory_channel', {'data': self.memoryUsage})
        self.socketio.emit('cpu_channel', {
            'data': {
                'usage': self.cpuCoreUsage,
                'temp': self.cpuTemperature
            }
        })

        eventlet.spawn_after(1.0, self.send_hardware_data_to_frontend)
