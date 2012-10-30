#
## VOLDEMORT (VDM) VistA Comparer
#
# (c) 2012 Caregraf, Ray Group Intl
# For license information, see LICENSE.TXT
#

# TODO: rename "vistaSchemaOrigin.py" ... ie work out the origin of schema changes
# - tie in Builds, Packages, File version
# - may show ALL changed schemas ie/ one in "both changes" from schema report => need to make this easy to import/calculate.
# - may do packages report ala Builds report ie/ with diffs and numbers etc. ie/ can show raw diffs and then tie it together.
# TODO: BUG with .0 - 21455.0, 810.4 which isn't even in schema!
# TODO: stuff allowed ot change: OE_RE_REPORT 101_24 ala 63_04
# Still need to go through and recheck:
# - why 9000010.07 not in Build: prob cause name change was by GOLD and not OTHER! ie/ old
# - 29320.2 ... Chase bug here ... why not in some OTHER build ie/ somewhere. Go through full other list ***
# - audit 1.1. has two unique fields (deleted by GOLD) or should be in other somewhere ... search.

"""
VOLDEMORT Other VistA Differ

This module reports on the differences made by another/non-GOLD VistA.
"""

import re
import json
import sys
import os
import cgi
from datetime import datetime 
from collections import defaultdict
from vistaBuilds import VistaBuilds
from vistaSchema import VistaSchema
from vdmU import HTMLREPORTHEAD, HTMLREPORTTAIL, WARNING_BLURB

__all__ = ['VistaOtherDiffer']
__version__ = ".3"

class VistaOtherDiffer:
    """
    Shared logic with stand alone Comparers of Builds, Schema etc. This
    brings the comparison logic together but only reports the differences
    in the "Other" VistA ie/ where it made changes that are NOT in the base/GOLD
    VistA.
    
    TODO: high priority - fix up (_ -> . throughout)
    """
    def __init__(self, baselineBuilds, otherBuilds, baselineSchema, otherSchema, reportsLocation="Reports"):
        """
        TODO: may allow pass in of relevant data. That way could share with
        other report generation
        """
        self.__bBuilds = baselineBuilds
        self.__oBuilds = otherBuilds
        self.__bSchema = baselineSchema
        self.__oSchema = otherSchema
        self.__reportsLocation = reportsLocation
        if not os.path.exists(self.__reportsLocation):
            try:
                os.mkdir(self.__reportsLocation)
            except:
                raise Exception("Bad location for Comparison Reports: %s ... exiting" % reportsLocation)
        self.__analyzeBuilds()
        self.__analyzeFiles()
        
    def __analyzeBuilds(self):
        # builds installed in Other and unique to it
        baseBuilds = self.__bBuilds.listBuilds(True)
        otherBuilds = self.__oBuilds.listBuilds(True)
        self.__otherOnlyBuilds = set(otherBuilds).difference(baseBuilds)

    def __analyzeFiles(self):
        """
        TODO: see if worth putting into Schema comparer and just repeat some of that 
        logic here
        """

        # Grab the data needed for this report - files in both GOLD
        # and Other VistA but changed by that other VistA; files unique to
        # Other VistA. 

        # 1. files in both where other has added or renamed fields
        bothFiles = self.__oSchema.sortFiles(set(self.__bSchema.listFiles(True)).intersection(self.__oSchema.listFiles(True)))
        self.__bothDiffFiles = {}
        for fmqlFileId in bothFiles:
            fileId = re.sub(r'\_', '.', fmqlFileId)
            bsch = self.__bSchema.getSchema(fmqlFileId)
            bFieldIds = self.__bSchema.getFieldIds(fmqlFileId)
            osch = self.__oSchema.getSchema(fmqlFileId)
            oFieldIds = self.__oSchema.getFieldIds(fmqlFileId)
            cFieldIds = set(bFieldIds).intersection(oFieldIds)
            bcFields = self.__bSchema.getFields(fmqlFileId, cFieldIds)
            ocFields = self.__oSchema.getFields(fmqlFileId, cFieldIds)
            hasRenamedFields = False
            oHasUniqueFields = False
            for i in range(len(bcFields)):
                # Just names for now but should do type etc too
                if bcFields[i]["name"] != ocFields[i]["name"]:
                    hasRenamedFields = True
            if bFieldIds != oFieldIds:
                oNotBFieldIds = set(oFieldIds).difference(bFieldIds)
                if len(oNotBFieldIds):
                    oHasUniqueFields = True
            if oHasUniqueFields or hasRenamedFields:
                self.__bothDiffFiles[fileId] = (oHasUniqueFields, hasRenamedFields)

        # 2. top files only in other
        self.__otherOnlyFiles = self.__oSchema.dotFiles(set(self.__oSchema.listFiles(True)).difference(self.__bSchema.listFiles(True)))
                
    def report(self, format="HTML"):
    
        if format == "HTML":
            rb = VODHTMLReportBuilder(self.__bSchema.vistaLabel, self.__oSchema.vistaLabel, self.__reportsLocation)
            self.__sbReport(rb) 
            reportLocation = rb.flush()
            return reportLocation
            
        raise ValueError("Unknown report format %s" % format)
        
    def __sbReport(self, reportBuilder):
        
        #
        # Go through all "other only" builds, isolating those that
        # change files. Note the files - a 'both file' or an 'other only' file
        #
        # After this, will note files that are not in builds but are different.
        #
        otherSchDiffFiles = set(self.__otherOnlyFiles).union(self.__bothDiffFiles)

        otherOnlyBuildFiles = defaultdict(list)
        otherOnlyBuildsWithFiles = []
        for buildName in self.__otherOnlyBuilds:
            buildFiles = self.__oBuilds.describeBuildFiles(buildName)
            if not len(buildFiles):
                continue # Let's just focus on the file changers.
            otherOnlyBuildsWithFiles.append(buildName)
            for buildFile in buildFiles:
                otherOnlyBuildFiles[buildFile["vse:file_id"]].append(buildName)
                                                    
        buildNotSchFiles = set(otherOnlyBuildFiles).difference(otherSchDiffFiles)
        schemaNotBuildFiles = set(otherSchDiffFiles).difference(otherOnlyBuildFiles)
        bothSchBuildFiles = set(otherSchDiffFiles).intersection(otherOnlyBuildFiles)
        
        reportBuilder.counts(otherOnlyBuilds=len(self.__otherOnlyBuilds), otherOnlyBuildsWithFiles=len(otherOnlyBuildsWithFiles), buildNotSchFiles=len(buildNotSchFiles), schemaNotBuildFiles=len(schemaNotBuildFiles), bothSchBuildFiles=len(bothSchBuildFiles))
        
        reportBuilder.startInBoth(len(bothSchBuildFiles))
        files = sorted(bothSchBuildFiles, key=lambda x: float(x))
        for no, file in enumerate(files, 1):
            reportBuilder.both(no, file, self.__oSchema.getFileName(re.sub(r'\.', '_', str(file))), otherOnlyBuildFiles[file])
        reportBuilder.endInBoth()
        
        reportBuilder.startInSchemaOnly(len(schemaNotBuildFiles))
        files = sorted(schemaNotBuildFiles, key=lambda x: float(x))
        for no, file in enumerate(files, 1):
            reportBuilder.inSchemaOnly(no, file, self.__oSchema.getFileName(re.sub(r'\.', '_', str(file))))
        reportBuilder.endInSchemaOnly()
        
        return self.__reportsLocation      
        
class VODHTMLReportBuilder:
    """
    """
    def __init__(self, baseVistaLabel, otherVistaLabel, reportLocation):
        self.__bVistaLabel = baseVistaLabel
        self.__oVistaLabel = otherVistaLabel
        self.__reportLocation = reportLocation
                
    def counts(self, otherOnlyBuilds, otherOnlyBuildsWithFiles, buildNotSchFiles, schemaNotBuildFiles, bothSchBuildFiles):
    
        self.__countsETCMU = "<div class='report' id='counts'><h2>Counts</h2><dl><dt>Other Only Builds</dt><dd>%d, %d change files</dd><dt>Schema n' Build Changed/Schema Only/Build Only</dt><dd>%d, %d, %d</dd></dl>" % (otherOnlyBuilds, otherOnlyBuildsWithFiles, bothSchBuildFiles, schemaNotBuildFiles, buildNotSchFiles)
            
    def startInBoth(self, countFiles):
        bothStart = "<div class='report' id='filesBuilds'><h2>Files and Builds</h2><p>%d files different in the Other VistA were changed in the following builds.</p>" % (countFiles)
        tblBoth = "<table><tr><th>#</th><th>File</th><th>Builds</th></tr>"
        self.__bothItems = [bothStart, tblBoth]
        
    def both(self, no, file, fileName, buildNames):
        schemaReportId = "schema%s_vs_%s.html" % (self.__bVistaLabel, self.__oVistaLabel) + "#" + str(file)      
        self.__bothItems.append("<tr id='%s'><td>%d</td><td>%s <a href='%s'>%s</a></td><td>" % (file, no, file, schemaReportId, fileName))        
        for no, buildName in enumerate(buildNames):
            buildReportId = "builds%s_vs_%s.html" % (self.__bVistaLabel, self.__oVistaLabel) + "#" + buildName
            if no > 0:
                self.__bothItems.append(", ")
            self.__bothItems.append("<a href='" + buildReportId + "'>" + buildName + "</a>")
        self.__bothItems.append("</td></tr>")
        
    def endInBoth(self):
        self.__bothItems.append("</table></div>")                                       

    def startInSchemaOnly(self, countFiles):
        self.__inSchemaOnlyItems = ["<div class='report' id='inSchemaOnly'><h2>In Schema Only</h2>"]
        
    def inSchemaOnly(self, no, file, fileName):
        if len(self.__inSchemaOnlyItems) > 1:
            self.__inSchemaOnlyItems.append(", ")
        schemaReportId = "schema%s_vs_%s.html" % (self.__bVistaLabel, self.__oVistaLabel) + "#" + str(file)
        self.__inSchemaOnlyItems.append("<a href='" + schemaReportId + "'>" + fileName + " (" + str(file) + ")</a>")
    
    def endInSchemaOnly(self):
        self.__inSchemaOnlyItems.append("</div>")      
    
    def flush(self):
        reportHead = (HTMLREPORTHEAD % ("Schema/Builds Report << VOLDEMORT", " VOLDEMORT Schema Builds Report"))
        blurb = "<p>The unique builds in %s which changed the Schema.</p>" % (self.__oVistaLabel)
        warning = "<p><strong>Warning:</strong> %s</p>" % WARNING_BLURB if WARNING_BLURB else ""
        reportTail = HTMLREPORTTAIL % datetime.now().strftime("%b %d %Y %I:%M%p")
        
        reportItems = [reportHead, blurb, warning, self.__countsETCMU]
        reportItems.extend(self.__bothItems)
        reportItems.extend(self.__inSchemaOnlyItems)
        reportItems.append(reportTail)
                
        reportFileName = self.__reportLocation + "/" + "schemaBuilds%s_vs_%s.html" % (re.sub(r' ', '_', self.__bVistaLabel), re.sub(r' ', '_', self.__oVistaLabel))
        with open(reportFileName, "w") as reportFile:
            for reportItem in reportItems:
                reportFile.write(reportItem)
        return reportFileName
                
# ######################## Module Demo ##########################

def demo():
    
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from copies.fmqlCacher import FMQLCacher
    gCacher = FMQLCacher("Caches")
    gCacher.setVista("GOLD")
    oCacher = FMQLCacher("Caches")
    oCacher.setVista("CGVISTA", "http://vista.caregraf.org/fmqlEP")
    vod = VistaOtherDiffer(VistaBuilds("GOLD", gCacher), VistaBuilds("CGVISTA", oCacher), VistaSchema("GOLD", gCacher), VistaSchema("CGVISTA", oCacher))
    reportLocation = vod.report(format="HTML")
    print "Report written to %s" % reportLocation
        
if __name__ == "__main__":
    demo()