Hardware Improvements
=====================

Let’s imagine you write a script to turn on a light bulb. At first glance, nothing happens.  
Should you rewrite the code?  
Often, the simplest approach is to check whether the bulb is properly plugged in.

This guide follows the same philosophy.  
Before troubleshooting software issues or motor-control logic, you should first ensure that the **mechanical parts of the chassis are functioning optimally**.

Below you will find recommendations for mechanical improvements, adjustments, and common checks that help prevent unnecessary debugging.

FAQ
---

**What are the advantages?**

- Improving mechanical skills  
- Reducing friction in the transmission (lower current consumption)  
- Achieving smoother driving  
- Reducing the risk of the car getting stuck while cornering  

**Can this step be skipped?**

The car kit includes a brushless motor with an integrated ESC, which maintains a nearly constant speed.  
This compensates partially for drivetrain friction and helps avoid getting stuck.  
However—just like buying a used car—it is strongly recommended to perform a mechanical inspection to ensure optimal performance.

**What tools do I need?**

- Hex key screwdriver  
- Grease  
- Degreaser  
- Isopropyl alcohol  
- Sponge & brush  
- Pliers  
- Phillips screwdriver  
- Flat file / sandpaper  

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/tools.png
   :align: center
   :width: 40%

**How much time is needed?**

- Approximately **4 hours** of work.

Transmission from the Motor
---------------------------

This part includes:

- Cleaning and greasing both differentials  
- Adjusting distances when remounting components  
- Checking for friction throughout the drivetrain  

Removing the Computer Board Support
-----------------------------------

Disconnect all wires, remove the mounting nut, then take off the safety clamps and case holders.

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/RPIsupport.png
   :align: center
   :width: 50%

Removing the Back Driving Shafts
---------------------------------

Unscrew the highlighted screws:

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/back_driving_shaft.png
   :align: center
   :width: 50%

Removing the Differential
-------------------------

Unscrew the highlighted screws. After step 3 you will see the cogwheels.

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/differential.png
   :align: center
   :width: 70%

Cleaning the Cogwheels
----------------------

1. Remove both differential halves.  
   From **Piece A**, remove the bearing and permanently remove the washer.  
2. Clean all grease from the case, cogwheels, and bearings.  
   Degrease the bearings thoroughly (e.g., with isopropyl alcohol) until they spin freely.

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/cogwheel.png
   :align: center
   :width: 50%

Tightening the Screws Equally
-----------------------------

- Remove the safety washer (A), then permanently remove the washer (B).  
- Remove the screws from the plastic cogwheel.  
  Lightly sand the surface where the flange attaches until flat.

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/drivenwheel.png
   :align: center
   :width: 70%

Mounting Them Back
------------------

- Apply grease to all moving parts.  
- Tighten screws evenly (not too tight), in the order indicated.  
- Spin the driving shaft to verify there are no blocking points.

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/mountback.png
   :align: center
   :width: 70%

Adjusting the Distance Between Cogwheel Axes
--------------------------------------------

Because cogwheels are not perfectly round, the gap between them may change during a full rotation.  
This may cause:

- Loss of grip  
- Wheel locking  

**Procedure:**

- Loosen screw **C**  
- Have someone spin both front wheels while you adjust the cogwheel distance  
- The goal is smooth rotation throughout the *entire* revolution of cogwheel A  

Note: tightening screw C may shift the cogwheel, requiring re-adjustment.

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/distance.png
   :align: center
   :width: 50%

Front-Axis Differential
-----------------------

The front differential requires **exactly the same treatment** as the rear one.

Abnormal Free Movement of the Wheels
------------------------------------

It is normal for wheels to feel slightly loose.  
You must balance:

- Too much freedom → loose parts  
- Too much stiffness → restricted movement  

We recommend placing a **thin washer** between the bearing and the driving shaft joint (thickness depends on the gap).  
Compare the modified wheel with an unmodified one.

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/wheelladjustment.png
   :align: center
   :width: 50%

Driving Shafts Must Move Freely
-------------------------------

The highlighted parts are the driving shafts. They must always move freely, regardless of wheel angle or ground clearance.

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/drivingshaft.png
   :align: center
   :width: 50%

To increase free movement:

- Slightly unscrew both the upper and lower screws  
- Repeat until the shaft moves freely in all positions  

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/gap.png
   :align: center
   :width: 50%

Steering
--------

The steering servo requires an additional screw to ensure the steering column does not disengage.  
The placement is difficult to access when the car is fully assembled.

Possible options:

1. Install it while working on the front differential.  
2. Unscrew the servo (without removing the rod), install the screw, and then reassemble.  
3. Use an improvised angled screwdriver—best for patient users.

**Important:** Ensure the Nucleo and servo are powered so that the servo holds the **0° position** during installation.

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/servo.png
   :align: center
   :width: 50%


Setting the Wheels’ Camber
--------------------------

**What is wheel camber?**

Camber is the angle of the wheel relative to a flat surface:

- **Positive camber**: top of wheel leans outward  
- **Negative camber**: top leans inward  

For this challenge, a **negative camber** is recommended.

**Benefits:**

- Improved handling  
- Reduced vibration during turns  
- Higher cornering speeds  
- More direct steering  
- Reduced steering force  
- Smaller steering angles  

### Setting Front-Axle Camber

Two ball-head screws (red circled) control camber.  
Steps:

- Insert a **2.5 mm hex wrench** through the wheel rim  
- Unscrew the upper screw more than the lower one  
- Adjust both sides symmetrically  

When removing the wheel, you will see a **plastic grub screw** (green circled), tightened with a **5 mm hex wrench**.  
This only secures the axis stub.

Before reattaching the wheel:

- Ensure both ball-head screws rotate freely  
- Ensure suspension moves freely after adjustment  

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/frontaxle.png
   :align: center
   :width: 50%

### Setting Rear-Axle Camber

You can modify rear camber by:

- Turning the red-circled screws to change the distance between chassis and wheel top  
- OR adjusting the traverse link mounting position (three available holes, green circled)

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/backaxle.png
   :align: center
   :width: 50%


Setting the Wheels’ Alignment
-----------------------------

**What is wheel alignment?**

Alignment (toe-in / toe-out) describes how the wheels point relative to the driving direction.

**Toe-in** is recommended for this challenge:

- Improves lateral cornering  
- Gives more direct steering response  

### Setting Front-Axle Alignment

Turn the **track rod levers** (red circled).  
They have reverse threads and can be adjusted without disassembly.  
Ensure both sides are adjusted symmetrically and test that the car drives straight.

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/frontaxlealignment.png
   :align: center
   :width: 50%


Adjusting the Car’s Height
--------------------------

Ground clearance is set using four screws.  
To increase height, loosen them (do **not** remove them).

Screw locations:

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/height.png
   :align: center
   :width: 50%


Adjusting the Suspensions
-------------------------

Even after increasing clearance, the car may not stay elevated due to soft suspension springs.

Suspensions can be hardened by:
- Using one of **six possible combinations**  
- Adding a **spacer** between the spring and its support  

.. image:: ../../images/hardwaresetupforcar/hardware_improvements/suspensions_back.png
   :align: center
   :width: 50%
