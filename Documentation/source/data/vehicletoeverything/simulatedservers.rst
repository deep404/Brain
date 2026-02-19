Simulated Servers
=================

Two simulated servers are provided, mirroring the behavior of the servers used
at the physical competition location. To use them locally, begin by cloning the
`Computer`_ repository on your PC.

.. _Computer: https://github.com/ECC-BFMC/Computer

Clone and Prepare the Repository
--------------------------------

.. code-block:: bash

    git clone https://github.com/ECC-BFMC/Computer.git
    cd Computer
    git submodule update --init --recursive

Each simulated server must be started in a separate terminal.

Starting the Traffic Communication Simulator
--------------------------------------------

In the **first terminal**, run:

This script simulates the **TrafficCommunicationServer**, including the
communication flow and the periodic broadcasting of vehicle positions.

.. code-block:: bash

    cd src/servers/trafficCommunicationServer
    python3 TrafficCommunication.py

Starting the Semaphore Stream Simulator
---------------------------------------

In the **second terminal**, run:

This script simulates the **streaming data from the traffic semaphore**, providing
a UDP-based data stream identical to the one available on-site.

.. code-block:: bash

    cd src/servers/SemaphoreStreamSIM
    python3 udpStreamSIM.py
