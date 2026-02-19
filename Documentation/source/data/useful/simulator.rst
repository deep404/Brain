Simulator
=========

Installing the Simulator on the PC
----------------------------------

The reference environment uses **Ubuntu 20.04** and **ROS Noetic**, but any newer Ubuntu version and any newer **ROS 1** distribution should also work.

The same repository contains **additional branches**, each contributed independently by participating teams.  
These branches were **created and published by the teams themselves**.  
**Bosch does not maintain, curate, or take ownership of the content in those branches;** they are made available *as-is* for reference or inspiration.

To install the simulator, clone the repository into your **Documents** folder, then follow the steps below  
(replace `{YOUR_USER}` with your actual username):

.. code-block:: bash

    catkin_make --pkg utils
    catkin_make
    echo 'export GAZEBO_MODEL_PATH="/home/{YOUR_USER}/Documents/Simulator/src/models_pkg:$GAZEBO_MODEL_PATH"' >> devel/setup.bash
    echo 'export ROS_PACKAGE_PATH="/home/{YOUR_USER}/Documents/Simulator/src:$ROS_PACKAGE_PATH"' >> devel/setup.bash
    source devel/setup.bash
    roslaunch sim_pkg map_with_all_objects.launch

Next, open **two additional terminals** and run:

.. code-block:: bash

    source devel/setup.bash
    rosrun example camera.py

.. code-block:: bash

    source devel/setup.bash
    rosrun example control.py


Additional Notes
----------------

Camera
~~~~~~

To modify camera **resolution** or **position**, adjust the following files:

- `src/models_pkg/camera/model.sdf`  
  Contains `<width>` and `<height>` tags for resolution.  
  No workspace recompilation is required.

- `src/models_pkg/rcCar_assembly/model.sdf`  
  Contains:

  - `<uri>model://camera</uri>` (camera inclusion)  
  - `<pose>` tag specifying position and orientation  
    (format: `<pose>X Y Z ROLL PITCH YAW</pose>` in radians)

  No recompilation is required after these changes.

Working with Gazebo
~~~~~~~~~~~~~~~~~~~

- To restart the simulation without restarting Gazebo:  
  `rosservice call /gazebo/reset_simulation`
- Disable the GUI in your launch file to save computational resources.
- Use **rqt** to inspect images, topics, frequencies, and debug data.
- To change map resolution, edit:  
  `src/models_pkg/track/materials/scripts/bfmc_track.material`  
  Higher resolution = higher resource usage.
- In `src/sim_pkg/launch/sublaunchers/` you will find launch files for each group of objects.  
  You can spawn specific elements while the simulator is running.
- You may create your own launch configurations by including existing launch files.  
  Example: `map_with_all_objects.launch` in `src/sim_pkg/launch/`.


ROS Vehicle and Simulator Integration
-------------------------------------

To integrate the physical car with the simulator, both the **RPi** and the **PC** must:

- Be on the **same network**
- Have **SSH enabled** on the Raspberry Pi
- Share consistent **ROS environment variables**

This setup allows the nodes on the car to communicate with the **roscore** running on the PC  
(or vice versa, if you choose to run roscore on the RPi instead).

On the Raspberry Pi
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    export ROS_IP=`hostname -I`
    export ROS_HOSTNAME=`hostname -I`
    export ROS_MASTER_URI="http://PC_IP:11311"

Where **PC_IP** is the IP address of the simulation PC.

On the PC
~~~~~~~~~

.. code-block:: bash

    export ROS_IP=`hostname -I`
    export ROS_HOSTNAME=`hostname -I`
    export ROS_MASTER_URI="http://$ROS_IP:11311"

Launching the System
--------------------

On the Raspberry Pi
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    cd Brain_ROS
    source devel/setup.bash
    roslaunch sim_pkg start_car_virtual.launch

On the PC
~~~~~~~~~

.. code-block:: bash

    cd Simulator
    source devel/setup.bash
    roslaunch sim_pkg map_with_car.launch

After launching:

- The **simulator publishes** on topics such as:  
  `automobile/image_raw`,  
  `automobile/localization`,  
  `automobile/IMU`,  
  `automobile/feedback`,  
  `automobile/semaphores/_`

- The **simulator subscribes** to:  
  `automobile/command`

Your vehicle (Brain_ROS on the RPi) can publish and subscribe normally, as if interacting with a real-world system.
