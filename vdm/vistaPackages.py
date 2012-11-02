#
## VOLDEMORT (VDM) VistA Comparer
#
# (c) 2012 Caregraf, Ray Group Intl
# For license information, see LICENSE.TXT
#

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

__all__ = ['VistaPackages']

class VistaPackages(object):
    """
    Access to the cached FMQL description of a Vista's Packages.     
    Main use is to for grouping Builds and just listing known Packages in the system. Its
    contents from dates to file lists etc aren't of use to VDM. It also notes the 
    13 Packages prioritized by the VA for VOLDEMORT.
    
    Main misconception is that Package == Application. Here it is really a "Code Bundle"
    for DIFROM transport of routines/files etc: "This file identifies the elements of a package that will be transported by the initialization routines created by DIFROM."
    
    This makes from strangeness like the same popular file (say New Person 200) being
    changed by/bundled with multiple Packages by DIFROM. Such things instead should 
    belong to shared/common 'Framework' bundles. In other words, VistA should have 
    the Kernel, Frameworks and then Applications.
    
    Little of its information is useful for Schema analysis: it namespaces (prefixes)
    for clustering/grouping routines as opposed to files. It file ranges talk to 
    (often shared) files grabbed as opposed to exclusive ownership.
    
    TODO:
    - given its limited utility, move to CSTOP 0 and cut down on the full grab. Still support but default to top level/build report support only.
    - tie in to Builds' "package_namespace_or_prefix"
    """
    def __init__(self, vistaLabel, fmqlCacher):
        self.vistaLabel = vistaLabel
        self.__fmqlCacher = fmqlCacher
        self.__indexNCleanPackages() 
        
    def __str__(self):
        return "Schema of %s" % self.vistaLabel
        
    # HELP PROCESSOR/XQH, Unwinder?
    VA_PRIORITY_13 = ["GENERIC CODE SHEET", "WOUNDED INJURED ILL WARRIORS", "MRSA INITIATIVE REPORTS", "CARE MANAGEMENT", "RPC BROKER", "ELECTRONIC SIGNATURE", "", "CAPACITY MANAGEMENT - RUM", "CAPACITY MANAGEMENT TOOLS", "SAGG PROJECT", "", "VISTALINK", "WEB SERVICES CLIENT"]  
    
    VA_NO_LONGER_USED = ["VOLUNTARY TIMEKEEPING"]
        
    # Priority packages for V1 of VDM by VA
    @property
    def listVAPriorityPackages(self):
        """
        VA's first 13 packages to merge. Note some items dropped
        """
        return self.VA_PRIORITY_13
        
    def listPackages(self):
        """
        Returns list of packages names in Package file order 
        """
        return list(self.__packageAbouts)
        
    def getNoSpecificValues(self):
        return -1
        
    def describePackage(self, packageName):
        """
        Fields of interest:
        - vse:ien
        - [description]
        - [short_description]
        - [current_version]
        - [class] "NATIONAL", "INACTIVE", "LOCAL" ... not mandatory
        
        Others are less interesting.
        
        high/low may not be very useful. PROBLEM LIST has low of 125, high of 9000011
        - [lowest_file_number] 
        - [highest_file_number]
        Current version' meaningless: In packageing package and package manifests for VistA, the VA doesn't seem to update the "current version" field. For example, 4 years of packages may separate OpenVistA from FOIA yet their packages show the same version.
        - [current_version]
        - ditto for version dates. Last date - there may be builds well beyond that.
        
        So Package establishes context for Builds but Builds are independent.
        """
        return self.__packageAbouts[packageName]
        
    def getPackageVersions(self, packageName):
        """
        Builds installed is a better guide.
        """
        return [cnode["version"] for cnode in self.__packageVersions[packageName]]
                
    def getPackageOfFile(self, fileArray):
        """
        Ex/ Patient (2/DPT) assigned to REGISTRATION as "DPT" is prefix in
        additional_prefixes of the Registration Package.
        
        TODO: move to static configuration for files AS Package prefixes
        only work for routines.
        
        Problem: 
        is for Routines but doesn't work completely for Files. 
        Ex/ Vitals (120.5) is ^GMR but prefix for Vitals Package is GMRV.
        """
        candidates = []
        for prefix in self.__prefixes:
            if len(prefix) < len(fileArray):
                continue
            if re.match(prefix, fileArray):
                candidates.append(self.__prefixes[prefix])
        # TODO: apply Excludes too
        return candidates
        
    def getPrefixes(self):
        """
        Return a list of prefixes and the package(s) they match. In combination with excluded prefixes, may assign a file to a Package.
        """
        return self.__prefixes
        
    def getExcludedPrefixes(self):
        """
        Same prefix may be excluded from multiple packages ex/ "ZZ" from TOOLKIT and ONCOLOGY.
        """
        return self.__excludedPrefixes
        
    def getDIFROMFiles(self):
        """
        For reference ...
        
        Returns list of files called out in Package definitions for DIFROM transport. Of limited use as just for telling DIFROM what to gather up. Only sometimes does it look like an Application Manifest (ex/ Oncology). Other times, it's just a 'bunch of stuff'.
        
        Package is a "bundling" concept, not a self-contained, separate applications.
        Ex/ 408.13 [u'REGISTRATION', u'INCOME VERIFICATION MATCH'] or
        44 [u'SCHEDULING', u'RECORD TRACKING'] or 200
[u'ORDER ENTRY/RESULTS REPORTING', u'OUTPATIENT PHARMACY', u'PAID', u'POLICE & SECURITY', u'PROBLEM LIST', u'SOCIAL WORK']
        But 2 only in 'INTEGRATED BILLING' where Insurance Type and Appointment fields are changed. Though assigned to Package Registration by Prefix don't appear
        in Registration's file list.
        """
        files = defaultdict(list)
        for packageName in self.__packageAbouts:
            if packageName not in self.__packageFiles:
                continue
            for packageFileAbout in self.__packageFiles[packageName]:
                files[packageFileAbout["vse:file_id"]].append(packageName)
        return files
        
    def getPackageDIFROMFiles(self, packageName):
        if packageName not in self.__packageFiles:
            return []
        return [packageFileAbout["file"] for packageFileAbout in self.__packageFiles[packageName]]
            
    __ALL_LIMIT = 200
    __CSTOP = 10000
        
    def __indexNCleanPackages(self):
        """
        Index and clean packages - will force caching if not already in cache
        """
        logging.info("%s: Packages - packaging Packages Index ..." % self.vistaLabel)
        start = datetime.now()
        self.__noSpecificValues = 0
        # TODO: move to dict of dicts. Dynamic naming.
        self.__packageAbouts = OrderedDict()
        self.__packageVersions = {}
        self.__packageFiles = {}
        self.__filesPackage = {} # from file to Package
        self.__prefixes = defaultdict(list)
        self.__excludedPrefixes = defaultdict(list)
        limit = 1000 if self.vistaLabel == "GOLD" else VistaPackages.__ALL_LIMIT
        cstop = 10 if self.vistaLabel == "GOLD" else VistaPackages.__CSTOP
        for i, packageResult in enumerate(self.__fmqlCacher.describeFileEntries("9_4", limit=limit, cstop=cstop)):
            # logging.info("... package result %d" % i)
            dr = FMQLDescribeResult(packageResult)
            self.__noSpecificValues += dr.noSpecificValues()
            name = packageResult["name"]["value"]
            if name in self.__packageAbouts:
                raise Exception("Two packages in this VistA have the same name %s - breaks assumptions" % name)
            self.__packageAbouts[name] = dr.cstopped(flatten=True)
            self.__packageAbouts[name]["vse:ien"] = packageResult["uri"]["value"].split("-")[1]
            if "file" in dr.cnodeFields():
                # catch missing 'file'. TBD: do verify version?
                self.__packageFiles[name] = [cnode for cnode in dr.cnodes("file") if "file" in cnode]
                # turn 1- form into straight file id. Note dd_number is optional
                for fileAbout in self.__packageFiles[name]:
                    # TODO: file name - want to 
                    fileAbout["vse:file_id"] = fileAbout["file"][2:]
            if "version" in dr.cnodeFields():
                self.__packageVersions[name] = [cnode for cnode in dr.cnodes("version") if "version" in cnode]
                last = self.__packageVersions[name][-1]
                if "date_installed_at_this_site" in last:
                    self.__packageAbouts[name]["vse:last_installed"] = last["date_installed_at_this_site"]
            # Should only be one package per main
            if "prefix" in packageResult:
                if packageResult["prefix"]["value"] in self.__prefixes:
                    raise Exception("Expected main prefix to belong to only one package but at least two have it - %s in %s and %s" % (packageResult["prefix"]["value"], self.__prefixes[packageResult["prefix"]["value"]][0], name))
                self.__prefixes[packageResult["prefix"]["value"]].append((name, True))
            # ie/ to go along with 'prefix', gathered additional and excluded
            # ex/ of DPT to include File PATIENT in Registration.
            if "additional_prefixes" in dr.cnodeFields():
                for additional in [cnode["additional_prefixes"] for cnode in dr.cnodes("additional_prefixes") if "additional_prefixes" in cnode]:
                    # has to be an array ie/ same prefix -> > 1 pkg 
                    # ex/ XPD to KERNEL and KIDS
                    self.__prefixes[additional].append((name, False))
            # ex/ "PSZ" for "PS" package says "PSZ" isn't in "PS" scope.
            if "excluded_name_space" in dr.cnodeFields():
                for excluded in [cnode["excluded_name_space"] for cnode in dr.cnodes("excluded_name_space") if "excluded_name_space" in cnode]:
                    # can have > 1 PKG ex/ "ZZ" in ONCOLOGY and TOOLKIT
                    self.__excludedPrefixes[excluded].append(name)
                
        logging.info("%s: Indexing, cleaning (with caching) %d packages took %s" % (self.vistaLabel, len(self.__packageAbouts), datetime.now()-start))
        
# ######################## Module Demo ##########################
                       
def demo():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from copies.fmqlCacher import FMQLCacher
    cacher = FMQLCacher("Caches")
    cacher.setVista("GOLD", fmqlEP="http://vista.caregraf.org/fmqlEP")
    cgps = VistaPackages("GOLD", cacher)
    for i, packageName in enumerate(cgps.listPackages(), 1):
        packageAbout = cgps.describePackage(packageName)
        print "%d. %s - %s - %s - %s" % (i, packageName, packageAbout["class"] if "class" in packageAbout else "NONE", packageAbout["current_version"] if "current_version" in packageAbout else "NONE", "" if "vse:last_installed" not in packageAbout else packageAbout["vse:last_installed"])
                    
if __name__ == "__main__":
    demo()