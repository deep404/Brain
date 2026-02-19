Fresh Start
===========

Option 1 – Build Using Our Image
--------------------------------

You can quickly set up your Raspberry Pi by flashing our preconfigured
`raspberry-BFMC2025-image`_ onto an empty SD card using the Raspberry Pi Imager.

.. _raspberry-BFMC2025-image: https://mega.nz/folder/mSBWFBIb#kR2f8mvAXj4gUnTHlm2tIg

**Steps:**

1. Open **Raspberry Pi Imager**.  
2. Insert your SD card into the PC.  
3. In *Raspberry Pi Device*, select **Raspberry Pi 5**.  
4. In *Operating System*, scroll down and choose **Use custom**, then select the downloaded image.  
5. In *Storage*, select your SD card.  
6. Open *Settings* and configure **only** the username and password  
   (default: ``pi`` / ``raspberry``).  
7. Click **Next** and complete the flashing process.

After flashing, insert the SD card into the Raspberry Pi and power it on. First boot after the flash might take a little bit longer.

Option 2 – Build From Scratch
-----------------------------

**Steps can be adjusted or skipped depending on your needs.**

1. Flash a clean Raspberry Pi OS image
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Open **Raspberry Pi Imager**.  
2. Insert your SD card into the PC.  
3. In *Raspberry Pi Device*, select **Raspberry Pi 5**.  
4. In *Operating System*, choose **Raspberry Pi OS**.  
5. In *Storage*, select your SD card.  
6. Open *Settings* and configure:
   - Username and password  
   - Your Wi-Fi credentials (optional but recommended)
7. Click **Next** to flash the card.

2. Connect to the Raspberry Pi
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ensure your PC and Pi are on the **same network**, then open a terminal or CMD:

.. code-block:: bash

    ping raspberrypi.local
    ssh pi@192.168.x.x

If ``raspberrypi.local`` does not resolve, check your router for the assigned IP.

3. Update and configure the system
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bring your OS up to date and configure basic development settings.

Typical actions:

- ``sudo apt update``  
- ``sudo apt upgrade``  
- configure git credentials  
- install additional packages as needed  

4. Clone the Brain repository and install dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    git clone https://github.com/ECC-BFMC/Brain.git
    cd Brain
    chmod +x setup.sh
    ./setup.sh
    cd src/dashboard/frontend
    npm start
    answer "y" to the popup
    close the frontend (CTRL + C)
    cd ../..

5. Install required services and reboot
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Services are described in detail in :doc:`services <services>`.

.. code-block:: bash

    cd services
    chmod +x angular-autostart/install.sh angular-autostart/uninstall.sh
    chmod +x brain-autostart/install.sh brain-autostart/uninstall.sh
    chmod +x rpi-wifi-fallback/install.sh rpi-wifi-fallback/uninstall.sh rpi-wifi-fallback/add-wifi.sh

    ./angular-autostart/install.sh
    ./brain-autostart/install.sh
    ./rpi-wifi-fallback/install.sh

    sudo reboot
