# lightingminion
Cedar's Lighting minion controls light fixtures via [OpenLighting](http://openlighting.org/ola/). 

Requirements
============

* OLA
* OLA's Python libraries
* Python (2 or 3)
* python-meteor
 
On Debian/Ubuntu, dependencies can be installed with the commands:

    sudo apt-get install ola ola-python python3 python3-pip
    sudo pip3 install python-meteor
    
Usage
=====
Once OLA has been installed and configured, make a copy of settings.json.example with the filename of your choice. Edit the copied file and change the server URL to your Cedar server's address. Then run:

    python lightingminion.py <config file>
    
After it connects, it will appear under Cedar's Minions page under the title 'New lighting minion', where it can be configured as desired.
