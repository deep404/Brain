New component
=============

When you want to implement some new feature, it's recommended to keep clean the project structure. With this in mind, you will notice that the "include"
and the "source" directory are following the same structure, ".hpp" files being under the the "include" and ".cpp" files under source. 

To simplify the addition of new components, use the ``newComponent.py`` script.  
This script automatically creates the required files and directories, following the existing project structure.

Using the ``newComponent.py`` Script
------------------------------------

Follow these steps to create a new component:

1. Navigate to the directory where the newComponent.py script is located (should be inside the project directory).

.. code-block::

   Embedded_Platform\newComponent\newComponent.py

2. Run the script in a terminal or IDE.
3. Enter the **category** of the component (options: ``brain``, ``driver``, ``periodics``, ``utils``).
4. Enter the **name** of the new component.
5. Choose whether to add a **serial callback command** (see `the related section here <https://bosch-future-mobility-challenge-documentation.readthedocs-hosted.com/data/embeddedplatform/debugging.html#the-commands-sent-are>`_).

.. note::

   The script ``newComponent.py`` and the flashing tool were **not designed for Linux usage**.  
   Correct functionality on Linux is therefore **not guaranteed**