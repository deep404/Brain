Race Track
==========

.. toctree::
   :maxdepth: 1
   :hidden:

   racetrack/material
   racetrack/roadmarkings
   racetrack/trafficsigns
   racetrack/otherelements
   racetrack/localization

* :doc:`Material </data/racetrack/material>`
  
  - Overview of the material characteristics.

* :doc:`Road markings </data/racetrack/roadmarkings>`
  
  - Description, sizes, and technical details of the road markings used on the track.

* :doc:`Traffic signs <racetrack/trafficsigns>`
  
  - Traffic signs PDF and the 3D model of the poles.

* :doc:`Other elements on the racetrack <racetrack/otherelements>`
  
  - Additional elements such as semaphores, pedestrians, blocks, tunnels, etc.

* :doc:`Localization system replica <racetrack/localization>`
  
  - Description of our localization system, which you can use to build your own.

Tracks
------

Here you can find the official maps in SVG format.  
You can extract any dimensions that are not explicitly listed in the pages above or use the files to design and build your own track.

- `Test Track <https://github.com/ECC-BFMC/Documentation/blob/master/source/racetrack/Track_Test.svg>`_  
- `Race Track <https://github.com/ECC-BFMC/Documentation/blob/master/source/racetrack/Track.svg>`_  

Elements Positioning
--------------------

The corresponding elements are fixed in the following locations on the track and will not be moved:

- Start semaphore at the starting line.  
- Parking signs at the beginning and end of the parking zones (left & right).  
- Traffic lights at each entry of the designated intersection.  
- Roundabout signs at every roundabout entry.  
- Highway entry signs at every highway entrance.  
- Highway exit signs at every highway exit.  
- Crosswalk signs at every crosswalk.  
- Tunnel location remains fixed.
- Different size in lane width.

.. image:: ../images/racetrack/Track.png
   :align: center
   :width: 50%
