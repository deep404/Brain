Traffic Signs
=============

Signs
-----

The track may contain the following types of traffic signs:

- Stop sign  
- Parking sign  
- Priority sign  
- Crosswalk sign  
- Highway entrance sign  
- Highway exit sign  
- Roundabout sign  
- One-way road sign  
- No-entry road sign  

You can download the full set of signs in PDF format here:  
`Traffic signs <https://github.com/ECC-BFMC/Documentation/blob/master/source/racetrack/TrafficSign.pdf>`_

This file can be printed to reproduce the signs accurately.

Each sign is contained within a **6 × 6 cm square** (scaled accordingly).  
Two examples are shown below:

.. image:: ../../images/racetrack/TrafficSign_Example.png
   :align: center
   :width: 50%

Each sign is mounted on top of a pillar, placing the visible sign at a height of **~20 cm**.  
Example below:

.. image:: ../../images/racetrack/TrafficSign_Construct.png
   :align: center
   :width: 50%

Below is how the signs look when placed on the actual track:

.. image:: ../../images/racetrack/StopSignReal.jpg
   :align: center
   :width: 50%

Traffic Sign Pillar (3D Models)
-------------------------------

The 3D models for the traffic sign supports can be found here:

- `Traffic sign base <https://github.com/ECC-BFMC/Documentation/blob/master/source/3DModels/TrackParts/SignPole_Base.STL>`_  
- `Traffic sign pole <https://github.com/ECC-BFMC/Documentation/blob/master/source/3DModels/TrackParts/SignPole.STL>`_  

Location on the Track
---------------------

The placement of traffic signs and traffic lights follows a consistent logic:

- Signs are positioned relative to the **road object they annotate**, such as:
 
  - Intersections  
  - Parking zones (start/end)  
  - Crosswalks  
  - Roundabouts  
  - Highway entrances/exits  
