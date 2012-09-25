#
## VOLDEMORT (VDM) VistA Comparer
#
# (c) 2012 Caregraf, Ray Group Intl
# Author: Caregraf
# For license information, see LICENSE.TXT
#

"""
VOLDEMORT Schema Comparison Report Generator

Generate Schema Comparison Reports using the VistaSchema module. Formats:
- HTML
  - references Google Table Javascript which allows re-ordering by column values
- Formatted Text
- CSV (for Excel)

Note: along with VistaSchema, this module can be part of a VOLDEMORT WSGI-based Web service. Such a service would allow analysis of any VistA with FMQL that is accessible from the service.

TODO - Changes/Additions Planned:
- fmqlId and counts logic move into VistaSchema
- leverages Packages support once in VistaSchema
- fill in Formatted Text and CSV reporters
- more counts: means moving field loops up to counts
- multiples too (ie/ if file has different multiples and if shared multiples have novel fields)
- use fixed manifest of VA assigned name spaces ie/ who owns certain number ranges and arrays and highlight this information (ex/ IHS ???, MSC 21400 etc.)
"""

import re
import json
import sys
import os
from datetime import datetime 
from vistaSchema import VistaSchema

__all__ = ['VistaSchemaComparer']
__version__ = ".1"

class VistaSchemaComparer(object):

    """
    A class to produce a report the compares a VistA against a baseline VistA. 
    """

    def __init__(self, baselineSchema, otherSchema, reportsLocation="Reports"):
        """
        @param baselineSchema: VistaSchema of baseline VistA. Usually "GOLD"
        @param otherSchema: VistaSchema of VistA being compared. Ex/ "WORLDVISTA"
        @param reportsLocation: Where to write reports. Defaults.
        """
        self.__bSchema = baselineSchema
        self.__oSchema = otherSchema
        self.__reportsLocation = reportsLocation
        if not os.path.exists(self.__reportsLocation):
            try:
                os.mkdir(self.__reportsLocation)
            except:
                raise Exception("Bad location for Comparison Reports: %s ... exiting" % reportsLocation)
        
    def compare(self, format="HTML"):
    
        if format == "HTML":
            rb = VSHTMLReportBuilder(self.__bSchema.vistaLabel, self.__oSchema.vistaLabel, self.__reportsLocation)
            self.__buildReport(rb) 
            reportLocation = rb.flush()
            return reportLocation
            
        raise ValueError("Unknown report format %s" % format)
        
    # TODO - have schema return to . form and remove all of this from here
    def __sortFiles(self, fileSet):
        return sorted(fileSet, key=lambda item: float(re.sub(r'\_', ".", item)))
        
    def __sortFields(self, fieldSet):
        return sorted(fieldSet, key=lambda item: float(item["number"]))
        
    # TODO - put count logic into Schema and handle neg #'s (RPMS has a -4)
    def __safeCount(self, sch):
        """Three cases - no count, count 0 or > 0. Reduce to "-" or > 0"""
        count = "-" if "count" not in sch or sch["count"] == "" or sch["count"] == "0" else sch["count"]
        return count
        
    def __buildReport(self, reportBuilder):
        baseOnlyTopFiles = self.__sortFiles(set(self.__bSchema.listFiles(True)).difference(self.__oSchema.listFiles(True)))
        otherOnlyTopFiles = self.__sortFiles(set(self.__oSchema.listFiles(True)).difference(self.__bSchema.listFiles(True)))
        allTopFiles = self.__sortFiles(set(self.__bSchema.listFiles(True)).union(self.__oSchema.listFiles(True)))
        bothTopFiles = self.__sortFiles(set(self.__bSchema.listFiles(True)).intersection(self.__oSchema.listFiles(True)))
        
        reportBuilder.counts(allTops=len(allTopFiles),  baseTops=self.__bSchema.countFiles(True),  baseOnlyTops=len(baseOnlyTopFiles),  basePopTops=self.__bSchema.countPopulatedTops(),  otherTops=self.__oSchema.countFiles(True), otherOnlyTops=len(otherOnlyTopFiles), otherPopTops=self.__oSchema.countPopulatedTops(), bothTops=len(bothTopFiles))
        
        reportBuilder.startInBoth()
        for no, fmqlFileId in enumerate(bothTopFiles, start=1):
            fileId = re.sub(r'\_', '.', fmqlFileId)
            bsch = self.__bSchema.getSchema(fmqlFileId)
            bFieldIds = self.__bSchema.getFieldIds(fmqlFileId)
            bCount = self.__safeCount(bsch)
            osch = self.__oSchema.getSchema(fmqlFileId)
            oFieldIds = self.__oSchema.getFieldIds(fmqlFileId)
            oCount = self.__safeCount(osch)
            # Special: may only apply to RPMS but perhaps others also rename or define fields ie/ the same field is used in different ways in each VistA.
            cFieldIds = set(bFieldIds).intersection(oFieldIds)
            bcFields = self.__bSchema.getFields(fmqlFileId, cFieldIds)
            ocFields = self.__oSchema.getFields(fmqlFileId, cFieldIds)
            renamedFields = {}
            for i in range(len(bcFields)):
                # Just names for now but should do type etc too
                if bcFields[i]["name"] != ocFields[i]["name"]:
                    renamedFields[ocFields[i]["number"]] = (ocFields[i]["name"], bcFields[i]["name"]) 
            if bFieldIds != oFieldIds:
                bNotOFieldIds = set(bFieldIds).difference(oFieldIds)
                bNotOFields = self.__bSchema.getFields(fmqlFileId, bNotOFieldIds)
                oNotBFieldIds = set(oFieldIds).difference(bFieldIds)
                oNotBFields = self.__oSchema.getFields(fmqlFileId, oNotBFieldIds)
                reportBuilder.both(no, fileId, bsch["name"], osch["name"], bsch["location"], bCount, oCount, renamedFields, len(bFieldIds), bNotOFields, len(oFieldIds), oNotBFields)
            else:
                reportBuilder.both(no, fileId, bsch["name"], osch["name"], bsch["location"], bCount, oCount, renamedFields)
        reportBuilder.endBoth()
                        
        self.__buildOneOnlyReport(reportBuilder, self.__bSchema, baseOnlyTopFiles, True)
        
        self.__buildOneOnlyReport(reportBuilder, self.__oSchema, otherOnlyTopFiles, False)
                                
    def __buildOneOnlyReport(self, reportBuilder, schema, onlyTopFiles, base=True):
        reportBuilder.startOneOnly(len(onlyTopFiles), base)
        for no, fmqlFileId in enumerate(onlyTopFiles, start=1):
            fileId = re.sub(r'\_', '.', fmqlFileId)
            sch = schema.getSchema(fmqlFileId)
            if "description" in sch:
                descr = sch["description"]["value"][:300] + " ..." if len(sch["description"]["value"]) > 300 else sch["description"]["value"]
                descr = descr.encode('ascii', 'ignore') # TODO: change report save
            else:
                descr = ""
            reportBuilder.oneOnly(no, fileId, sch["name"], sch["location"], descr, noFields=len(schema.getFieldIds(fmqlFileId)), count=self.__safeCount(sch))
        reportBuilder.endOneOnly()        
    
WARNING_BLURB = "This report was generated by %s of VOLDEMORT's Schema Comparison module. This module has not been fully tested and will change regularly until VOLDEMORT is released." % __version__
    
HTMLREPORTHEAD = """<!DOCTYPE html> 
<html lang="en">
<head>
<title>%s</title>
<meta charset="utf-8" />
<link rel='stylesheet' href='http://www.caregraf.org/semanticvista/analytics/VOLDEMORT/voldemort.css' type='text/css'>
</head>
<body>
<div id="header">
<h1 id="logo">%s</h1>
</div>
<div id="reports">
"""

HTMLREPORTTAIL = """
</div><div id="footer">Powered by <a href="http://www.caregraf.org/semanticvista">FMQL</a>, generated at %s</div>
</body>
</html>"""
        
class VSHTMLReportBuilder:
    """
    TODO: 
    - pair down of "both" to highlight files that are different and just count those that the same
    - css pair down
    - consider effect of datatables (or equivalent) js on column choice
    """

    def __init__(self, baseVistaLabel, otherVistaLabel, reportLocation):
        self.__bVistaLabel = baseVistaLabel
        self.__oVistaLabel = otherVistaLabel
        self.__reportLocation = reportLocation
                
    def counts(self, allTops, baseTops, baseOnlyTops, basePopTops, otherTops, otherOnlyTops, otherPopTops, bothTops):
    
        self.__countsETCMU = "<div class='report' id='counts'><h2>Schema Counts</h2><dl><dt>Total</dt><dd>%d files</dd><dt>%s (\"Baseline\")</dt><dd>%d, %d unique, %d populated (%.1f%%)</dd><dt>%s (\"Other\")</dt><dd>%d, %d unique, %d populated (%.1f%%)</dd><dt>In Both</dt><dd>%d</dd></dl></div>" % (allTops, self.__bVistaLabel, baseTops, baseOnlyTops, basePopTops, round(((float(basePopTops)/float(baseTops)) * 100), 2), self.__oVistaLabel, otherTops, otherOnlyTops, otherPopTops, round(((float(otherPopTops)/float(otherTops)) * 100), 2), bothTops) 
       
    def startInBoth(self):
        bothStart = "<div class='report' id='both'><h2>Files in Both</h2><p>Files common to both VistAs. Any differences will be in their fields and the number of entries each VistA has. Fields unique to %s (\"missing fields\") means %s has fallen behind and is missing some builds present in %s. Fields unique to %s (\"custom fields\") means it has added custom entries not found in %s. Entries labeled \"field name mismatch\" show fields with different names in each VistA. Some mismatches are superficial name variations but many represent the use of the same field for different purposes by each system." % (self.__bVistaLabel, self.__oVistaLabel, self.__bVistaLabel, self.__oVistaLabel, self.__bVistaLabel)
        self.__bothCompareItems = [bothStart]
        tblStartCompare = "<table><tr><th>#</th><th>ID/Locn</th><th>Name</th><th># Entries</th><th>Fields Missing</th><th>Custom Fields</th></tr>"
        self.__bothCompareItems.append(tblStartCompare)
                                                
    def both(self, no, id, bname, oname, location, bCount, oCount, renamedFields={}, noBFields=-1, bNotOFields=[], noOFields=-1, oNotBFields=[]):
        """
        TODO: must change to handle subfiles which have no location but have a container
        """
        self.__bothCompareItems.append("<tr id='%s'><td>%d</td>" % (id, no))
        self.__bothCompareItems.append("<td>%s</td><td>%s</td>" % (id + "<br/>" + self.__location(location), bname if bname == oname else "<span class='titleInCol'>File Name Mismatch</span><br/>" + bname + "<br/>" + oname))
        if bCount == oCount:
            if bCount == "-":
                self.__bothCompareItems.append("<td/>")
            else:
                self.__bothCompareItems.append("<td>%s</td>" % bCount)
        else:
            self.__bothCompareItems.append("<td>%s<br/>%s</td>" % (bCount, oCount))
        # Now fields: diff em
        if len(bNotOFields):
            diffFieldBlurb = "Baseline has %d unique fields out of %d" % (len(bNotOFields), noBFields)
            self.__bothCompareItems.append("<td><span class='titleInCol'>%s</span><br/>%s</td>" % (diffFieldBlurb, self.__muFields(bNotOFields)))
        else:
            self.__bothCompareItems.append("<td/>")
        self.__bothCompareItems.append("<td>")
        if len(oNotBFields):
            diffFieldBlurb = "Other has %d unique fields out of %d" % (len(oNotBFields), noOFields)
            self.__bothCompareItems.append("<span class='titleInCol'>%s</span><br/>%s" % (diffFieldBlurb, self.__muFields(oNotBFields)))
        if len(renamedFields.keys()):
            renamedFieldBlurb = "Field Name Mismatch"
            renamedFieldsMU = ""
            renamedFieldIds = sorted(renamedFields.keys())
            for renamedFieldId in renamedFieldIds:
                if renamedFieldsMU:
                    renamedFieldsMU += "<br/>"
                renamedFieldsMU += "%s: %s (base) -- %s (other)" % (renamedFieldId, self.__niceFieldName(renamedFields[renamedFieldId][1]), self.__niceFieldName(renamedFields[renamedFieldId][0]))
            self.__bothCompareItems.append("<br/><br/><span class='titleInCol'>%s</span><br/>%s" % (renamedFieldBlurb, renamedFieldsMU))
        self.__bothCompareItems.append("</td></tr>")
        
    def __muFields(self, fields):
        muFields = ""
        for field in fields:
            if muFields:
                muFields += ", "
            muFields += self.__niceFieldName(field["name"]) + " (%s)" % field["number"]
        return muFields
        
    def __niceFieldName(self, fieldName):
        return re.sub(r'\_', ' ', fieldName)
        
    def endBoth(self):
        self.__bothCompareItems.append("</table></div>")
        
    def startOneOnly(self, uniqueCount, base=True):
        BASEBLURB = "%d files are unique to %s. Along with missing fields, these files indicate baseline builds missing from %s. The Build reports cover builds in more detail." % (uniqueCount, self.__bVistaLabel, self.__oVistaLabel)
        OTHERBLURB = "%d files are unique to %s. Along with custom fields added to common files, these indicate the extent of custom functionality in this VistA." % (uniqueCount, self.__oVistaLabel)
        self.__oneOnlyIsBase = base
        oneOnlyStart = "<div class='report' id='%s'><h2>Files only in %s </h2><p>%s</p>" % ("baseOnly" if base else "otherOnly", self.__bVistaLabel if base else self.__oVistaLabel, BASEBLURB if base else OTHERBLURB)
        self.__oneOnlyItems = [oneOnlyStart]
        tblStartOne = "<table><tr><th>#</th><th>ID/Locn</th><th>Name</th><th> # Fields</th><th># Entries</th><th>Description (first part)</th></tr>"
        self.__oneOnlyItems.append(tblStartOne)
        
    def oneOnly(self, no, fileId, name, location, descr, noFields, count):
        self.__oneOnlyItems.append("<tr id='%s'><td>%d</td>" % (fileId, no))
        self.__oneOnlyItems.append("<td>%s</td><td>%s</td>" % (fileId + "<br/>" + self.__location(location), name))
        self.__oneOnlyItems.append("<td>%s</td><td>%s</td><td>%s</td></tr>" % (noFields, count, descr))
        
    def endOneOnly(self):
        self.__oneOnlyItems.append("</table></div>")
        if self.__oneOnlyIsBase:
            self.__baseOnlyItems = self.__oneOnlyItems
        else:
            self.__otherOnlyItems = self.__oneOnlyItems
        
    def __location(self, location):
        locationPieces = location.split("(")
        return "<span class='marray'>%s</span>%s" % (locationPieces[0], "(" + locationPieces[1] if locationPieces[1] else "")
                                
    def flush(self):
    
        reportHead = (HTMLREPORTHEAD % ("Schema Comparison Report << VOLDEMORT", " VOLDEMORT Schema Comparison Report"))
        blurb = "<p>Compare two VistA versions, %s ('Other') against %s ('Baseline'). This report shows which files and fields are shared and which are exclusive to one or other VistA. For each file, the report also gives a count of its entries as reported by its FileMan.</p>" % (self.__oVistaLabel, self.__bVistaLabel)
        warning = "<p><strong>Warning:</strong> %s</p>" % WARNING_BLURB if WARNING_BLURB else ""
        nav = "<p>Jump to: <a href='#counts'>Counts</a> | <a href='#both'>In Both</a> | <a href='#%s'>%s Only</a> | <a href='#%s'>%s Only</a></p>" % ("otherOnly", self.__oVistaLabel, "baseOnly", self.__bVistaLabel)
        reportTail = HTMLREPORTTAIL % datetime.now().strftime("%b %d %Y %I:%M%p")
        
        reportItems = [reportHead, blurb, warning, nav, self.__countsETCMU]
        reportItems.extend(self.__bothCompareItems)
        reportItems.extend(self.__otherOnlyItems)
        reportItems.extend(self.__baseOnlyItems)
        reportItems.append(reportTail)
                
        reportFileName = self.__reportLocation + "/" + "schema%s_vs_%s.html" % (re.sub(r' ', '_', self.__bVistaLabel), re.sub(r' ', '_', self.__oVistaLabel))
        with open(reportFileName, "w") as reportFile:
            for reportItem in reportItems:
                reportFile.write(reportItem)
        return reportFileName
    
class VSFormattedTextReportBuilder:

    def __init__(self):
        pass
        
    def counts(self):
        # %6s etc. ie. tables
        pass
        
class VSCSVReportBuilder:

    """
    CSV or consider xlrd module
    - dialect=csv.excel
    """

    def __init__(self):
        pass
    
# ######################## Module Demo ##########################

def demo():
    """
    Demo expects GOLD to be in its Cache and runs against Caregraf's web-hosted version of OpenVistA 'CGVISTA'
    
    Running this and the result:
    $ python vistaSchemaComparer.py
    GOLD: Schema Building (with caching) took 0:00:03.548585
    CGVISTA: Schema Building (with caching) took 0:00:02.408705
    Report written to Reports/schemaGOLD_vs_CGVISTA.html
    """
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from fmqlCacher import FMQLCacher
    gCacher = FMQLCacher("Caches")
    gCacher.setVista("GOLD")
    oCacher = FMQLCacher("Caches")
    oCacher.setVista("CGVISTA", "http://vista.caregraf.org/fmqlEP")
    vsr = VistaSchemaComparer(VistaSchema("GOLD", gCacher), VistaSchema("CGVISTA", oCacher))
    reportLocation = vsr.compare(format="HTML")
    print "Report written to %s" % reportLocation
        
if __name__ == "__main__":
    demo()