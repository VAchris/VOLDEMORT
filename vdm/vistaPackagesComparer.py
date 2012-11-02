#
## VOLDEMORT (VDM) VistA Comparer
#
# (c) 2012 Caregraf, Ray Group Intl
# For license information, see LICENSE.TXT
#

"""
VOLDEMORT Packages Comparison Report Generator. Really for reference from Builds
report.

TODO:
- do "SELECT ALL REFERRERS" for each so have total of builds per package or just make this the basis of a generic PackageBuild comparison report. All builds per package etc and count em.
OR
- downgrade this. Just put information in Build Comparison report.
"""

import re
import json
import sys
import os
import cgi
from datetime import datetime 
from vistaPackages import VistaPackages
from vdmU import HTMLREPORTHEAD, HTMLREPORTTAIL, WARNING_BLURB

__all__ = ['VistaPackagesComparer']
__version__ = ".3"

class VistaPackagesComparer(object):

    """
    A class to produce a report the compares a VistA against a baseline VistA.
    
    Package is nothing but a Build bundler for VDM and the report generated here just provides context for builds.
    """

    def __init__(self, baselinePackages, otherPackages, reportsLocation="Reports"):
        """
        @param baselinePackages: VistaPackages of baseline VistA. Usually "GOLD"
        @param otherPackages: VistaPackages of VistA being compared. Ex/ "WORLDVISTA"
        @param reportsLocation: Where to write reports. Defaults.
        """
        self.__bPackages = baselinePackages
        self.__oPackages = otherPackages
        self.__reportsLocation = reportsLocation
        if not os.path.exists(self.__reportsLocation):
            try:
                os.mkdir(self.__reportsLocation)
            except:
                raise Exception("Bad location for Comparison Reports: %s ... exiting" % reportsLocation)
        
    def compare(self, format="HTML"):
    
        if format == "HTML":
            rb = VPHTMLReportBuilder(self.__bPackages.listVAPriorityPackages, self.__bPackages.vistaLabel, self.__oPackages.vistaLabel, self.__reportsLocation)
            self.__packageReport(rb) 
            reportLocation = rb.flush()
            return reportLocation
        
        """
        if format == "TEXT":
            rb = VBFormattedTextReportPackageer(self.__bPackages.vistaLabel, self.__oPackages.vistaLabel, self.__reportsLocation)
        """
                    
        raise ValueError("Unknown report format %s" % format)
        
    def __packageReport(self, reportPackager):
    
        basePackages = self.__bPackages.listPackages()
        otherPackages = self.__oPackages.listPackages()

        allPackages = set(basePackages).union(otherPackages)
        baseOnlyPackages = set(basePackages).difference(otherPackages)
        otherOnlyPackages = set(otherPackages).difference(basePackages)
        commonPackages = set(basePackages).intersection(otherPackages)
                
        # With this can calculate total, baseOnly, otherOnly, both (total - baseOnly + otherOnly), oneOnly (baseOnly + otherOnly); baseMultis = base
        reportPackager.counts(total=len(allPackages), common=len(commonPackages), baseTotal=len(basePackages), baseOnly=len(baseOnlyPackages), otherTotal=len(otherPackages), otherOnly=len(otherOnlyPackages))
        
        reportPackager.valuesCounts(self.__bPackages.getNoSpecificValues(), self.__oPackages.getNoSpecificValues())
                
        self.__packageOneOnlyReport(reportPackager, self.__bPackages, baseOnlyPackages, True)
        self.__packageOneOnlyReport(reportPackager, self.__oPackages, otherOnlyPackages, False)
        
        reportPackager.startCommon(len(commonPackages))
        # Want packages in install order (of GOLD)
        for no, packageName in enumerate(self.__bPackages.listPackages(), start=1):
            if packageName not in commonPackages:
                continue
            packageAbout = self.__bPackages.describePackage(packageName)
            reportPackager.common(no, packageAbout["vse:ien"], packageName, "" if "description" not in packageAbout else packageAbout["description"])
        reportPackager.endCommon()             
        
    def __packageOneOnlyReport(self, reportPackager, packages, packageNamesToShow, base=True):
        reportPackager.startOneOnly(len(packageNamesToShow), base)
        # Want packages in install order
        for no, packageName in enumerate(packages.listPackages(), start=1):
            if packageName not in packageNamesToShow:
                continue # ie/ too many
            packageAbout = packages.describePackage(packageName)
            reportPackager.oneOnly(no, packageAbout["vse:ien"], packageName, "" if "description" not in packageAbout else packageAbout["description"])
        reportPackager.endOneOnly()        
        
class VPHTMLReportBuilder:
    """
    """
    def __init__(self, vaPriorityPackages, baseVistaLabel, otherVistaLabel, reportLocation):
        self.__vaPriorityPackages = vaPriorityPackages
        self.__bVistaLabel = baseVistaLabel
        self.__oVistaLabel = otherVistaLabel
        self.__reportLocation = reportLocation
                
    def counts(self, total, common, baseTotal, baseOnly, otherTotal, otherOnly):
    
        self.__countsETCMU = "<div class='report' id='counts'><h2>Package Counts</h2><dl><dt>Total/Common</dt><dd>%d/%d</dd><dt>%s Installed/Unique</dt><dd>%d/%d</dd><dt>%s Installed/Unique</dt><dd>%d/<span class='highlight'>%d</span></dd>" % (total, common, self.__bVistaLabel, baseTotal, baseOnly, self.__oVistaLabel, otherTotal, otherOnly) 
        
    def valuesCounts(self, baseValuesCount, otherValuesCount):
        # self.__countsETCMU += "<dt>Datapoints - Base/Other</dt><dd>%d/%d</dd>" % (baseValuesCount, otherValuesCount)
        self.__countsETCMU += "</dl>"
           
    def startOneOnly(self, uniqueCount, base=True):
        BASEBLURB = "%d packages are unique to %s and missing from %s." % (uniqueCount, self.__bVistaLabel, self.__oVistaLabel)
        OTHERBLURB = "%d packages are unique to %s and missing from %s." % (uniqueCount, self.__oVistaLabel, self.__bVistaLabel)
        self.__oneOnlyIsBase = base
        oneOnlyStart = "<div class='report' id='%s'><h2>Packages only in %s </h2><p>%s</p>" % ("baseOnly" if base else "otherOnly", self.__bVistaLabel if base else self.__oVistaLabel, BASEBLURB if base else OTHERBLURB)
        self.__oneOnlyItems = [oneOnlyStart]
        # TODO: add in package once there
        tblStartOne = "<table><tr><th>#</th><th>Name</th><th>Description</th></tr>"
        self.__oneOnlyItems.append(tblStartOne)
        
    def oneOnly(self, no, ien, name, description):
        """
        no not necessarily sequential as skip multis
        """
        self.__oneOnlyItems.append("<tr id='%s'><td>%d</td>" % (name, no))
        nameMU = name if name not in self.__vaPriorityPackages else "<span class='highlight'>" + name + "</span>"
        self.__oneOnlyItems.append("<td>%s</td>" % (nameMU))
        self.__oneOnlyItems.append("<td>%s</td>" % (description))
        self.__oneOnlyItems.append("</tr>")
        
    def endOneOnly(self):
        self.__oneOnlyItems.append("</table></div>")
        if self.__oneOnlyIsBase:
            self.__baseOnlyItems = self.__oneOnlyItems
        else:
            self.__otherOnlyItems = self.__oneOnlyItems
                                       
    def startCommon(self, count):
        BLURB = "%d packages are common to both %s and %s." % (count, self.__bVistaLabel, self.__oVistaLabel)
        start = "<div class='report' id='common'><h2>Common Packages</h2><p>%s</p>" % BLURB
        self.__commonItems = [start]
        tblStart = "<table><tr><th>#</th><th>Name</th><th>Description</th></tr>"
        self.__commonItems.append(tblStart)
        
    def common(self, no, ien, name, description):
        """
        no not necessarily sequential as skip multis
        """
        self.__commonItems.append("<tr id='%s'><td>%d</td>" % (name, no))
        nameMU = name if name not in self.__vaPriorityPackages else "<span class='highlight'>" + name + "</span>"
        self.__commonItems.append("<td>%s</td>" % (nameMU))
        self.__commonItems.append("<td>%s</td>" % (description))
        self.__commonItems.append("</tr>")
        
    def endCommon(self):
        self.__commonItems.append("</table></div>")
                                       
    def flush(self):
    
        reportHead = (HTMLREPORTHEAD % ("Package Comparison Report << VOLDEMORT", " VOLDEMORT Package Comparison Report"))
        
        blurb = "A detailed comparison of 'Packages' from two VistAs: %s ('Base') and %s ('Other')." % (self.__bVistaLabel, self.__oVistaLabel)
        
        warning = "<p><strong>Warning:</strong> %s</p>" % WARNING_BLURB if WARNING_BLURB else ""        
        # TODO: use bVistaLabel etc names
        nav = "<p>Jump to: <a href='#otherOnly'>%s Only</a> | <a href='#baseOnly'>%s Only</a> | <a href='#common'>Common</a></p>" % (self.__oVistaLabel, self.__bVistaLabel)
        
        reportTail = HTMLREPORTTAIL % datetime.now().strftime("%b %d %Y %I:%M%p")
                        
        reportItems = [reportHead, blurb, warning, self.__countsETCMU, nav]
        reportItems.extend(self.__otherOnlyItems)
        reportItems.extend(self.__baseOnlyItems)
        reportItems.extend(self.__commonItems)
        reportItems.append(reportTail)
                
        reportFileName = self.__reportLocation + "/" + "packages%s_vs_%s.html" % (re.sub(r' ', '_', self.__bVistaLabel), re.sub(r' ', '_', self.__oVistaLabel))
        with open(reportFileName, "w") as reportFile:
            for reportItem in reportItems:
                reportFile.write(reportItem)
        return reportFileName 
        
# ######################## Module Demo ##########################

def demo():
    """
    Demo expects GOLD to be in its Cache and runs against Caregraf's web-hosted version of OpenVistA 'CGVISTA'
    
    Running this and the result:
    $ python vistaPackagesComparer.py
    GOLD: Packages Packageing (with caching) took 0:00:03.548585
    CGVISTA: Packages Packageing (with caching) took 0:00:02.408705
    Report written to Reports/schemaGOLD_vs_CGVISTA.html
    """
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from copies.fmqlCacher import FMQLCacher
    gCacher = FMQLCacher("Caches")
    gCacher.setVista("GOLD")
    oCacher = FMQLCacher("Caches")
    oCacher.setVista("CGVISTA", "http://vista.caregraf.org/fmqlEP")
    vbr = VistaPackagesComparer(VistaPackages("GOLD", gCacher), VistaPackages("CGVISTA", oCacher))
    reportLocation = vbr.compare(format="HTML")
    print "Report written to %s" % reportLocation
        
if __name__ == "__main__":
    demo()
