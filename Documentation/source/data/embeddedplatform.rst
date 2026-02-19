Embedded platform
=================

.. toctree::
   :maxdepth: 1
   :hidden:

   embeddedplatform/preliminarySetup
   embeddedplatform/buildAndFlash
   embeddedplatform/newComponent
   embeddedplatform/debugging
   embeddedplatform/mainFlow
   embeddedplatform/calibration

**Quick navigation**

* :doc:`Preliminary setup <embeddedplatform/preliminarySetup>`

  - Follow this first to correctly set up your environment. 

* :doc:`This is how you can build your project <embeddedplatform/buildAndFlash>`

  - Step-by-step instructions to compile and flash the code.

* :doc:`Adding a new component (object) <embeddedplatform/newComponent>`

  - Use our helper script to easily generate new components.

* :doc:`Debugging via serial <embeddedplatform/debugging>`

  - This is how you debug the board via serial

* :doc:`How it works <embeddedplatform/mainFlow>`

  - A high-level view of how the embedded logic works.

* :doc:`calibration procedure <embeddedplatform/calibration>`

  - A few notes regarding the calibration

.. note::

   The **embedded platform** runs on the :code:`Nucleo-F401RE` microcontroller.  
   It acts as a bridge between high-level processing and low-level motor control & sensor reading.

The project is based on **C/C++** and uses **mbed OS v6.17**.  
Its architecture is organized into **four main layers**:

**1. Brain**
   - State machine of the Nucleo
   - KL manager and power safety features
   - Global states definition
   - High-level controlling logic

**2. Drivers**
   - Interfaces for: BatteryManager, BNO, SteeringMotor, SpeedingMotor, SerialCommunication, VelocityControlDuration
   - Responsible for low-level hardware interaction

**3. Periodics**
   - Periodic tasks such as:
     - IMU value publishing
     - Blinker signals (running version)
     - Instant consumption & total voltage publisher
     - Resource monitor

**4. Utils**
   - Helper tools: serial message (de)construction, callbacks, tasks interface, task manager

.. tip::

   Start with the **Preliminary setup** if this is your first time working on the platform.  
   Once everything is installed and built, explore the **Debugging** section to test your setup.