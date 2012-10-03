#
## VOLDEMORT (VDM) VistA Comparer
#
# (c) 2012 Caregraf, Ray Group Intl
# For license information, see LICENSE.TXT
#

"""
Module for retrieving, caching and analysing a VistA's builds returned by FMQL 
"""

import os
import re
import urllib
import urllib2
import json
import sys
from datetime import timedelta, datetime 
import logging
from collections import OrderedDict, defaultdict
from copies.fmqlCacher import FMQLDescribeResult

__all__ = ['VistaBuilds']

class VistaBuilds(object):
    """
    TODO:
    - bring 9.7 install in here too ie/ Builds and Installs.
    - pkg tagger (list of regexps - [(r'xx', PKGNAME)] ie build pkg tagger
    - current version grabs everything about every build into a Cache. Instead
    grab select builds only, one by one. ex/ grab only those not in base.
    """

    def __init__(self, vistaLabel, fmqlCacher):
        self.vistaLabel = vistaLabel
        self.__fmqlCacher = fmqlCacher
        self.__indexNCleanBuilds() 
                
    def __str__(self):
        return "Builds of %s" % self.vistaLabel
                          
    def getBuildAbouts(self):
        """
        A Summary of each build, returned in load order.
        """
        return self.__buildAbouts
        
    def getBuildFiles(self, buildId):
        """
        From Build (9.6)/File (9.64)
        
        TODO: need to preserve order of builds (out of order now)
        """
        return self.__buildFiles[buildId]
        
    def getFiles(self):
        """
        All files effected with play by play effect of each (installed) build
        
        Precise Query: DESCRIBE 9_64 IN %s CSTOP 1000
        """
        fls = defaultdict(list)
        for buildId, buildFiles in self.__buildFiles.items():
            for buildFile in buildFiles:
                # TODO: centralize this and restatement of values
                if "file" not in buildFile:
                    logging.error("No 'file' in %s" % buildFile)
                    continue
                flId = buildFile["file"][2:] # get rid of 1-
                fls[flId].append(buildFile)
        return fls
        
    def getBuildGlobals(self, buildId):
        """
        Precise Query: DESCRIBE 9_67 IN %s FILTER(.01=\"1-8994\") CSTOP 1000
        """
        pass
        
    def getGlobals(self):
        pass
        
    def getBuildRoutines(self, buildId):
        """
        From Build Component (9.67)/build component=Build (.01=1-9.8)
        
        Includes Delete
        
        Precise Query: DESCRIBE 9_67 IN %s FILTER(.01=\"1-9.8\") CSTOP 1000
        """
        return self.__buildRoutines[buildId]
        
    def getRoutines(self):
        pass
                
    def getBuildRPCs(self, buildId):
        """
        From Build Component (9.67)/build component=Build (.01=1-8994)
        
        Includes Delete
        
        Precise Query: DESCRIBE 9_67 IN %s FILTER(.01=\"1-8994\") CSTOP 1000
        """
        return self.__buildRPCs[buildId]
        
    def getRPCs(self):
        pass
        
    __ALL_LIMIT = 200
                
    def __indexNCleanBuilds(self):
        """
        Index and clean builds - will force caching if not already in cache
        """
        start = datetime.now()
        self.__buildAbouts = OrderedDict()
        self.__buildFiles = {}
        self.__buildMultiples = {}
        self.__buildGlobals = {}
        self.__buildRoutines = {} # from build components
        self.__buildRPCs = {} # from build components
        limit = 1000 if self.vistaLabel == "GOLD" else VistaBuilds.__ALL_LIMIT
        for buildResult in self.__fmqlCacher.describeFileEntries("9_6", limit=limit, cstop=10000):
            dr = FMQLDescribeResult(buildResult)
            id = buildResult["uri"]["value"]
            self.__buildAbouts[id] = dr.cstopped(flatten=True)
            if "file" in dr.cnodeFields():
                self.__buildFiles[id] = dr.cnodes("file")
            if "multiple_build" in dr.cnodeFields():
                self.__buildMultiples[id] = dr.cnodes("multiple_build")
                # TODO: may not need as another codes field has this. Add as accessor
                self.__buildAbouts[id]["vse:is_multiple"] = True # synthesized
            if "package_namespace_or_prefix" in dr.cnodeFields():
                pass # may join?
            # Strange structure: entry for all possibilities but only some have data
            if "build_components" in dr.cnodeFields():
                bcs = dr.cnodes("build_components")
                for bc in bcs:
                    if "entries" not in bc:
                        continue
                    if bc["build_component"] == "1-8994":
                        self.__buildRPCs[id] = bc["entries"] 
                    if bc["build_component"] == "1-9.8":
                        self.__buildRoutines[id] = bc["entries"]
                    continue
        logging.info("%s: Indexing, cleaning (with caching) %d builds took %s" % (self.vistaLabel, len(self.__buildAbouts), datetime.now()-start))
                
# ######################## Module Demo ##########################
                       
def demo():
    """
    Simple Demo of this Module
    
    Equivalent from command line:
    $ python
    ...
    >>> from copies.fmqlCacher import FMQLCacher 

    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from copies.fmqlCacher import FMQLCacher
    cacher = FMQLCacher("Caches")
    cacher.setVista("CGVISTA", fmqlEP="http://vista.caregraf.org/fmqlEP")
    cgbs = VistaBuilds("CGVISTA", cacher)
    cacher = FMQLCacher("Caches")
    cacher.setVista("GOLD")
    gbs = VistaBuilds("GOLD", cacher)   
    print "Number Builds in CG: %d, in GOLD: %d" % (len(cgbs.getBuildAbouts()), len(gbs.getBuildAbouts()))
    gbsFiles = gbs.getFiles()
    print "%d Files changed in GOLD builds: %s" % (len(gbsFiles), sorted(list(gbsFiles)))
                
if __name__ == "__main__":
    demo()
