#
## VOLDEMORT (VDM) VistA Meta Reporter
#
# (c) 2012 Caregraf, Ray Group Intl
# For license information, see LICENSE.TXT
#

"""
VOLDEMORT Meta Auditer - does a VistA's meta "add up"?

TODO:
- for first files diff pass, need Builds to correlation with installs (ie/ not
just loaded builds). 
"""

import re
import json
import sys
import os
from datetime import datetime 
from vistaBuilds import VistaBuilds
from vistaSchema import VistaSchema

__all__ = ['VistaMetaAuditer']
__version__ = ".2"

class VistaMetaAuditer(object):

    """
    A class to:
    - compare different aspect's of the meta of a VistA and
    spot inconsistencies. Some are due to crude redaction of Files from FOIA etc.
    - spot missing mandatories (date of distribution for builds) etc. 
    
    Note: that VistA's meta description should match its contents except for 
    the routines file which only contains the routines loaded in builds - 
    a VistA will have routines that were loaded before the build system
    existed. This is not true of RPCs or Cross References etc whose FileMan
    descriptions are complete.
    """

    def __init__(self, schema, builds, reportsLocation="Reports"):
        """
        """
        self.__schema = schema
        self.__builds = builds
        self.__reportsLocation = reportsLocation
        if not os.path.exists(self.__reportsLocation):
            try:
                os.mkdir(self.__reportsLocation)
            except:
                raise Exception("Bad location for Meta Reports: %s ... exiting" % reportsLocation)
        
    def report(self, format="TEXT"):
    
        if format == "TEXT":
            rb = VBFormattedTextReportBuilder(self.__schema.vistaLabel, self.__reportsLocation)
            self.__buildReport(rb) 
            reportLocation = rb.flush()
            return reportLocation
            
        raise ValueError("Unknown report format %s" % format)
        
    def __buildReport(self, reportBuilder):
        """
        TODO:
        - some build files not in schema due to lack of install correlation in
        
        """
    
        # Top files in Schema vs number changed in Builds
        buildFiles = self.__builds.getFiles()
        schemaTopFiles = [re.sub(r'\_', '.', file) for file in self.__schema.listFiles(topOnly=True)]
        # List of build-only files with the builds that define them
        bfsnis = [(df, buildFiles[df]) for df in set(buildFiles).difference(schemaTopFiles)]
        reportBuilder.buildFilesNotInSchema(bfsnis)
        
        # TODO: other way - in schema but not in builds ie/ not introduced through build system
        
        # TODO: RPCs in system vs number changed in builds
        
        return
        
class VBFormattedTextReportBuilder:
    """
    See: http://www.afpy.org/doc/python/2.7/library/textwrap.html
    """
    def __init__(self, vistaLabel, reportLocation):
        self.__vistaLabel = vistaLabel
        self.__reportLocation = reportLocation   
        
    def buildFilesNotInSchema(self, bfsnis):
        print "Files in builds but not in Schema"
        print "=================================="
        print "Some like 'DENT*', 'ONC*' are redacted but not properly removed from the build system. 'COMPARE DSIR 5.2' (CGVISTA) were never installed which Builds should record. Need to delve into redaction more formally."
        for i, (df, builds) in enumerate(bfsnis, 1):
            print "%d: %s - %s" % (i, df, str(builds))
        
    def flush(self):
        pass
    
# ######################## Module Demo ##########################

def demo():
    """
    Audit GOLD
    """
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from copies.fmqlCacher import FMQLCacher
    oCacher = FMQLCacher("Caches")
    oCacher.setVista("GOLD")
    vbr = VistaMetaAuditer(VistaSchema("GOLD", oCacher), VistaBuilds("GOLD", oCacher))
    reportLocation = vbr.report(format="TEXT")
    print "Report written to %s" % reportLocation
        
if __name__ == "__main__":
    demo()