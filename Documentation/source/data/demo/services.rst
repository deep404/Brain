Services
========

Three services are installed on the Raspberry Pi to simplify configuration,
startup behavior, and development workflows.

angular-autostart
-----------------
This service automatically starts the frontend (dashboard) during boot.

Key points:

- The frontend starts once at boot, even if its code changes.  
- There is **no need to manually restart** the frontend after code updates.  
- This is especially useful during development, as frontend startup can take time.

Documentation for this service is available in the  
`raspberry-BFMC2025-angular-autostart README`_.

.. _raspberry-BFMC2025-angular-autostart README: https://github.com/ECC-BFMC/Brain/tree/master/services/angular-autostart

brain-autostart
---------------
This service waits for an incoming HTTP connection on the Angular frontend port.
Once a connection is detected, it automatically starts the Brain ``main.py`` script.

Key points:

- Primarily useful during demos.  
- Can be disabled during active development if manual control is preferred.

Documentation is available in the  
`raspberry-BFMC2025-brain-autostart README`_.

.. _raspberry-BFMC2025-brain-autostart README: https://github.com/ECC-BFMC/Brain/tree/master/services/brain-autostart

rpi-wifi-fallback
-----------------
At boot, this service checks whether the Raspberry Pi can connect to a known Wi-Fi network.

Behavior:

- If a valid Wi-Fi connection **is available**, it connects normally (based on the prioritization of the networks).
- If **no Wi-Fi network is found**, it automatically starts a hotspot, allowing a computer
  or phone to connect to the Raspberry Pi.  
- After connecting, you may either:
  
  - remain on the hotspot (no internet), or  
  - configure the Raspberry Pi to connect to a valid Wi-Fi network.

Documentation is available in the  
`raspberry-BFMC2025-rpi-wifi-fallback README`_.

.. _raspberry-BFMC2025-rpi-wifi-fallback README: https://github.com/ECC-BFMC/Brain/tree/master/services/rpi-wifi-fallback
