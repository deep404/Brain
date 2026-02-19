Semaphores
==========

UDP (User Datagram Protocol) is a fast and lightweight method for sending and receiving network messages. These messages 
are often "un-targeted," meaning they may be broadcast to multiple receivers without requiring an acknowledgment or validation 
of the sender. This lack of confirmation is acceptable in cases where communication speed is essential, or when the 
sender’s identity is not important. In this context, UDP is ideal for transmitting informational messages, such as status 
updates or sensor readings, where receiving every message is not critical.


UDP is a way to rapidly send & receive on the network un-targeted messages, that generally are just informative
and don't need a validation of the sender (due to communication speed necessity or simply because there's no need to pinpoint the 
sender). It should be simply used to validate messages or states.


Each semaphore broadcasts its status at a frequency of 5 Hz. These broadcasts include the semaphore’s position on the map and 
its current state (red, yellow, or green).

Semaphore state
---------------

=======================  =============  =============  =============
Semaphore state          0              1              2
=======================  =============  =============  =============
Color                    RED            YELLOW         GREEN
=======================  =============  =============  =============

Semaphore cycle
---------------

The cycle of each semaphore is described in the table below

=============  ======  ==========  =============  ======
Start Cycle    RED     GREEN       YELLOW         RED              
=============  ======  ==========  =============  ======



To run
------

The API listens for UDP messages on port 5007. To intercept and test these messages, run the script located at src/data/Semaphores/processSemaphores.py.

For testing purposes, you can simulate the data transmission using a script found in the "Computer" project. 
Running this simulation on your computer will allow you to validate that data is being transmitted and received correctly.