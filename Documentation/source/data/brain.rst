Brain Project
=============

.. toctree::
   :maxdepth: 1
   :hidden:

   brain/newComponent
   brain/mainFlow
   brain/stateMachine

* :doc:`New component <brain/newComponent>`
  
  - How to integrate new components into the existing codebase.

* :doc:`How it works <brain/mainFlow>`
  
  - Explanations regarding the internal flow and structure of the code.

* :doc:`The State Machine <brain/stateMachine>`

  - Detailed guide on adding new modes, transitions, and using the State Machine.

Alternative Projects
--------------------

There are two alternative implementations: **Startup_c** and **Brain_ROS**.  
However, **neither is currently maintained**, so if you choose to develop using one of them, you will need to adapt it using the information provided in this documentation.

Overview
--------

This documentation describes the **Brain** project, which runs on the Raspberry Pi.  
It simplifies the startup of your autonomous vehicle by providing:

- Basic built-in functionalities  
- A clear structure for adding your own modules  
- APIs for interacting with the **V2X systems**

Everything in the project can be tuned or extended according to your specific requirements.

Features
--------

The Brain project includes the following elements and mechanisms:

- **Service-like architecture** based on **four prioritized message queues**, where components can send messages depending on urgency.

- **Examples of parallel processes**, each using different worker threads to handle tasks concurrently.

- **A message definition class** describing all messages, their owners, and their types.

- **Subscription examples** for various message topics.

- **A gateway** that receives messages and forwards them to all subscribers (useful for testing and development).

- **Camera driver process**, capable of:

  - Adjusting camera parameters in real time (ISO, aperture, etc.)
  - Sending images in multiple formats or resolutions
  - Enabling straightforward video recording

- **Serial communication driver**, responsible for:

  - Reading data from the Nucleo board (e.g., battery status)
  - Sending commands to the Nucleo (e.g., speed commands)
  - Running read/write operations on separate threads

- **UDP-based V2X API**, receiving asynchronous data from:

  - Other cars
  - Semaphores (traffic lights)

- **TrafficCommunication server API**, which:

  - Receives location data from the localization device  
  - Sends traffic-related information back to the server

- **Asynchronous server process** for communication with the *Demo* project on the Computer:

  - Acts as a middleware between the vehicle and the demo software  
  - Receives movement commands from the PC  
  - Allows setting various parameters  
  - Forwards data from the Brain project to the dashboard for visualization

- **Message Handling**, defined as **Enumerations** (Enums) in ``src/utils/messages/allMessages.py``. Each message type specifies:

  - **Queue**: The priority queue it belongs to (e.g., Critical, General).
  - **Owner**: The component responsible for handling the message.
  - **msgID**: A unique identifier for the message.
  - **msgType**: The data type of the message payload.

- **State Machine** (``src/statemachine/stateMachine.py``), the central control unit of the vehicle. It manages the system's operating modes and transitions:

  - It listens for specific messages (like mode change requests).
  - It validates transitions to ensure safe operation.
  - It coordinates the start and stop of other processes based on the current state.

- **WorkerProcess** (``src/templates/workerprocess.py``), a standard template for creating new processes. It inherits from ``multiprocessing.Process`` and provides:

  - **Thread Management**: Built-in support for running multiple threads within the process.
  - **Message Queue Integration**: Automatic setup for reading from and writing to the inter-process communication queues.
  - **Lifecycle Management**: Standardized methods for starting, stopping, and pausing the process and its threads.

- **ThreadWithStop** (``src/templates/threadwithstop.py``), a utility class that extends ``threading.Thread``. It provides a simple mechanism to stop the thread gracefully:

  - **Inheritance**: Inherits from ``threading.Thread``.
  - **Stop Mechanism**: Includes a ``stop()`` method that sets an internal event. The thread's run loop should check this event to terminate.
  - **Usage**: Useful for creating background threads that need to be stopped cleanly when the main process exits or when a specific condition is met.