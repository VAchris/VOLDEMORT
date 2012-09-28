VOLDEMORT (VDM)
===============

The public version of VOLDEMORT (VDM), the VA's tool for comparing the setup of any VistA system against a GOLD master. 

Notes
-----
- Two GOLDs: for OSEHRA, GOLD VistA will be a cleaned up version of FOIA and the latest version, zipped, is in the 'gold' directory of this repository. The VA's internal GOLD will also have proprietary elements not available on OSEHRA and not present in FOIA.
- VDM version 1 is scheduled for release in December 2012. Between then and now, new reports and code upgrades will be posted here.
- VDM relies on FMQL, the FileMan Query Language to download system meta data from a VistA. FMQL is available at: http://www.caregraf.org/semanticvista/fmql#fmqlrelease/ reporitory (https://github.com/caregraf/FMQL)

Installation and running
------------------------
1. Clone this repository from git
2. Go into the VOLDEMORT directory and Install the python package
    python setup.py install
   and now you can delete the repository and its directory if you like - you won't be using it again
3. Create a working directory somewhere. Let's call it 'vdm'. In 'vdm' ...
    python -m vdm -h
   you will see a message about VOLDERMORT setting up its cache and then see a printout of help
    python -m vdm -v CGVISTA -f "http://vista.caregraf.org/fmqlEP" -r schema  
   will run against the publicly hosted Caregraf test VistA
4. to run against your own VistA, install FMQL on it. See  
[http://repository.caregraf.org/fmql/raw-file/tip/Releases/v0.9/installFMQLV0_9.html]   
IMPORTANT: use the FMQL KIDS in /copies and not the one referenced in these install instructions. 
Then to run directly against the FMQL RPC ...  
    python -m vdm -v LABELFORYOURVISTA -h HOST -p PORT -a ACCESS -v VERIFY -r schema

