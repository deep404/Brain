New component
=============

When you want to implement some new feature, it's recommended to keep clean the project structure.

To facilitate the addition of new components to the project, utilize the newComponent.py script. This script automates the 
process of creating the necessary files and directories for a new component, adhering to the existing structure of the project. 

Aditionally, it adds the necessary command lines in the main.py.

**Utilizing the newComponent.py Script**

Here is how you can use the script:

1. Navigate to the directory where the newComponent.py script is located and run it.

.. code-block::

   cd Brain
   python3 newComponent.py

2. Next, input the name of the new component.
3. When prompted, input the category of the component (existing directories are "data," "gateway," "hardware," "template," or "utils").
