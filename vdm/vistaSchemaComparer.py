#
## VOLDEMORT (VDM) VistA Comparer
#
# (c) 2012 Caregraf, Ray Group Intl
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
- tie in to builds (do separate Files builds report first)
- leverages Packages support once in VistaSchema
- fill in Formatted Text and CSV reporters
- use fixed manifest of VA assigned name spaces ie/ who owns certain number ranges and arrays and highlight this information (ex/ IHS ???, MSC 21400 etc.)
"""

import re
import json
import csv
import sys
import os
from datetime import datetime 
from vistaSchema import VistaSchema
from vdmU import HTMLREPORTHEAD, HTMLREPORTTAIL, WARNING_BLURB

__all__ = ['VistaSchemaComparer']
__version__ = ".3"

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
    
        baseOnlyFiles = self.__sortFiles(set(self.__bSchema.listFiles(False)).difference(self.__oSchema.listFiles(False)))
        otherOnlyFiles = self.__sortFiles(set(self.__oSchema.listFiles(False)).difference(self.__bSchema.listFiles(False)))
        bothFiles = self.__sortFiles(set(self.__bSchema.listFiles(False)).intersection(self.__oSchema.listFiles(False)))
                                
        counts = {} # we'll count as we go and then add to the report at the end.
                
        reportBuilder.startInBoth()
        counts["noBNotOFields"] = 0
        counts["noONotBFields"] = 0
        counts["norenamedFields"] = 0
        for no, fmqlFileId in enumerate(bothFiles, start=1):
            fileId = re.sub(r'\_', '.', fmqlFileId)
            bsch = self.__bSchema.getSchema(fmqlFileId)
            osch = self.__oSchema.getSchema(fmqlFileId)
            loc = bsch["location"] if "location" in bsch else ""
            parent = bsch["parent"] if "parent" in bsch else ""
            # Labs are special - don't count for now. Will change later.
            if re.match(r'63', fileId):
                reportBuilder.both(no, fileId, bsch["name"], osch["name"], loc, parent, 0, 0, {})
                continue
            bFieldIds = self.__bSchema.getFieldIds(fmqlFileId)
            bCount = self.__safeCount(bsch)
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
                    counts["norenamedFields"] += 1
            if bFieldIds != oFieldIds:
                bNotOFieldIds = set(bFieldIds).difference(oFieldIds)
                bNotOFields = self.__bSchema.getFields(fmqlFileId, bNotOFieldIds)
                counts["noBNotOFields"] += len(bNotOFieldIds)
                oNotBFieldIds = set(oFieldIds).difference(bFieldIds)
                oNotBFields = self.__oSchema.getFields(fmqlFileId, oNotBFieldIds)
                counts["noONotBFields"] += len(oNotBFieldIds)
                reportBuilder.both(no, fileId, bsch["name"], osch["name"], loc, parent, bCount, oCount, renamedFields, len(bFieldIds), bNotOFields, len(oFieldIds), oNotBFields)
            else:
                reportBuilder.both(no, fileId, bsch["name"], osch["name"], loc, parent, bCount, oCount, renamedFields)
        reportBuilder.endBoth()
                        
        self.__buildOneOnlyReport(reportBuilder, self.__bSchema, baseOnlyFiles, True)
        
        self.__buildOneOnlyReport(reportBuilder, self.__oSchema, otherOnlyFiles, False)

        # Number of fields in a system's top files; number in files shared by both systems
        counts["baseCountFields"] = self.__countFields(self.__bSchema, self.__bSchema.listFiles(False))   
        counts["baseBothCountFields"] = self.__countFields(self.__bSchema, bothFiles)     
        counts["otherCountFields"] = self.__countFields(self.__oSchema, self.__oSchema.listFiles(False))
        counts["otherBothCountFields"] = self.__countFields(self.__oSchema, bothFiles)     
        
        allFiles = set(self.__bSchema.listFiles(False)).union(self.__oSchema.listFiles(False))
        counts["allFiles"] = len(allFiles)
        counts["bothFiles"] = len(bothFiles)
        counts["baseFiles"] = self.__bSchema.countFiles(False)
        counts["baseTops"]= self.__bSchema.countFiles(True)
        counts["baseMultiples"] = counts["baseFiles"] - counts["baseTops"]
        counts["baseOnlyFiles"] = len(baseOnlyFiles)
        counts["basePopTops"] = self.__bSchema.countPopulatedTops()
        counts["otherFiles"] = self.__oSchema.countFiles(False)
        counts["otherTops"]= self.__oSchema.countFiles(True)
        counts["otherMultiples"] = counts["otherFiles"] - counts["otherTops"]
        counts["otherOnlyFiles"] = len(otherOnlyFiles)
        counts["otherPopTops"] = self.__oSchema.countPopulatedTops()
        
        reportBuilder.counts(counts) 
                                        
    def __buildOneOnlyReport(self, reportBuilder, schema, files, base=True):
        reportBuilder.startOneOnly(len(files), base)
        for no, fmqlFileId in enumerate(files, start=1):
            fileId = re.sub(r'\_', '.', fmqlFileId)
            sch = schema.getSchema(fmqlFileId)
            if "description" in sch:
                descr = sch["description"]["value"][:300] + " ..." if len(sch["description"]["value"]) > 300 else sch["description"]["value"]
                descr = descr.encode('ascii', 'ignore') # TODO: change report save
            else:
                descr = ""
            loc = sch["location"] if "location" in sch else ""
            parent = sch["parent"] if "parent" in sch else ""
            reportBuilder.oneOnly(no, fileId, sch["name"], loc, parent, descr, noFields=len(schema.getFieldIds(fmqlFileId)), count=self.__safeCount(sch))
        reportBuilder.endOneOnly() 
        
    def __countFields(self, schema, files):
        count = 0
        for fmqlFileId in files:
            count += len(schema.getFieldIds(fmqlFileId))
        return count

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
        self.__parents = {}
        self.__loadNamespaces()
        
    def __loadNamespaces(self):
        # TODO: look at high/low
        # TODO: fix to use pkg_resources: http://peak.telecommunity.com/DevCenter/PythonEggs#accessing-package-resources
        reader = csv.DictReader(open(os.path.join(os.path.dirname(__file__), "resources/Namespaces.csv")), delimiter='\t')
        self.namespaces = {}
        for row in reader:
            self.namespaces[row["NUMBER"]] = row["NAME"]
        self.namespaces["214"] = "MEDSPHERE"
                       
    def startInBoth(self):
        bothStart = "<div class='report' id='both'><h2>Differences between Files in Both</h2><p>Files common to both VistAs that have schema as opposed to content differences. Fields unique to %s (\"missing fields\") means %s has fallen behind and is missing some builds present in %s. Fields unique to %s (\"custom fields\") means it has added custom entries not found in %s. Entries labeled \"field name mismatch\" show fields with different names in each VistA. Some mismatches are superficial name variations but many represent the use of the same field for different purposes by each system. Note that this list <span class='highlight'>does not highlight differences in Lab files</span> - local sites customize these extensively. There needs to be a separate 'lab differences' report." % (self.__bVistaLabel, self.__oVistaLabel, self.__bVistaLabel, self.__oVistaLabel, self.__bVistaLabel)
        self.__bothCompareItems = [bothStart]
        tblStartCompare = "<table><tr><th>Both #</th><th>Name/ID/Locn</th><th># Entries</th><th>Fields Missing</th><th>Custom Fields</th></tr>"
        self.__bothCompareItems.append(tblStartCompare)
                                                
    def both(self, no, id, bname, oname, location, parent, bCount, oCount, renamedFields={}, noBFields=-1, bNotOFields=[], noOFields=-1, oNotBFields=[]):
        """
        TODO: must change to handle subfiles which have no location but have a container
        """
        if parent:
            self.__parents[id] = (parent, bname)
        # only show differences - will still inc no
        # for now ignore / and _ differences. TODO: check if due to old FMQL
        bnameTest = re.sub(r'\/', '_', bname)
        onameTest = re.sub(r'\/', '_', oname)
        if not (len(bNotOFields) or len(oNotBFields) or (bnameTest != onameTest)):
            return
        self.__bothCompareItems.append("<tr id='%s'><td>%d</td>" % (id, no))
        if bnameTest == onameTest:
            self.__bothCompareItems.append("<td>%s<br/><br/>" % bname)
        else:
            self.__bothCompareItems.append("<td class='highlight'><span class='titleInCol'>File Name Mismatch</span><br/>" + bname + "<br/>" + oname + "<br/><br/>")
        if location:
            self.__bothCompareItems.append("%s &nbsp;%s</td>" % (id, self.__location(location)))
        else:
            self.__bothCompareItems.append("%s</td>" % (self.__subFileId(id, parent)))
            
        if bCount == oCount:
            if bCount == "-":
                self.__bothCompareItems.append("<td/>")
            else:
                self.__bothCompareItems.append("<td>%s</td>" % bCount)
        else:
            self.__bothCompareItems.append("<td>%s<br/>%s</td>" % (bCount, oCount))

        if re.match(r'63', id):
            self.__bothCompareItems.append("<td colspan='2'>IGNORING - Lab files always different</td></tr>")
            return

        if len(bNotOFields):
            diffFieldBlurb = "Baseline has %d unique fields out of %d" % (len(bNotOFields), noBFields)
            self.__bothCompareItems.append("<td><span class='titleInCol'>%s</span><br/>%s</td>" % (diffFieldBlurb, self.__muFields(bNotOFields)))
        else:
            self.__bothCompareItems.append("<td/>")
        if not (len(oNotBFields) or len(renamedFields.keys())):
            self.__bothCompareItems.append("<td/></tr>")   
            return 
            
        self.__bothCompareItems.append("<td class='highlight'>")
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
            fieldNumberMU = field["number"]
            # TODO: 776XXX etc which don't match. What are they? Check?
            if re.match(r'\d{6}\.?', field["number"]):
                vaStationId = re.match(r'(\d{3})', field["number"]).group(1)
                if vaStationId in self.namespaces:
                    fieldNumberMU = "<strong>" + field["number"] + " (" + self.namespaces[vaStationId] + ")</strong>"
            muFields += self.__niceFieldName(field["name"]) + " (%s)" % fieldNumberMU
        return muFields
        
    def __niceFieldName(self, fieldName):
        return re.sub(r'\_', ' ', fieldName)
        
    def endBoth(self):
        self.__bothCompareItems.append("</table></div>")
        
    def startOneOnly(self, uniqueCount, base=True):
        BASEBLURB = "%d files are unique to %s. Along with missing fields, these files indicate baseline builds missing from %s. The Build reports cover builds in more detail." % (uniqueCount, self.__bVistaLabel, self.__oVistaLabel)
        OTHERBLURB = "%d files are unique to %s. Along with custom fields added to common files, these indicate the extent of custom functionality in this VistA. Descriptions should help distinguish between files once released centrally by the VA - 'Property of the US Government ...' - and files local to the VistA being compared." % (uniqueCount, self.__oVistaLabel)
        self.__oneOnlyIsBase = base
        oneOnlyStart = "<div class='report' id='%s'><h2>Files only in %s </h2><p>%s</p>" % ("baseOnly" if base else "otherOnly", self.__bVistaLabel if base else self.__oVistaLabel, BASEBLURB if base else OTHERBLURB)
        self.__oneOnlyItems = [oneOnlyStart]
        tblStartOne = "<table><tr><th>#</th><th>ID/Locn</th><th>Name</th><th> # Fields</th><th># Entries</th><th>Description (first part)</th></tr>"
        self.__oneOnlyItems.append(tblStartOne)
        
    def oneOnly(self, no, fileId, name, location, parent, descr, noFields, count):
        self.__oneOnlyItems.append("<tr id='%s'><td>%d</td>" % (fileId, no))
        if parent:
            self.__parents[fileId] = (parent, name)
        if location:
            self.__oneOnlyItems.append("<td>%s</td><td>%s</td>" % (fileId + "<br/><br/>" + self.__location(location), name))
        else:
            self.__oneOnlyItems.append("<td>%s</td><td>%s</td>" % (self.__subFileId(fileId, parent), name))
        self.__oneOnlyItems.append("<td>%s</td><td>%s</td><td>%s</td></tr>" % (noFields, count, descr))
        
    def __subFileId(self, fileId, parent):
        ids = [fileId]
        while parent in self.__parents:
            ids.insert(0, self.__parents[parent][0])
            parent = self.__parents[parent][0]
        subFileId = ""
        indent = ""
        indentInc = "&nbsp;&nbsp;&nbsp;"
        for id in ids:
            if subFileId:
                subFileId += "<br/>"
            subFileId = subFileId + indent + id
            indent = indent + indentInc
        return subFileId
        
    def endOneOnly(self):
        self.__oneOnlyItems.append("</table></div>")
        if self.__oneOnlyIsBase:
            self.__baseOnlyItems = self.__oneOnlyItems
        else:
            self.__otherOnlyItems = self.__oneOnlyItems
        
    def __location(self, location):
        if not location:
            return ""
        locationPieces = location.split("(")
        return "<span class='marray'>%s</span>%s" % (locationPieces[0], "(" + locationPieces[1] if locationPieces[1] else "")
        
    # Change to a dict as too long for anything else.
    def counts(self, counts): 
        
        self.__countsETCMU = "<div class='report' id='counts'><h2>Schema Counts</h2><dl><dt>Overall</dt><dd>%d files, %d in both</dd><dt>%s (\"Baseline\")</dt><dd>%d files, %d tops, %d multiples, %d unique, %d populated (%.1f%%)<br/>%d fields, %d in shared files, %d unique</dd><dt>%s (\"Other\")</dt><dd>%d files, %d tops, %d multiples, <span class='highlight'>%d unique (%.1f%%)</span>, %d populated (%.1f%%)<br/>%d fields, %d in shared files, <span class='highlight'>%d unique, %d repurposed, %d custom (%.1f%%)</span></dd></dl></div>" % (counts["allFiles"], counts["bothFiles"], self.__bVistaLabel, counts["baseFiles"], counts["baseTops"], counts["baseMultiples"], counts["baseOnlyFiles"], counts["basePopTops"], round(((float(counts["basePopTops"])/float(counts["baseTops"])) * 100), 2), counts["baseCountFields"], counts["baseBothCountFields"], counts["noBNotOFields"], self.__oVistaLabel, counts["otherFiles"], counts["otherTops"], counts["otherMultiples"], counts["otherOnlyFiles"], round(((float(counts["otherOnlyFiles"])/float(counts["otherFiles"])) * 100), 2), counts["otherPopTops"], round(((float(counts["otherPopTops"])/float(counts["otherTops"])) * 100), 2), counts["otherCountFields"], counts["otherBothCountFields"], counts["noONotBFields"], counts["norenamedFields"], counts["noONotBFields"] + counts["norenamedFields"], round(((float(counts["noONotBFields"] + counts["norenamedFields"])/float(counts["otherBothCountFields"])) * 100), 2)) 
                                
    def flush(self):
    
        reportHead = (HTMLREPORTHEAD % ("Schema Comparison Report << VOLDEMORT", " VOLDEMORT Schema Comparison Report"))
        blurb = "<p>Compare two VistA versions, %s ('Other') against %s ('Baseline'). This report shows which files and fields are shared and which are exclusive to one or other VistA. For each file, the report also gives a count of its entries as reported by its FileMan. The most relevant information is highlighted in grey.</p>" % (self.__oVistaLabel, self.__bVistaLabel)
        warning = "<p><strong>Warning:</strong> %s</p>" % WARNING_BLURB if WARNING_BLURB else ""
        nav = "<p>Jump to: <a href='#counts'>Counts</a> | <a href='#both' class='highlight'>In Both</a> | <a href='#%s' class='highlight'>%s Only</a> | <a href='#%s'>%s Only</a></p>" % ("otherOnly", self.__oVistaLabel, "baseOnly", self.__bVistaLabel)
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
    """
    See: http://www.afpy.org/doc/python/2.7/library/textwrap.html
    
    Also: %*s and max(len(w) for w in x) ie. set width to fit biggest
    """
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
    from copies.fmqlCacher import FMQLCacher
    gCacher = FMQLCacher("Caches")
    gCacher.setVista("GOLD")
    oCacher = FMQLCacher("Caches")
    oCacher.setVista("CGVISTA", "http://vista.caregraf.org/fmqlEP")
    vsr = VistaSchemaComparer(VistaSchema("GOLD", gCacher), VistaSchema("CGVISTA", oCacher))
    reportLocation = vsr.compare(format="HTML")
    print "Report written to %s" % reportLocation
        
if __name__ == "__main__":
    demo()
