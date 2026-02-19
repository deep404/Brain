The State Machine
=================

Overview
--------
The State Machine is a core component that manages the operating modes of the car. It ensures thread-safe mode transitions and controls the active processes for each mode.

Adding a New Mode
-----------------
To add a new mode, you need to modify the ``SystemMode`` class in ``src/statemachine/systemMode.py``.

Add a new entry to the ``SystemMode`` Enum. Each mode defines which processes are enabled and their configuration.

.. code-block:: python

    NEW_MODE = {
        "mode": "new_mode",
        "camera": {
            "process": {
                "enabled": True, 
            },
            "thread": {
                "resolution": "720p",
            }
        },
        # ... other processes
    }

**Configuration Details:**

*   **process**: The ``enabled`` flag is actually a message sent to the process (e.g. ``processCamera``). The process uses this flag to **pause or resume** its owning threads.
*   **thread**: This dictionary is for the threads owned by the process. You can pass custom messages here, such as ``"resolution": "720p"``. 
    
    *Note: The "resolution" key is just an example. Changing this value does not automatically change the camera's actual resolution unless the thread logic is implemented to read this value and apply the change.*

Adding a Transition
-------------------
To allow transitions to your new mode, modify the ``TransitionTable`` class in ``src/statemachine/transitionTable.py``.

First, ensure you have created ``SystemMode.NEW_MODE`` as described above. Then, add the allowed transitions for each mode in the ``_TRANSITIONS`` dictionary.

You need to define:
1.  Which existing modes can transition **TO** your new mode.
2.  Which modes your new mode can transition **TO** (so you can switch out of it).

.. code-block:: python

    SystemMode.DEFAULT: { # DEFAULT is the startup mode
        "dashboard_new_button": SystemMode.NEW_MODE,
        # ...
    },
    
    # Define transitions FROM your new mode to others
    SystemMode.NEW_MODE: {
        "dashboard_default_button": SystemMode.DEFAULT,
        "dashboard_auto_button": SystemMode.AUTO,
        # ...
    }

Usage & Handling State Changes
------------------------------
To use the State Machine, you get the instance and request mode changes. Processes and threads must subscribe to state changes to react accordingly.

.. tip::
    For complete implementation details, please refer to the following files in the Brain repository:
    
    *   ``src/dashboard/processDashboard.py`` (Requesting mode changes)
    *   ``src/hardware/camera/processCamera.py`` (Handling process state changes)
    *   ``src/hardware/camera/threads/threadCamera.py`` (Handling thread state changes)

**1. Requesting a Mode Change**

This example from ``processDashboard.py`` shows how to initialize the State Machine and request a mode change.

.. code-block:: python

    from src.statemachine.stateMachine import StateMachine
    
    class processDashboard(WorkerProcess):
        def __init__(self, ...):
            # ...
            # Get the singleton instance of the State Machine
            self.stateMachine = StateMachine.get_instance()
            # ...

        def handle_driving_mode(self, dataDict):
            """Handle driving mode change request."""
            # Request a mode change. The argument is the TRANSITION NAME defined in the TransitionTable.
            self.stateMachine.request_mode(f"dashboard_{dataDict['Value']}_button")

**2. Handling State Changes in a Process**

In the process (e.g. ``processCamera.py``), you subscribe to ``StateChange`` messages in ``__init__``. The handler checks the ``enabled`` flag to pause or resume threads.

.. code-block:: python

    from src.utils.messages.allMessages import StateChange
    from src.utils.messages.messageHandlerSubscriber import messageHandlerSubscriber
    from src.statemachine.systemMode import SystemMode

    class processCamera(WorkerProcess):
        def __init__(self, queueList, ...):
            self.queuesList = queueList
            # ...
            # Subscribe to StateChange messages
            self.stateChangeSubscriber = messageHandlerSubscriber(self.queuesList, StateChange, "lastOnly", True)
            
            super(processCamera, self).__init__(self.queuesList, ...)

        # This method is automatically called by the WorkerProcess (parent class) loop
        def state_change_handler(self):
            message = self.stateChangeSubscriber.receive()
            if message is not None:
                # Access the configuration for this process in the new mode
                modeDict = SystemMode[message].value["camera"]["process"]

                if modeDict["enabled"] == True:
                    self.resume_threads()
                elif modeDict["enabled"] == False:
                    self.pause_threads()

**3. Handling State Changes in a Thread**

Threads (e.g. ``threadCamera.py``) can also subscribe to ``StateChange`` to receive custom configurations (like the "resolution" example).

.. code-block:: python

    from src.utils.messages.allMessages import StateChange
    from src.utils.messages.messageHandlerSubscriber import messageHandlerSubscriber
    from src.statemachine.systemMode import SystemMode

    class threadCamera(ThreadWithStop):
        def __init__(self, queuesList, ...):
            # ...
            self.queuesList = queuesList
            self.subscribe()
            # ...

        def subscribe(self):
            # Subscribe to StateChange messages
            self.stateChangeSubscriber = messageHandlerSubscriber(self.queuesList, StateChange, "lastOnly", True)

        # This method is automatically called by the ThreadWithStop (parent class) loop
        def thread_work(self):
            # ...
            message = self.stateChangeSubscriber.receive()
            if message is not None:
                 # Access the thread configuration
                 threadConfig = SystemMode[message].value["camera"]["thread"]
                 if "resolution" in threadConfig:
                     print(f"Requested resolution: {threadConfig['resolution']}")
                     # Apply resolution logic here...
