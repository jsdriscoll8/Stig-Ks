# Stig-Ks-Master
Simplifies RHEL ISO configuration - allows for effortless repackaging with kickstarts.

## Requirements
No special environment is required. Any 3.10+ version of Python will work from either the command line or your preferred IDE. The program must be run in a Debian variant, whether natively or in WSL. 

The program will automatically apt install three required libraries related to ISO creation: xorriso, isolinux, and genisoimage.

## Running
* Run main.py. The program begins by asking if you would like to mount and unpack the ISO, copying its files to a temporary location of your choice. Otherwise, you may select the location of the .iso and its files if it has already been extracted.
* Next, select a kickstart from the /kickstarts folder, or provide a path to a .ks file. I have provided a selection of kickstarts for various hard drive sizes - they are functionally identical except for partition sizes; these kickstarts take in manual network settings but otherwise complete installation automatically. 
* Optionally, add a %post script to the aforementioned kickstart. These postscripts run a one-shot service, pulling an Ansible playbook from a remote repository and taking care of STIG and other tasks performed after installation is complete.
* Finally, the program will repackage the ISO with the kickstart modifications. The program will verify and/or install the libraries it needs to do so, find the correct volume ID and the location of a needed binary, and then build the file to a user defined location. 

## Known Bugs and Issues
When working in WSL, issues arise when working between Windows and Linux filesystems. Beyond the severe speed penalties, remaking ISOs to & from locations in Windows has resulted in bugged or broken installations; stay within the Linux environment if you are using WSL.
