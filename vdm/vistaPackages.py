#
## VOLDEMORT (VDM) VistA Comparer
#
# (c) 2012 Caregraf, Ray Group Intl
# For license information, see LICENSE.TXT
#

"""
TODO: do before final rev of VistA Schema Changes Report ie/ over time report. Also may tie packages back to Schema report itself (ie/ let Schema do surface level package grab for name spaces)

Package dates from DIFROM (pre KIDS) time. It records the version of a package, their templates, files and namespaces.

From walk:
- current_version == latest full version in version multiple. There may be subsequent patches. 
  - ROOM FOR INCONSIST: make sure this is true
- for prefix, need prefix + additional prefixes less excluded (sub prefixes not to consider)
  - ROOM FOR INCONSIST: make sure pkg prefix assertions don't overlap
- for high low range: whole numbers. Then actual files listed under File (all appear to be top files)
  - ROOM FOR INCONSIST: check that all files in system in number range are explicitly under File multiple
- ignore: 
  - environment check/post_init etc dates in 9_4 itself. Seem to be from first install only.
  
Calculate:
- files in KIDS vs list of files EXPLICITLY given in Packages.

TODO - Old Notes (work through):
- Current version' meaningless: In building package and build manifests for VistA, the VA doesn't seem to update the "current version" field. For example, 4 years of builds may separate OpenVistA from FOIA yet their packages show the same version.
- Frozen Packages: packages whose latest FOIA builds are more than two years old or which lack builds appear to be frozen/in maintenance or no longer in active use. Examples include NDBI
- Real VistAs have many local packages/builds
- OSEHRA missing packages: OSEHRA's code base is missing some FOIA packages. Examples include VISIT TRACKING (VSIT), PHARMACY (PS). Note that though the packages are in FOIA's package file, they have probably been deprecated.
- FOIA has packages, builds and installs for "prohibited copyright code": in the FOIA build list, the VA lists DENT builds as "PROHIBITED FROM FOIA DUE TO COPYRIGHT" and says they are not installed. However, FOIA has all four of the latest builds, DENT*1.2*57, DENT*1.2*58, DENT*1.2*60, DENT*1.2*61 (Install: 9_7-8366) in its package, build and install files. But the latest DENT routines ARE NOT in the Routines (9.8) file, so the code must be purged after install - the VA VISTA has the same setup but isn't purged so the latest DENT routines are in its Routines file. It appears that despite its manifest, the VA installs the builds and then hacks out the routines and custom files. One file purged is the DENTAL CPT CODE MAPPING (schema:228) and deleting it leaves (hanging) references
"""

import os
import re
import urllib
import urllib2
import json
import sys
from datetime import timedelta, datetime 
import logging

__all__ = ['VistaSchema']

class VistaPackages(object):
    """
    Access to the cached FMQL description of a Vista's Packages.
    """
    def __init__(self, vistaLabel, fmqlCacher):
        self.vistaLabel = vistaLabel
        self.__fmqlCacher = fmqlCacher
        self.__makePackages() 
        
    def __str__(self):
        return "Schema of %s" % self.vistaLabel
        
    def packageOfFile(self, fileId, fileName):
        """
        May match by file range OR by namespace
        """

# ######################## Module Demo ##########################
                       
def demo():
    pass
                
if __name__ == "__main__":
    demo()