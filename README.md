VOLDEMORT (VDM)
===============

The public version of VOLDEMORT (VDM), the VA's tool for comparing the setup of any VistA system against a GOLD master. 

Notes
-----
- Two GOLDs: for OSEHRA, GOLD VistA will be a cleaned up version of FOIA and the latest version, zipped, is in the 'gold' directory of this repository. The VA's internal GOLD will also have proprietary elements not available on OSEHRA and not present in FOIA.
- VDM version 1 is scheduled for release in December 2012. Between then and now, new reports and code upgrades will be posted here.
- VDM relies on FMQL, the FileMan Query Language to download system meta data from a VistA. FMQL is available at: http://www.caregraf.org/semanticvista/fmql#fmqlrelease.

Installation and running
------------------------
1. Copy the contents of /copies and /src where you want to run the program. Let's call the location /vdm so you'll have /vdm/vistaSchema.py etc. 
2. make a subdirectory, "Caches" and copy gold/GOLD.zip in there and unzip it
3. when in /vdm type:  
    python vdm.py -v CGVISTA -f "http://vista.caregraf.org/fmqlEP" -r schema  
to run against the publicly hosted Caregraf test VistA
4. to run against your own VistA, install FMQL on it. See  
[http://repository.caregraf.org/fmql/raw-file/tip/Releases/v0.9/installFMQLV0_9.html]   
IMPORTANT: use the FMQL KIDS in /copies and not the one referenced in these install instructions. 
Then to run directly against the FMQL RPC ...  
    python vdm.py -v {LABELFORYOURVISTA} -h "itshost" -p PORT -a ACCESS -v VERIFY -r schema

