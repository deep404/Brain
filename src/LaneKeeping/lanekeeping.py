from src.LaneKeeping.lane_config import load_lane_config

import configparser
import math
import traceback

import cv2
import numpy as np
from scipy.stats import norm


class LaneKeeping:
    """
    This class implements the lane keeping algorithm by calculating steering angles from the detected lines.

    Attributes:
        log (logging object):
            Logic logger, child of root logger
        config (configparser object):
            Open configuration file of the whole project
        width (integer):
            The width of the input image
        height (integer):
            The height of the input image
        angle (float):
            Steering angle
        last_angle (float):
            Previous steering angle
        steer_value_list (list):
            Store last k steering values
        median_constant (integer):
            Num of the last steering angles to be saved
        print_desire_lane (bool):
            Visualization of the desired lane
        bottom_width (integer):
            Bottom width difference of left and right lane div 2
        top_width (integer)
            Top width difference of left and right lane div 2
        slices (integer):
            Number of slices from the lane detection
        bottom_row_index (integer):
            Height of the first histogram
        top_row_index (integer) :
            Height of the last histogram
    """

    def __init__(self, width, height, logger, camera):

        self.width = width
        self.height = height
        self.log = logger

        self.angle = 0.0
        self.last_angle = 0.0

        self.config = load_lane_config()

        # Rolling average parameters
        self.steer_value_list = list()
        self.median_constant = int(self.config["LANE_KEEPING"].get("median_constant"))

        self.print_desire_lane = self.config["LANE_KEEPING"].getboolean("print_desire_lane")

        self.max_coef_of_sharp_turn = float(self.config["LANE_KEEPING"].get("max_coef_of_sharp_turn"))
        self.min_coef_of_sharp_turn = float(self.config["LANE_KEEPING"].get("min_coef_of_sharp_turn"))
        self.sharp_turning_factor = float(self.config["LANE_KEEPING"].get("sharp_turning_factor"))
        self.max_lk_steer = int(self.config["PARAMS"].get("max_lk_steer"))

        self.slices = int(self.config["LANE_DETECT"].get("slices"))
        self.bottom_offset = int(self.config["LANE_DETECT"].get("bottom_offset"))

        if camera == "455":
            self.choose_455()
        elif camera == "405":
            self.choose_405()

        self.prev_mean_right = 0
        self.prev_mean_left = 0

        self.turn_left = False
        self.turn_right = False

        self.change_lane_stage_1 = True
        self.change_lane_stage_2 = False
        self.count = 0

        self.get_error_weights = range(0, self.real_slices)

        mu = float(self.config["LANE_KEEPING"].get("mu"))
        sigma = float(self.config["LANE_KEEPING"].get("sigma"))

        self.max_smoothing_iterations = int(self.config["CHANGE_LANE"].get("max_smoothing_iterations"))
        self.change_lane_threshold = int(self.config["CHANGE_LANE"].get("threshold"))
        self.change_lane_count = int(self.config["CHANGE_LANE"].get("count"))
        self.change_lane_mid = {
            "static": float(self.config["CHANGE_LANE"].get("dif_from_mid_multiplier_static")),
            "dynamic": float(self.config["CHANGE_LANE"].get("dif_from_mid_multiplier_dynamic")),
        }
        self.smoothing_iterations = self.max_smoothing_iterations
        self.smoothing_step = 0
        self.min_smoothing_factor = float(self.config["LANE_KEEPING"].get("min_smoothing_factor"))
        self.max_smoothing_factor = float(self.config["LANE_KEEPING"].get("max_smoothing_factor"))
        self.smoothing_factor = np.linspace(0.1, 1, self.smoothing_iterations)

        self.roundabout = False

        self.max_lane_changing_tries = {
            "static": int(self.config["CHANGE_LANE"].get("max_lane_changing_tries_static")),
            "dynamic": int(self.config["CHANGE_LANE"].get("max_lane_changing_tries_dynamic")),
        }

        # Calculate the survival function using the complementary cumulative distribution function (ccdf)
        cdf = norm.cdf(self.plot_y_norm, mu, sigma)
        sf = 1 - cdf
        self.sf = (sf - sf[-1]) / (sf[0] - sf[-1])

    # ------------------------------------------------------------------------------#

    def choose_405(self):
        self.bottom_perc = float(self.config["LANE_DETECT"].get("bottom_perc_405"))
        self.peaks_min_width = int(self.config["LANE_DETECT"].get("peaks_min_width_405"))
        self.peaks_max_width = int(self.config["LANE_DETECT"].get("peaks_max_width_405"))

        # FIX
        self.bottom_row_index = (self.height - 1) - self.bottom_offset
        self.bottom_row_index = max(0, min(self.height - 1, self.bottom_row_index))

        end = int((1 - self.bottom_perc) * self.height)
        end = max(0, min(self.height - 1, end))

        step_mag = max(1, int(self.height * self.bottom_perc / self.slices))
        self.step = -step_mag

        self.real_slices = int((end - self.bottom_row_index) // self.step)
        self.real_slices = max(1, self.real_slices)

        self.top_row_index = self.bottom_row_index + self.real_slices * self.step
        self.top_row_index = max(0, min(self.height - 1, self.top_row_index))

        # NOTE: linspace includes endpoints by default :contentReference[oaicite:1]{index=1}
        self.plot_y = np.linspace(self.bottom_row_index, self.top_row_index, self.real_slices)
        self.plot_y_norm = np.linspace(0, 1, self.real_slices)

        self.get_error_weights = range(0, self.real_slices)

        self.bottom_width = int(self.config["LANE_KEEPING"].get("bottom_width_405"))
        self.top_width = int(self.config["LANE_KEEPING"].get("top_width_405"))


    def choose_455(self):
        self.bottom_perc = float(self.config["LANE_DETECT"].get("bottom_perc_455"))
        self.peaks_min_width = int(self.config["LANE_DETECT"].get("peaks_min_width_455"))
        self.peaks_max_width = int(self.config["LANE_DETECT"].get("peaks_max_width_455"))

        # FIX
        self.bottom_row_index = (self.height - 1) - self.bottom_offset
        self.bottom_row_index = max(0, min(self.height - 1, self.bottom_row_index))

        end = int((1 - self.bottom_perc) * self.height)
        end = max(0, min(self.height - 1, end))

        step_mag = max(1, int(self.height * self.bottom_perc / self.slices))
        self.step = -step_mag

        self.real_slices = int((end - self.bottom_row_index) // self.step)
        self.real_slices = max(1, self.real_slices)

        self.top_row_index = self.bottom_row_index + self.real_slices * self.step
        self.top_row_index = max(0, min(self.height - 1, self.top_row_index))

        self.plot_y = np.linspace(self.bottom_row_index, self.top_row_index, self.real_slices)
        self.plot_y_norm = np.linspace(0, 1, self.real_slices)
        self.get_error_weights = range(0, self.real_slices)

        self.bottom_width = int(self.config["LANE_KEEPING"].get("bottom_width_455"))
        self.top_width = int(self.config["LANE_KEEPING"].get("top_width_455"))


    # ------------------------------------------------------------------------------#

    def desired_lane(self, left_fit, right_fit, polynomial=2):
        """Caclulates multiple points on the desired lane that the car should follow.

        Parameters
        ----------
        left_fit : array
            The left polyfit
        right_fit : array
            The right polyfit

        Returns
        -------
        array
            The desired lane points
        """

        if left_fit is not None and right_fit is not None:
            # BOTH LANES (Desired lane is the middle lane of those lane)

            desire_lane = (
                (left_fit[0] + right_fit[0]) / 2 * self.plot_y**2
                + (left_fit[1] + right_fit[1]) / 2 * self.plot_y
                + (left_fit[2] + right_fit[2]) / 2
            )

        elif left_fit is None:
            # Create the desired lane depending only on the right lane , the bottom_width and top_width params
            desire_lane = np.ndarray([])

            top_width = self.top_width

            # right_fit = a,b,c where y = ax^2 +bx + c
            # if a < 0 => left turn => turn sharply => change top_width
            if right_fit[0] < -(self.max_coef_of_sharp_turn):
                top_width = int(top_width * self.sharp_turning_factor)
            elif right_fit[0] < -(self.min_coef_of_sharp_turn):
                add = (-right_fit[0] - self.min_coef_of_sharp_turn) / (
                    self.max_coef_of_sharp_turn - self.min_coef_of_sharp_turn
                )
                top_width = int(top_width * (1 + add * (self.sharp_turning_factor - 1)))

            cnt = 0
            for i in self.plot_y:

                fix = self.bottom_width - ((self.bottom_width - top_width) * self.plot_y_norm[cnt])
                cnt += 1

                # desire lane is on the left of the right_lane so we need to subtract the fix
                value = (right_fit[0] * i**2 + right_fit[1] * i + right_fit[2]) - fix

                desire_lane = np.append(desire_lane, value)

            desire_lane = desire_lane[1:]

        elif right_fit is None:
            # Create the desired lane depending only on the left lane , the bottom_width and top_width params
            desire_lane = np.ndarray([])

            top_width = self.top_width

            # left_fit = a,b,c where y = ax^2 +bx + c
            # if a > 0 => right turn => turn sharply => change top_width
            if left_fit[0] > self.max_coef_of_sharp_turn:
                top_width = int(top_width * self.sharp_turning_factor)
            elif left_fit[0] > self.min_coef_of_sharp_turn:
                add = (left_fit[0] - self.min_coef_of_sharp_turn) / (
                    self.max_coef_of_sharp_turn - self.min_coef_of_sharp_turn
                )
                top_width = int(top_width * (1 + add * (self.sharp_turning_factor - 1)))

            cnt = 0
            for i in self.plot_y:

                fix = self.bottom_width - ((self.bottom_width - top_width) * self.plot_y_norm[cnt])
                cnt += 1

                value = (left_fit[0] * i**2 + left_fit[1] * i + left_fit[2]) + fix

                desire_lane = np.append(desire_lane, value)

            desire_lane = desire_lane[1:]

        if (self.turn_left or self.turn_right) and self.change_lane_stage_1:
            smooth_lane = ((self.width // 2) - desire_lane) * (self.sf)
            desire_lane += smooth_lane
        elif self.change_lane_stage_2:
            dif_from_mid = (self.width // 2 - desire_lane[0]) * self.change_lane_mid[self.overtake_type]
            desire_lane += dif_from_mid

        return desire_lane.astype(np.int32)

    def visualize_desire_lane(self, frame, plot_x, bgr_colour=(50, 205, 50)):
        """Visualization of the desired lane with a neon glow effect.

        Parameters
        ----------
        frame : array
            input image
        plot_x : array
            having the x values of the points of the desired lane.
        bgr_colour : tuple
            An optional parameter representing the color of the desire lane.
        """

        if frame is not None:

            plot_y = self.plot_y.astype(np.int32)

            points = []
            for i in range(len(plot_y)):
                points.append([int(plot_x[i]), int(plot_y[i])])
            pts = np.array(points, np.int32)

            # Outer glow
            cv2.polylines(frame, [pts], False, (30, 120, 30), 7, cv2.LINE_AA)
            # Mid glow
            cv2.polylines(frame, [pts], False, bgr_colour, 3, cv2.LINE_AA)
            # Bright core
            bright = tuple(min(255, int(ch * 1.4)) for ch in bgr_colour)
            cv2.polylines(frame, [pts], False, bright, 1, cv2.LINE_AA)

    def get_error(self, desired):
        """Calculates the error between the setpoint (desired lane) and the measured lane position (the actual lane position of the vehicle)

        Parameters
        ----------
        desired : array
            The points of the desired lane

        Returns
        -------
        float
            calculated error
        """

        if len(desired) != 0:
            weighted_mean = np.average(desired, weights=[*self.get_error_weights])

            # The actual lane is the middle lane.
            center = int(self.width / 2.0)
            error = weighted_mean - center

            return error
        return 0

    # ------------------------------------------------------------------------------#
    def change_lane_maneuver(self, lanes_detection, direction, overtake_type, smoothing_iterations=None):

        destination = {"right": 1, "left": -1}
        self.overtake_type = overtake_type

        if smoothing_iterations and smoothing_iterations < self.max_smoothing_iterations:
            self.smoothing_iterations = smoothing_iterations
            self.smoothing_factor = np.linspace(
                self.min_smoothing_factor, self.max_smoothing_factor, self.smoothing_iterations
            )

        self.angle, frame = self.change_lane(lanes_detection, destination=destination[direction])

        # Lane change HUD indicator
        arrow = "<<" if direction == "left" else ">>"
        text = f"{arrow} LANE CHANGE {direction.upper()} {arrow}"
        bg_color = (140, 80, 0) if direction == "left" else (0, 80, 140)
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cx = self.width // 2
        cy = int(0.08 * self.height)
        pad_x, pad_y = 14, 8
        overlay = frame.copy()
        cv2.rectangle(overlay, (cx - tw // 2 - pad_x, cy - th // 2 - pad_y),
                      (cx + tw // 2 + pad_x, cy + th // 2 + pad_y), bg_color, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        cv2.rectangle(frame, (cx - tw // 2 - pad_x, cy - th // 2 - pad_y),
                      (cx + tw // 2 + pad_x, cy + th // 2 + pad_y), (200, 200, 200), 1)
        cv2.putText(frame, text, (cx - tw // 2, cy + th // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)

        return self.angle, frame

    def change_lane(self, lanes_detection, destination):

        threshold = self.change_lane_threshold
        count = self.change_lane_count

        # extract data from lane detection
        frame = lanes_detection["frame"]
        left_lane = lanes_detection["left"]
        right_lane = lanes_detection["right"]
        left_coef = lanes_detection["left_coef"]
        right_coef = lanes_detection["right_coef"]

        # Choose turning left/right
        self.turn_left = True if (destination == -1 and not self.turn_right) else False
        self.turn_right = True if (destination == 1 and not self.turn_left) else False

        # If both are False => We still are on the middle of changing lanes so act accordingly
        if not self.turn_left and not self.turn_right:
            # if stage_1 => reset params and exit
            if self.change_lane_stage_1:
                self.reset_change_lane_params()
                self.angle, frame = self.lane_keeping(lanes_detection)

                self.log.debug(
                    ">>>> Lane change interrupted - remaining in current lane due to conflicting turn signal.\n"
                )
                return self.angle, frame

            # else (stage_2) => reset params and run change_lane depending on the last call
            else:
                self.reset_change_lane_params()
                self.turn_left = True if destination == -1 else False
                self.turn_right = True if destination == 1 else False

        # Find mean of each lane
        # maybe find the middle point of the polyfits (from coefs)
        mean_right = 0 if not right_lane else float(np.average(right_lane))
        mean_left = 0 if not left_lane else float(np.average(left_lane))

        # if we have not change lanes (From the beginning)
        if self.change_lane_stage_1:

            # For left turn
            if self.turn_left:
                # Because we want to turn left check if left lane became right
                left_lane_changed_to_right = (
                    self.prev_mean_left + threshold > mean_right
                    and self.prev_mean_left > 0
                    and mean_right > 0
                )

                if left_lane_changed_to_right:
                    self.change_lane_stage_1 = False
                    self.change_lane_stage_2 = True
                    # else stay in stage 1

            # for right turn
            elif self.turn_right:

                # check if right lane became the left one
                right_lane_changed_to_left = (
                    self.prev_mean_right - threshold < mean_left
                    and self.prev_mean_right > 0
                    and mean_left > 0
                )

                if right_lane_changed_to_left:
                    self.change_lane_stage_1 = False
                    self.change_lane_stage_2 = True

        # if lanes changed again as they were before
        elif self.change_lane_stage_2:

            if self.turn_left:

                # if right lane changes to left
                right_lane_changed_to_left = (
                    self.prev_mean_right - threshold < mean_left
                    and self.prev_mean_right > 0
                    and mean_left > 0
                )

                if right_lane_changed_to_left:
                    self.change_lane_stage_2 = False
                    self.change_lane_stage_1 = True
                    # else stay in stage 2

            elif self.turn_right:

                # if left lane changes to right
                left_lane_changed_to_right = (
                    self.prev_mean_left + threshold > mean_right
                    and self.prev_mean_left > 0
                    and mean_right > 0
                )

                if left_lane_changed_to_right:
                    self.change_lane_stage_2 = False
                    self.change_lane_stage_1 = True

        # [Stage 1] When left/right lanes are still the same
        if self.change_lane_stage_1:

            # Check if with the detected lanes we can switch lanes
            if (self.turn_left and not left_lane) or (self.turn_right and not right_lane):
                # initialize params for next run and exit

                self.reset_change_lane_params()
                self.angle, frame = self.lane_keeping(lanes_detection)
                self.log.debug(
                    "\n\n\n\n>>>> Unable to change lanes - correct lane did not detected.\n\n\n\n"
                )

                return self.angle, frame

            if self.turn_left:
                # Make left --> None, right lane --> left and then do lane keeping
                self.angle, error, frame = self.pid_controller(None, left_coef, frame)
                self.count = 0

            elif self.turn_right:
                # Make left lane --> right, right --> None and then do lane keeping
                self.angle, error, frame = self.pid_controller(right_coef, None, frame)
                self.count = 0

        # [Stage 2] When lanes have changed only once (Do lane keeping without changing anything, wait for some frames and then exit)
        elif self.change_lane_stage_2:

            self.angle, error, frame = self.pid_controller(left_coef, right_coef, frame)

            # if we are on stage 2 for the required frames (change params for next run and exit)
            if self.count >= count:
                self.reset_change_lane_params()
                self.log.debug(">>>> Lane change completed successfully.\n")
            else:
                self.count += 1

        self.fix_angle()
        self.last_angle = self.angle

        self.prev_mean_left = mean_left
        self.prev_mean_right = mean_right

        return self.angle, frame

    def reset_change_lane_params(self):
        self.turn_left = False
        self.turn_right = False
        self.overtake_type = None
        self.count = 0
        self.change_lane_stage_1 = True
        self.change_lane_stage_2 = False
        self.prev_mean_left = 0
        self.prev_mean_right = 0
        self.smoothing_iterations = self.max_smoothing_iterations
        self.smoothing_step = 0
        self.smoothing_factor = np.linspace(
            self.min_smoothing_factor,
            self.max_smoothing_factor,
            self.smoothing_iterations,
        )

    # ------------------------------------------------------------------------------#

    def pid_controller(self, left, right, frame=None):
        """Performs the angle calculation based on the left and right polyfits. Steps :
        1) create a polyfit for the desired lane that the car should follow.
        2) extract the points of that lane and the lane that the car currently follows.
        3) find the error of those two points (width diffrence in the same height)
        4) adjust steering angle based on the error and PID controller's parameters

        Parameters
        ----------
        left : array
            Left polyfit
        right : array
            Right polyfit
        frame : array
            The frame with the lines

        Returns
        -------
        float
            calculated angle
        float
            calculated error
        array
            The frame with the desire lane
        """

        if left is None and right is None:
            angle = self.last_angle
            error = 0
            self.log.warning("No lanes found")
        else:
            desired_lane = self.desired_lane(left, right)

            if self.print_desire_lane:
                self.visualize_desire_lane(frame, desired_lane)

            error = self.get_error(desired_lane)
            angle = 90 - math.degrees(math.atan2(self.height, error))

            # If we change lanes --> Smooth the lane
            if (self.turn_left or self.turn_right) and self.change_lane_stage_1:
                if self.smoothing_step < self.smoothing_iterations:
                    angle = angle * self.smoothing_factor[self.smoothing_step]
                    self.smoothing_step += 1

        self.last_angle = angle
        return angle, error, frame

    def fix_angle(self):
        """Fixes the angle so the car changes its position smoothly.
        - simple PD control on the angle (not activated now)
        - rolling average on the last N calculated angles (activated)
        """

        self.steer_value_list.insert(0, self.angle)
        if len(self.steer_value_list) == self.median_constant:
            self.steer_value_list.pop()

        median = np.average(self.steer_value_list)
        self.angle = median
        self.last_angle = self.angle

    def lane_keeping(self, lanes_detection):
        """Performs the pipeline for the lanekeeping.
        1) Perform Lane Detection
        2) Calculate the steering angle for lane keeping
        3) Smooth the angle

        Parameteres
        -----------
        lanes_detection : dictionary
            Result of lane detection : frame, left_coef, right_coef

        Returns
        -------
        float
            calculated steering angle
        array
            lane keeping output image
        """

        frame = lanes_detection["frame"]
        left_coef = lanes_detection["left_coef"]
        right_coef = lanes_detection["right_coef"]

        if self.turn_left:
            self.angle, frame = self.change_lane_maneuver(lanes_detection, direction="left", overtake_type=self.overtake_type)

        elif self.turn_right:
            self.angle, frame = self.change_lane_maneuver(lanes_detection, direction="right", overtake_type=self.overtake_type)

        else:

            trust_left = lanes_detection["trust_left"]
            trust_right = lanes_detection["trust_right"]

            left_coef = left_coef if trust_left else None
            right_coef = right_coef if trust_right else None

            self.angle, error, frame = self.pid_controller(left_coef, right_coef, frame)

            self.fix_angle()
            self.last_angle = self.angle

        self.angle = max(min(self.max_lk_steer, self.angle), -self.max_lk_steer)

        return self.angle, frame
