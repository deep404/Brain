Welcome to BFMC's documentation!
================================

Bosch Future Mobility Challenge (BFMC) is an international student technical competition of Bosch Engineering Center Cluj since 2017. Our partner 
is IEEE-ITSS. In this competition the participants have to to implement autonomous driving alghoritms on a vehicle at 1/10 scale, provided by Robert 
Bosch. Check here the competition `website <https://boschfuturemobility.com/>`_

This is the official documentation of the competition and it includes the descriptions of the given code, the race-track and it's elements, V2X 
systems, diagrams, hardware, as well as a starting point and directions of the knowledge required for the best experience.

The Brain project is already installed on the provided Raspberry Pi, while the embedded project is already implemented on the Nucleo board, while 
the computer project needs to be installed on a PC.

.. toctree::
   :titlesonly:
   :maxdepth: 1
   :hidden:
   
   data/demo
   data/hardwaresetupofcar
   data/racetrack
   data/vehicletoeverything
   data/embeddedplatform
   data/brain
   data/useful


All given packages
------------------

* :doc:`Demo <data/demo>`

  - Describes how to play with the car, with the gven demo.

* :doc:`Connection Diagram <data/hardwaresetupofcar>`

  - All the hardware components list that can be found on the car together with the diagram connection scheme and other useful things.

* :doc:`Race track <data/racetrack>`

  - Info about all the phisical elements that can be found on the racetrack, their dimensions and placement. This info can be used in order to recreate a similar environment.

* :doc:`Vehicle to everything <data/vehicletoeverything>`

  - A series of connectivity servers and softwares will be present at the competition, like semaphores, a localization system, a traffic monitor and vehicle communication.

* :doc:`Embedded platform <data/embeddedplatform>`

  - The code that is already installed on the Nucleo board. Here's how it works.

* :doc:`Brain <data/brain>`

  - The code that is already installed on the raspbery. Here's how it works.

* :doc:`Useful links and information <data/useful>`

  - General useful information. A series of tools and skills that would be beneficial for this project. Of course you can use your own.