Preliminary Setup
==============================

Before you initiate the building process, ensure your environment is correctly configured.  
This guide provides a clear, step-by-step setup for all required tools and components.

.. note::

   All installations should use **Python 3.6+**.  
   Administrative privileges may be required for some steps.

1. **Python Installation**
--------------------------

Install Python version 3.6 or newer.  
You can download it from the `official Python website <https://www.python.org/downloads/>`_.

2. **CMake Installation**
-------------------------

Install CMake to manage the build process of your software.  
`Download it here <https://cmake.org/download/>`_.

3. **Ninja Installation**
-------------------------

Install Ninja using pip:

.. code-block:: bash

   pip install ninja
   python -m pip install ninja

Alternatively, you can find other installation options on the `Ninja GitHub page <https://github.com/ninja-build/ninja/wiki/Pre-built-Ninja-packages>`_.

4. **Mbed-tools Installation**
------------------------------

Install mbed-tools using pip:

.. code-block:: bash

   pip install mbed-tools
   python -m pip install mbed-tools

5. **Cross-Compiler Installation**
----------------------------------

Install a cross-compiler to build your project for the Nucleo-F401RE.  
`Download a suitable version here <https://developer.arm.com/downloads/-/gnu-rm>`_.

6. **Packages for Building Output**
-----------------------------------

Install additional packages for better output formatting:

.. code-block:: bash

   pip install prettytable intelhex


Windows Setup
~~~~~~~~~~~~~

After installing all components, verify that environment variables are set correctly.  
They should look similar to the image below:

.. image:: ../../images/embeddedplatform/envVariables.png
   :align: center
   :width: 90%

If they are missing, add the following paths manually:

.. code-block:: bash

   C:\Program Files\CMake\bin

.. code-block:: bash

   C:\Users\fill_with_your_user\AppData\Local\Programs\Python\Python3XX

.. code-block:: bash

   C:\Users\fill_with_your_user\AppData\Local\Programs\Python\Python3XX\Scripts

.. code-block:: bash

   C:\Program Files (x86)\GNU Arm Embedded Toolchain\10 2021.10\bin

.. tip::

   Replace ``fill_with_your_user`` with your actual Windows username.


Pull Project and Set up the MBED OS Version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To configure the correct MBED OS version:

1. Navigate to the project directory in your terminal.
2. Clone the repository and deploy the required MBED OS version using the commit specified in the ``mbed-os.lib`` file.

.. code-block:: bash

   cd working_directory
   git clone https://github.com/ECC-BFMC/Embedded_Platform.git
   cd path/to/your/project
   mbed-tools deploy

If you wish to use a different MBED OS version, modify the commit line in ``mbed-os.lib`` accordingly.