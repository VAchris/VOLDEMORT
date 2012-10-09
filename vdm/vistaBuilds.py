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
      - date stamps from that
    - pkg tagger (list of regexps - [(r'xx', PKGNAME)] ie build pkg tagger
      - "package name or prefix"
    - current version grabs everything about every build into a Cache. Instead
    grab select builds only, one by one. ex/ grab only those not in base.
    """

    def __init__(self, vistaLabel, fmqlCacher):
        self.vistaLabel = vistaLabel
        self.__fmqlCacher = fmqlCacher
        self.__indexNCleanBuilds() 
                
    def __str__(self):
        return "Builds of %s" % self.vistaLabel
                                          
    def listBuilds(self):
        """
        Returns list of build names in Build file order
        """
        return list(self.__buildAbouts)
        
    def describeBuild(self, buildName):
        """
        Fields of interest:
        - vse:ien
        - [type] "SINGLE PACKAGE", "MULTI-PACKAGE", "GLOBAL PACKAGE"
        - [track_package_nationally]
        - [date_distributed]
        - [package_file_link]
        - [description_of_enhancements]
        Others are less interesting.
        """
        return self.__buildAbouts[buildName]
                                
    def getFiles(self):
        """
        All files created/updated in the build system with list of builds effecting them
                
        Precise Query: DESCRIBE 9_64 IN %s CSTOP 1000
        """
        fls = defaultdict(list)
        for buildName, buildFiles in self.__buildFiles.items():
            for buildFile in buildFiles:
                fls[buildFile["vse:file_id"]].append(buildName)
        return fls
                
    def describeBuildFiles(self, buildName):
        """
        From Build (9.6)/File (9.64)
        
        Fields:
        vse:file_id (from 'file')
        data_comes_with_file
        send_full_or_partial_dd
        update_the_data_dictionary
        sites_data: overwrite etc.
        ... others less interesting
        
        TODO: need to preserve order of builds (out of order now)
        """
        # file fields with: set(field for fis in self.__buildFiles.values() for fi in fis for field in fi)
        return [] if buildName not in self.__buildFiles else self.__buildFiles[buildName]
        
    def getGlobals(self):
        pass
        
    def describeBuildGlobals(self, buildName):
        """        
        TODO: may remove as doesn't seem to be in any builds (ala GLOBAL BUILD option in 'type')
        """
        return [] if buildName not in self.__buildGlobals else self.__buildGlobals[buildName]
                        
    def getRoutines(self):
        pass
        
    def describeBuildRoutines(self, buildName):
        """
        From Build Component (9.67)/build component=Build (.01=1-9.8)
        
        Includes Delete
        
        Precise Query: DESCRIBE 9_67 IN %s FILTER(.01=\"1-9.8\") CSTOP 1000
        """
        return [] if buildName not in self.__buildRoutines else self.__buildRoutines[buildName]
        
    def getRPCs(self):
        pass
        
    def describeBuildRPCs(self, buildName):
        """
        From Build Component (9.67)/build component=Build (.01=1-8994)
        
        Includes Delete
        
        Precise Query: DESCRIBE 9_67 IN %s FILTER(.01=\"1-8994\") CSTOP 1000
        """
        return [] if buildName not in self.__buildRPCs else self.__buildRPCs[buildName]
        
    def describeBuildMultiples(self, buildName):
        """
        Note that a build may contain others (multiples) and have explicit
        files/kernel etc. 
        """
        return [] if buildName not in self.__buildMultiples else self.__buildMultiples[buildName]
        
    __ALL_LIMIT = 200
                
    def __indexNCleanBuilds(self):
        """
        Index and clean builds - will force caching if not already in cache
        
        CNodes: only see ...
        'required_build', u'install_questions', u'multiple_build', u'file', 'build_components', u'package_namespace_or_prefix' 
        but no "global"
        """
        start = datetime.now()
        types = {}
        self.__buildAbouts = OrderedDict()
        cfields = {}
        self.__buildFiles = {}
        self.__buildMultiples = {}
        self.__buildGlobals = {}
        self.__buildRoutines = {} # from build components
        self.__buildRPCs = {} # from build components
        self.__buildBadMeta = {} # note bad meta
        limit = 1000 if self.vistaLabel == "GOLD" else VistaBuilds.__ALL_LIMIT
        for buildResult in self.__fmqlCacher.describeFileEntries("9_6", limit=limit, cstop=10000):
            dr = FMQLDescribeResult(buildResult)
            name = buildResult["name"]["value"]
            if name in self.__buildAbouts:
                raise Exception("Two builds in this VistA have the same name %s - breaks assumptions" % name)
            # Don't show FMQL itself
            if re.match(r'CGFMQL', name):
                continue
            self.__buildAbouts[name] = dr.cstopped(flatten=True)
            for cfield in dr.cnodeFields():
                cfields[cfield] = ""
            self.__buildAbouts[name]["vse:ien"] = buildResult["uri"]["value"].split("-")[1]
            if "file" in dr.cnodeFields():
                # catch missing 'file'. TBD: do verify version?
                self.__buildFiles[name] = [cnode for cnode in dr.cnodes("file") if "file" in cnode]
                # turn 1- form into straight file id. Note dd_number is optional
                for fileAbout in self.__buildFiles[name]:
                    fileAbout["vse:file_id"] = fileAbout["file"][2:]
            if "global" in dr.cnodeFields():
                self.__buildGlobals[name] = [cnode for cnode in dr.cnodes("global") if "global" in cnode]
            if "multiple_build" in dr.cnodeFields():                
                self.__buildMultiples[name] = [cnode for cnode in dr.cnodes("multiple_build") if "multiple_build" in cnode]
            # TODO: required build for tracing if want to be full Build analysis framework
            if "package_namespace_or_prefix" in dr.cnodeFields():
                pass # may join?
            # Strange structure: entry for all possibilities but only some have data
            if "build_components" in dr.cnodeFields():
                bcs = dr.cnodes("build_components")
                for bc in bcs:
                    if "entries" not in bc:
                        continue
                    if bc["build_component"] == "1-8994":
                        self.__buildRPCs[name] = bc["entries"] 
                    if bc["build_component"] == "1-9.8":
                        self.__buildRoutines[name] = bc["entries"]
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
    buildNames = cgbs.listBuilds()
    print "First build is: %s" % buildNames[0]
    print cgbs.describeBuild(buildNames[0])
    print cgbs.describeBuildFiles(buildNames[0])
    flsEffected = cgbs.getFiles()
    for i, (fid, fi) in enumerate(flsEffected.items(), 1):
        print "%d: %s - %s" % (i, fid, str(fi))
    print len(list(flsEffected))
                
if __name__ == "__main__":
    demo()
