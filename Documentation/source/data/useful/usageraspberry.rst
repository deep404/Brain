Developing on Raspberry Pi
==========================

Direct Connection – Ethernet Cable
----------------------------------
You can connect a PC directly to the Raspberry Pi using an Ethernet cable.

Two options exist:

1. **Automatic addressing (Zeroconf)**  
   Most systems assign link-local addresses automatically, allowing access at:  
   ``raspberrypi.local``

2. **Static IP setup**  
   Configure static IPs on both PC and Pi if needed.

This approach works well for isolated, offline development setups.

Remote Development – SSH and SFTP
---------------------------------
The most common method for remote development uses:

- **SSH** for terminal access  
- **SFTP** for file transfer  

Enable SSH via:

- empty ``ssh`` file in ``/boot`` (first boot), or  
- ``sudo raspi-config`` → Interface Options → SSH  

**Linux/macOS:**

- SSH: ``ssh user@IP``  
- SFTP: ``sftp://<IP>`` via file explorer  

**Windows:**

- SSH: PuTTY or Windows Terminal  
- SFTP: WinSCP  

Remote Development – VNC or X11 Forwarding
-------------------------------------------
`VNC <https://www.raspberrypi.org/documentation/remote-access/vnc>`_ provides a full
remote graphical desktop.

Enable via ``sudo raspi-config``

→ Interface Options → VNC

Alternatively, you can forward individual windows using:

Enable via ``ssh -X user@IP``

However, X forwarding is typically slower than VNC.

Remote Development – VS Code (Remote SSH)
------------------------------------------
Visual Studio Code offers a highly productive workflow using the
**Remote SSH** extension.

Features:

- Directly edits files on the Raspberry Pi  
- Integrated terminal and debugging  
- Intellisense, linting, Python/C++/Node support  
- Automatic file sync  

This is one of the most popular modern methods for RPi development.

Network File System (NFS) Development
-------------------------------------
You may keep project files on your PC and let the Raspberry Pi access them via NFS.

Advantages:

- No need to repeatedly upload files  
- Fast for large codebases  
- Ideal when building on the PC but running on the Pi  

Example:

``sudo mount -t nfs <pc-ip>:/project /home/pi/project``


Container-Based Development (Docker/Podman)
-------------------------------------------
The Raspberry Pi 5 is powerful enough to run containers efficiently.

Use cases:

- Microservices  
- Robotics frameworks (e.g., ROS2 containers)  
- Reproducible development environments  
- Isolated Python/Node.js/C++ toolchains  

Typical workflow:

- Build containers on the PC  
- Deploy and run them on the Pi  

Development Method Summary
--------------------------

+---------------------------+------------------------------+-----------------------------+------------------------------+
| Method                    | Use Case                     | Pros                        | Cons                         |
+===========================+==============================+=============================+==============================+
| Direct (HDMI)             | Full desktop                 | Simple & stable             | Requires peripherals         |
+---------------------------+------------------------------+-----------------------------+------------------------------+
| FTDI Serial               | Setup/debug w/o network      | Works even when system fails| No GUI, limited bandwidth    |
+---------------------------+------------------------------+-----------------------------+------------------------------+
| USB-C Gadget Mode         | Headless, fast dev           | One cable, stable, no Wi-Fi | Requires config              |
+---------------------------+------------------------------+-----------------------------+------------------------------+
| Direct Ethernet           | Offline access               | Fast & reliable             | Some setup needed            |
+---------------------------+------------------------------+-----------------------------+------------------------------+
| SSH + SFTP                | Daily development            | Fast, secure, convenient    | Terminal only                |
+---------------------------+------------------------------+-----------------------------+------------------------------+
| VNC                       | GUI remote work              | Full desktop experience     | Slower than SSH              |
+---------------------------+------------------------------+-----------------------------+------------------------------+
| VS Code Remote SSH        | Modern coding workflow       | Debugging, linting, IDE     | Needs stable SSH             |
+---------------------------+------------------------------+-----------------------------+------------------------------+
| NFS Development           | Large projects               | No file sync needed         | Requires network & setup     |
+---------------------------+------------------------------+-----------------------------+------------------------------+
| Container-based dev       | Reproducible envs            | Clean isolation, scalable   | Overhead vs native           |
+---------------------------+------------------------------+-----------------------------+------------------------------+
