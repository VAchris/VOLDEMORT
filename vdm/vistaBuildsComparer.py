#
## VOLDEMORT (VDM) VistA Comparer
#
# (c) 2012 Caregraf, Ray Group Intl
# For license information, see LICENSE.TXT
#

"""
VOLDEMORT Builds Comparison Report Generator

TODO:
- package namespace or prefix note
"""

import re
import json
import sys
import os
import cgi
from datetime import datetime 
from vistaBuilds import VistaBuilds
from vdmU import HTMLREPORTHEAD, HTMLREPORTTAIL, WARNING_BLURB

__all__ = ['VistaBuildsComparer']
__version__ = ".2"

class VistaBuildsComparer(object):

    """
    A class to produce a report the compares a VistA against a baseline VistA.
    
    TODO: 
    - dynamic chart example ie/ not HTML but a simple "demo" of number of builds
    installed. 
    """

    def __init__(self, baselineBuilds, otherBuilds, reportsLocation="Reports"):
        """
        @param baselineBuilds: VistaBuilds of baseline VistA. Usually "GOLD"
        @param otherBuilds: VistaBuilds of VistA being compared. Ex/ "WORLDVISTA"
        @param reportsLocation: Where to write reports. Defaults.
        """
        self.__bBuilds = baselineBuilds
        self.__oBuilds = otherBuilds
        self.__reportsLocation = reportsLocation
        if not os.path.exists(self.__reportsLocation):
            try:
                os.mkdir(self.__reportsLocation)
            except:
                raise Exception("Bad location for Comparison Reports: %s ... exiting" % reportsLocation)
        
    def compare(self, format="TEXT"):
    
        if format == "HTML":
            rb = VBHTMLReportBuilder(self.__bBuilds.vistaLabel, self.__oBuilds.vistaLabel, self.__reportsLocation)
            self.__buildReport(rb) 
            reportLocation = rb.flush()
            return reportLocation
        
        """
        if format == "TEXT":
            rb = VBFormattedTextReportBuilder(self.__bBuilds.vistaLabel, self.__oBuilds.vistaLabel, self.__reportsLocation)
        """
                    
        raise ValueError("Unknown report format %s" % format)
        
    def __buildReport(self, reportBuilder):
    
        # TODO: is this in lex order and then is BPS*1.0*10 before BPS*1.0*2
        baseBuilds = self.__bBuilds.listBuilds()
        otherBuilds = self.__oBuilds.listBuilds()
        allBuilds = sorted(set(baseBuilds).union(otherBuilds))
        baseOnlyBuilds = sorted(set(baseBuilds).difference(otherBuilds))
        otherOnlyBuilds = sorted(set(otherBuilds).difference(baseBuilds))
        commonBuilds = sorted(set(baseBuilds).intersection(otherBuilds))
                
        # With this can calculate total, baseOnly, otherOnly, both (total - baseOnly + otherOnly), oneOnly (baseOnly + otherOnly); baseMultis = base
        reportBuilder.counts(total=len(allBuilds), common=len(commonBuilds), baseTotal=len(baseBuilds), baseOnly=len(baseOnlyBuilds), otherTotal=len(otherBuilds), otherOnly=len(otherOnlyBuilds))
        
        # TODO: base on install. Move into builds ie/ a one shot () date ranges
        reportBuilder.dateRanges(self.__bBuilds.describeBuild(baseBuilds[0])["date_distributed"], self.__bBuilds.describeBuild(baseBuilds[-1])["date_distributed"], self.__oBuilds.describeBuild(otherBuilds[0])["date_distributed"], self.__oBuilds.describeBuild(otherBuilds[-1])["date_distributed"])
        
        self.__buildOneOnlyReport(reportBuilder, self.__bBuilds, baseOnlyBuilds, True)
        self.__buildOneOnlyReport(reportBuilder, self.__oBuilds, otherOnlyBuilds, False)
        
    def __buildOneOnlyReport(self, reportBuilder, builds, buildsNamesToShow, base=True):
        reportBuilder.startOneOnly(len(buildsNamesToShow), base)
        for no, buildName in enumerate(buildsNamesToShow, start=1):
            buildAbout = builds.describeBuild(buildName)
            frgrm = (len(builds.describeBuildFiles(buildName)), len(builds.describeBuildRoutines(buildName)), len(builds.describeBuildGlobals(buildName)), len(builds.describeBuildRPCs(buildName)), len(builds.describeBuildMultiples(buildName)))
            reportBuilder.oneOnly(no, buildName, buildAbout["date_distributed"] if "date_distributed" in buildAbout else "", "", "NATIONAL" if "track_package_nationally" in buildAbout and buildAbout["track_package_nationally"] == "YES" else "LOCAL", buildAbout["type"] if "type" in buildAbout else "", buildAbout["description_of_enhancements"] if "description_of_enhancements" in buildAbout else "", frgrm)
        reportBuilder.endOneOnly()        
        
class VBHTMLReportBuilder:
    """
    """
    def __init__(self, baseVistaLabel, otherVistaLabel, reportLocation):
        self.__bVistaLabel = baseVistaLabel
        self.__oVistaLabel = otherVistaLabel
        self.__reportLocation = reportLocation
                
    def counts(self, total, common, baseTotal, baseOnly, otherTotal, otherOnly):
    
        self.__countsETCMU = "<div class='report' id='counts'><h2>Build Counts</h2><dl><dt>Total/Common</dt><dd>%d/%d</dd><dt>%s Total/Unique</dt><dd>%d/%d</dd><dt>%s Total/Unique</dt><dd>%d/%d</dd>" % (total, common, self.__bVistaLabel, baseTotal, baseOnly, self.__oVistaLabel, otherTotal, otherOnly) 
        
    def dateRanges(self, baseStart, baseEnd, otherStart, otherEnd):
        
        self.__countsETCMU += "<dt>%s Dates</dt><dd>%s --> %s</dd><dt>%s Dates</dt><dd>%s --> %s</dd></dl></div>" % (self.__bVistaLabel, baseStart, baseEnd, self.__oVistaLabel, otherStart, otherEnd)
        
    def startOneOnly(self, uniqueCount, base=True):
        BASEBLURB = "%d builds are unique to %s and missing from %s." % (uniqueCount, self.__bVistaLabel, self.__oVistaLabel)
        OTHERBLURB = "%d builds are unique to %s and missing from %s." % (uniqueCount, self.__oVistaLabel, self.__bVistaLabel)
        self.__oneOnlyIsBase = base
        oneOnlyStart = "<div class='report' id='%s'><h2>Builds only in %s </h2><p>%s</p>" % ("baseOnly" if base else "otherOnly", self.__bVistaLabel if base else self.__oVistaLabel, BASEBLURB if base else OTHERBLURB)
        self.__oneOnlyItems = [oneOnlyStart]
        # TODO: add in package once there
        tblStartOne = "<table><tr><th>#</th><th>Name</th><th>Released</th><th>Installed</th><th>Scope/Type<br/># files/routines/globals/rpcs/multiples</th><th>Description</th></tr>"
        self.__oneOnlyItems.append(tblStartOne)
        
    def oneOnly(self, no, name, released, installed, scope, type, description, frgrm):
        """
        no not necessarily sequential as skip multis
        """
        self.__oneOnlyItems.append("<tr id='%s'><td>%d</td>" % (name, no))
        self.__oneOnlyItems.append("<td>%s</td>" % (name))
        self.__oneOnlyItems.append("<td>%s</td><td>%s</td>" % (released, installed))
        self.__oneOnlyItems.append("<td>%s/%s<br/>%s/%s/%s/%s/%s</td>" % (scope, type, frgrm[0], frgrm[1], frgrm[2], frgrm[3], frgrm[4]))
        # Long lines cause wrap problems
        description = cgi.escape(re.sub(r'\=\=\=\=\=\=+', '=====', description[0:1000]))
        self.__oneOnlyItems.append("<td>%s</td></tr>" % description)
        
    def endOneOnly(self):
        self.__oneOnlyItems.append("</table></div>")
        if self.__oneOnlyIsBase:
            self.__baseOnlyItems = self.__oneOnlyItems
        else:
            self.__otherOnlyItems = self.__oneOnlyItems
                                       
    def flush(self):
    
        reportHead = (HTMLREPORTHEAD % ("Build Comparison Report << VOLDEMORT", " VOLDEMORT Build Comparison Report"))
        
        blurb = "A detailed comparison of 'Builds' from two VistAs: %s ('Base') and %s ('Other'). Data drawn from files <a href='http://vista.caregraf.org/schema#9_6'>Build (9.6)</a> and <a href='http://vista.caregraf.org/schema#9_7'>Install (9.7)</a> - example build <a href='http://vista.caregraf.org/rambler#!9_6-2337'>GMRC*3.0*4s</a>/ <a href='http://vista.caregraf.org/query?fmql=DESCRIBE 9_67 IN 9_6-2337 CSTOP 100&format=HTML'>details</a>. Note that FMQL Builds (CG*) are excluded and that builds in both VistAs are ignored. This report is about builds unique to the VistAs being compared." % (self.__bVistaLabel, self.__oVistaLabel)
        
        warning = "<p><strong>Warning:</strong> %s</p>" % WARNING_BLURB if WARNING_BLURB else ""        
        # TODO: use bVistaLabel etc names
        nav = "<p>Jump to: <a href='#otherOnly'>%s Only</a> | <a href='#baseOnly'>%s Only</a></p>" % (self.__oVistaLabel, self.__bVistaLabel)
        
        reportTail = HTMLREPORTTAIL % datetime.now().strftime("%b %d %Y %I:%M%p")
                        
        reportItems = [reportHead, blurb, warning, self.__countsETCMU, nav]
        reportItems.extend(self.__otherOnlyItems)
        reportItems.extend(self.__baseOnlyItems)
        reportItems.append(reportTail)
                
        reportFileName = self.__reportLocation + "/" + "builds%s_vs_%s.html" % (re.sub(r' ', '_', self.__bVistaLabel), re.sub(r' ', '_', self.__oVistaLabel))
        with open(reportFileName, "w") as reportFile:
            for reportItem in reportItems:
                reportFile.write(reportItem)
        return reportFileName
        
class VBFormattedTextReportBuilder:
    """
    See: http://www.afpy.org/doc/python/2.7/library/textwrap.html
    """
    def __init__(self, baseVistaLabel, otherVistaLabel, reportLocation):
        self.__bVistaLabel = baseVistaLabel
        self.__oVistaLabel = otherVistaLabel
        self.__reportLocation = reportLocation    
        
    def counts(self, total, common, baseTotal, baseOnly, otherTotal, otherOnly):
                
        print "{:<24}{:^6}".format("Total Number of Builds:", total)
        print "{:<24}{:^6}".format("In Common:", common)
        print "{:<24}{:^6}".format("In Base:", baseTotal)
        print "{:<24}{:^6}".format("Only In Base:", baseOnly)
        print "{:<24}{:^6}".format("In Other:", otherTotal)
        print "{:<24}{:^6}".format("Only In Other:", otherOnly)
        
    def flush(self):
        reportFileName = self.__reportLocation + "/" + "builds%s_vs_%s.txt" % (re.sub(r' ', '_', self.__bVistaLabel), re.sub(r' ', '_', self.__oVistaLabel))
        with open(reportFileName, "w") as reportFile:
            for reportItem in reportItems:
                reportFile.write(reportItem)
        return reportFileName    
        
# ######################## Module Demo ##########################

def demo():
    """
    Demo expects GOLD to be in its Cache and runs against Caregraf's web-hosted version of OpenVistA 'CGVISTA'
    
    Running this and the result:
    $ python vistaBuildsComparer.py
    GOLD: Builds Building (with caching) took 0:00:03.548585
    CGVISTA: Builds Building (with caching) took 0:00:02.408705
    Report written to Reports/schemaGOLD_vs_CGVISTA.html
    """
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from copies.fmqlCacher import FMQLCacher
    gCacher = FMQLCacher("Caches")
    gCacher.setVista("GOLD")
    oCacher = FMQLCacher("Caches")
    oCacher.setVista("CGVISTA", "http://vista.caregraf.org/fmqlEP")
    vbr = VistaBuildsComparer(VistaBuilds("GOLD", gCacher), VistaBuilds("CGVISTA", oCacher))
    reportLocation = vbr.compare(format="HTML")
    print "Report written to %s" % reportLocation
        
if __name__ == "__main__":
    demo()
