VOLDEMORT (VDM)
===============
VOLDEMORT (VDM) V1 is a VistA system comparison application that leverages what every VistA knows about itself. It is written in Python and uses FMQL, the open source FileMan query mechanism to query and cache VistA system data. It compares what a VistA returns to a canonical ("GOLD") VistA definition and produces a series of "difference" reports for file schema, routines and more. VDM V1 is due for release in December 2012.

Current Work (as of 10/2/12)
----------------------------
a) framework enhancement for processing system build and install information
b) report generator for a "build difference" report
c) optimization (threading) to speed up FMQL calling. The current VDM is network I/O bound (too much detail!)
d) a standard Windows install

Installation and running
------------------------
1. Clone this repository from git

2. Go into the VOLDEMORT directory and Install the python package

        python setup.py install

   and now you can delete the repository and its directory if you like - you won't be using it again

3. Create a working directory and in there run

        python -m vdm -h

   you will see a message about VOLDERMORT setting up its cache and then see a printout of help

4. Try it ...

        python -m vdm -v CGVISTA -f "http://vista.caregraf.org/fmqlEP" -r schema  
   will run against the publicly hosted Caregraf test VistA

5. To run against your own VistA

   Install FMQL on your VistA. See  
[http://repository.caregraf.org/fmql/raw-file/tip/Releases/v0.9/installFMQLV0_9.html]   
   A copy of the FMQL KIDS is in 'fmqlkids'

   Then to run VDM directly against the FMQL RPC ...  

        python -m vdm -v LABELFORYOURVISTA -h HOST -p PORT -a ACCESS -v VERIFY -r schema

