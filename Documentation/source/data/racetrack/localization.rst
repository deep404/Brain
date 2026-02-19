Localization System
===================

The localization system used at our competition venue is built using  
**MDEK1001** devices (`MDEK1001 <https://www.qorvo.com/products/p/MDEK1001>`_),  
which can be reproduced in each team’s testing environment.  
A full kit of **12 boards** can typically be found for **~300 USD**.

Each MDEK1001 module can be configured as an:

- **Anchor**
- **Tag**
- **Gateway**

All configuration is done through Qorvo’s mobile application via **BLE**.

System Architecture
-------------------

One important characteristic of our setup is that we **do not** obtain the
location data from the Gateway.  
Instead:

1. The **Tag** outputs its position directly over **serial communication**.  
2. A small device is connected via UART to the MDEK Tag.  
3. That device sends the location wirelessly to the **TrafficCommunicationServer**.  
4. The TrafficCommunicationServer provides location updates to the interested cars.

This approach ensures low latency, simpler integration, and independence from the
MDEK’s built-in network positioning messages.

Recommendation for Teams
------------------------

To best simulate how localization data is gathered and distributed in the
official environment, we encourage you to:

- Base your implementation on this architecture  
- Use the **TrafficCommunicationServer** (described in the *Computer* section)
  as your starting point  
- Read UWB Tag data via **serial/UART**, not via the Gateway

By mirroring this structure, your system will behave consistently with the one
used during the competition.
