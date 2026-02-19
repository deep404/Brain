V2X - Vehicle to everything
============================

.. toctree::
   :maxdepth: 1
   :hidden:
   
   vehicletoeverything/TrafficCommunication
   vehicletoeverything/Semaphores
   vehicletoeverything/simulatedservers

* :doc:`Traffic communication system <vehicletoeverything/TrafficCommunication>`

  - How the TrafficCommunication system is working and how to interact with it

* :doc:`Semaphores <vehicletoeverything/Semaphores>`

  - How the semaphores are streaming data on the track.

* :doc:`Simulated servers <vehicletoeverything/simulatedservers>`

  - Simulates the servers we have in the location.

For all the V2X communications to work, all the cars RPi (or computers replaced) will have to be connected to the same LAN. Prior the competition, the teams will 
share with the organizers the MAC of the car computer, so to get a static IP address for their car.

API's are given in the brain project for interaction with all the systems, together with simulated servers (or components), which are running on a computer.
This is done to ensure that the participants have integrated the functionality of all the systems present at the 
location. 