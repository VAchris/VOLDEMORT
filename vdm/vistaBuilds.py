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
    Lynchpin for most VistA System data reporting.
    
    TODO:
    - test install for files now in here ...
      - important: ex/ files like 19620.1 showing up in listFiles due to COMPARE DSIR 5.2
      which though loaded was never installed
    - consider pass in names NOT to load/index ie/ if in Base, why reload from remote system. ie/ depth not needed if date distrib equal.
    - pkg tagger (list of regexps - [(r'xx', PKGNAME)] ie build pkg tagger
      - "package name or prefix"  
      - will use (uri, label) form from Cache update
      - tie into Stations and Conventions for naming Class 3 builds
    - use Cacher filters like "yes/no" -> true/false, default values etc. ie. sparce hard to record on   
    - defaults in Comparer ... better done in here
    - handle cnodes generically ie/ if there properly then deref file by name into the desired label for an index. Make the indexes into one dictionary ie/ self.__indexes
    - consider link into (static) release notes
    - current version grabs everything about every build into a Cache. Instead
    grab select builds only, one by one. ex/ grab only those not in base.
    """
    def __init__(self, vistaLabel, fmqlCacher):
        self.vistaLabel = vistaLabel
        self.__fmqlCacher = fmqlCacher
        self.__indexNCleanBuilds() 
                
    def __str__(self):
        return "Builds of %s" % self.vistaLabel
        
    def getNoSpecificValues(self):
        """
        How many datapoints are available <=> number of fields in indexed entries
        
        TODO: expand for tabulation - show file/field=# 
        """
        return self.__noSpecificValues
                                          
    def listBuilds(self, installedOnly=True):
        """
        Returns list of build names in Build file order if all builds requested and
        in active/installed order if ask for 'installedOnly'
        """
        if installedOnly:
            return list(self.__buildAboutsInstalled)
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
                                
    def getFiles(self, installedOnly=True):
        """
        All files created/updated in the build system with list of builds effecting them
                
        Precise Query: DESCRIBE 9_64 IN %s CSTOP 1000
        """
        fls = defaultdict(list)
        for buildName, buildFiles in self.__buildFiles.items():
            if installedOnly and buildName not in self.__buildAboutsInstalled:
                continue
            for buildFile in buildFiles:
                # TODO: remove once FOIA GOLD has this stuff (will go from Cache too)
                if float(buildFile["vse:file_id"]) < 1.1:
                    continue
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
        
        TODO: issue of no "action". Assume "send to site" (added) vs "delete at site"?
        
        Includes Delete
        
        Precise Query: DESCRIBE 9_67 IN %s FILTER(.01=\"1-9.8\") CSTOP 1000
        """
        return [] if buildName not in self.__buildRoutines else self.__buildRoutines[buildName]
        
    def listInstallationRoutines(self, buildName):
        """
        TODO: may add to routines list and support a filter.
        
        As opposed to routines in the build, these are routines that run along with the build process. 
        - comments: "This routine will be run as part of the post-install for patch"
        - some early builds don't name their routines -- A4A7KILL in A4A7*1.01*11 is clearly a build routine. Asked to run manually.
        - Some seem to have be batch culled in FOIA (RPMS still has "DG272PT*" is in build DG*5.3*272)
        - one can call others: in RPMS where GMRAY18 is ... it calls ^GMRAY18A,^GMRAY18B,^GMRAY18C,^GMRAY18D,^GMRAY18E,^GMRAY18F,^GMRAY18G and ^GMRAY18I,^GMRAY18J,^GMRAY18K,^GMRAY18L,^GMRAY18M,^GMRAY18N,^GMRAY18P.
        """
        pass
        
    def getRPCs(self):
        pass
        
    def describeBuildRPCs(self, buildName):
        """
        From Build Component (9.67)/build component=Build (.01=1-8994)
        
        TODO: still need to add to GOLD
        
        Includes Delete
        
        Precise Query: DESCRIBE 9_67 IN %s FILTER(.01=\"1-8994\") CSTOP 1000
        """
        return [] if buildName not in self.__buildRPCs else self.__buildRPCs[buildName]
        
    def describeBuildMultiples(self, buildName):
        """
        Note that a build may contain others (multiples) and have explicit
        files/kernel etc. Only makes sense in the context of a build ie/ there is
        no "getMultiples" method.
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
        logging.info("%s: Builds - building Builds Index ..." % self.vistaLabel)
        start = datetime.now()
        self.__noSpecificValues = 0
        # TODO: move to dict of dicts. Dynamic naming.
        self.__buildAbouts = OrderedDict()
        self.__buildFiles = {}
        self.__buildMultiples = {}
        self.__buildGlobals = {}
        self.__buildRoutines = {} # from build components
        self.__buildRPCs = {} # from build components
        limit = 1000 if self.vistaLabel == "GOLD" else VistaBuilds.__ALL_LIMIT
        for i, buildResult in enumerate(self.__fmqlCacher.describeFileEntries("9_6", limit=limit, cstop=10000)):
            # logging.info("... build result %d" % i)
            dr = FMQLDescribeResult(buildResult)
            self.__noSpecificValues += dr.noSpecificValues()
            name = buildResult["name"]["value"]
            if name in self.__buildAbouts:
                raise Exception("Two builds in this VistA have the same name %s - breaks assumptions" % name)
            # Don't show FMQL itself
            if re.match(r'CGFMQL', name):
                continue
            self.__buildAbouts[name] = dr.cstopped(flatten=True)
            self.__buildAbouts[name]["vse:ien"] = buildResult["uri"]["value"].split("-")[1]
            self.__buildAbouts[name]["vse:status"] = "NEVER_INSTALLED" # overridden below
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
        self.__installAbouts = OrderedDict()
        noInstalls = 0
        for i, installResult in enumerate(self.__fmqlCacher.describeFileEntries("9_7", limit=limit, cstop=0)):
            # WV has entries with no status: usually there is a follow on with data 
            if "status" not in installResult:
                logging.error("No 'status' in install %s" % installResult["uri"]["value"])
                continue
            ir = FMQLDescribeResult(installResult)
            self.__noSpecificValues += ir.noSpecificValues()            
            name = installResult["name"]["value"]
            # Don't show FMQL itself
            if re.match(r'CGFMQL', name):
                continue
            if name not in self.__installAbouts:
                self.__installAbouts[name] = []
            self.__installAbouts[name].append(ir.cstopped(flatten=True)) 
            noInstalls += 1
            
        # Finally let's go through these installs (in order), all have status
        # and note various aspects of the build like if still installed, last install
        # time etc.
        self.__buildAboutsInstalled = OrderedDict()
        for name, installInfos in self.__installAbouts.items():
            if name not in self.__buildAbouts:
                continue # TODO: look at this: FOIA GECS*2.0*10 (corrupt FOIA?)
            for installInfo in installInfos:
                if installInfo["status"] == "Install Completed":
                    try:
                        self.__buildAbouts[name]["vse:last_install_effect"] = installInfo["install_complete_time"]
                    except: # TODO: check this further - 0LR*5.2*156 in VAVISTA
                        self.__buildAbouts[name]["vse:last_install_effect"] = installInfo["install_start_time"]
                    self.__buildAbouts[name]["vse:status"] = "INSTALLED"
                    if name in self.__buildAboutsInstalled:
                        del self.__buildAboutsInstalled[name]
                    self.__buildAboutsInstalled[name] = self.__buildAbouts[name]
                elif installInfo["status"] == "De-Installed":
                    # TODO: no obvious field for this.
                    self.__buildAbouts[name]["vse:last_install_effect"] = ""
                    self.__buildAbouts[name]["vse:status"] = "DE_INSTALLED"
                    # Should always be but just in case
                    if name in self.__buildAboutsInstalled: 
                        del self.__buildAboutsInstalled[name]
                    else:
                        logging.error("De-installing an uninstalled build: %s" % installInfo["uri"])

        logging.info("%s: Indexing, cleaning (with caching) %d builds, %d installs took %s" % (self.vistaLabel, len(self.__buildAbouts), noInstalls, datetime.now()-start))    
                        
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
    print len(buildNames)
    print len(cgbs.listBuilds(False))
    print "First build is: %s" % buildNames[0]
    print cgbs.describeBuild(buildNames[0])
    print cgbs.describeBuildFiles(buildNames[0])
    flsEffected = cgbs.getFiles()
    for i, (fid, fi) in enumerate(flsEffected.items(), 1):
        print "%d: %s - %s" % (i, fid, str(fi))
    print len(list(flsEffected))
    print "Number of specific values available: %d" % cgbs.getNoSpecificValues()
                
if __name__ == "__main__":
    demo()
