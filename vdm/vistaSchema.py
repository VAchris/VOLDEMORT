#
## VOLDEMORT (VDM) VistA Comparer
#
# (c) 2012 Caregraf, Ray Group Intl
# For license information, see LICENSE.TXT
#

"""
Module for retrieving, caching and analysing a VistA's schemas returned by FMQL

TODO - Changes/Additions Planned:
- any FMQLisms in Schema returned move in here
  - ie/ . not _ to match Builds file ids
- leverage Packages.csv (https://raw.github.com/OSEHR/VistA-FOIA/master/Packages.csv)
"""

import os
import re
import urllib
import urllib2
import json
import sys
from datetime import timedelta, datetime 
import logging

__all__ = ['VistaSchema']

class VistaSchema(object):
    """
    Access to the cached FMQL description of a Vista's Schema
    """
    
    def __init__(self, vistaLabel, fmqlCacher):
        self.vistaLabel = vistaLabel
        self.__fmqlCacher = fmqlCacher
        self.badSelectTypes = []
        self.__makeSchemas() 
        
    def __str__(self):
        return "Schema of %s" % self.vistaLabel
        
    def getNoSpecificValues(self):
        pass # TODO: ala builds etc, count specific values
        
    def listFiles(self, topOnly=False):
        if topOnly:
            topFiles = []
            for fileId in self.__schemas:
                if not self.__schemas[fileId]:
                    continue # error file
                if "parent" in self.__schemas[fileId]:
                    continue
                topFiles.append(fileId)
            return topFiles
        return self.__schemas.keys()
        
    def countFiles(self, topOnly=False):
        return len(self.listFiles(topOnly))
        
    def countPopulatedTops(self):
        """
        How many of top level files are populated - not many in FOIA/GOLD
        """
        if not self.__schemas:
            self.__makeSchemas()
        no = 0
        for fileId in self.__schemas:
            if "parent" in self.__schemas[fileId]:
                continue
            if "count" not in self.__schemas[fileId]:
                continue
            if not self.__schemas[fileId]["count"]:
                continue
            if int(self.__schemas[fileId]["count"]) > 0:
                no += 1
        return no              
        
    def getSchema(self, file):
        return self.__schemas[file]
                            
    def getFieldIds(self, file):
        sch = self.getSchema(file)
        return [field["number"] for field in sch["fields"]]
                
    def getFields(self, file, fieldIds):
        """Return in order of field number, the same order returned by FMQL"""
        sch = self.getSchema(file)
        if not len(fieldIds):
            return []
        fields = []
        for field in sch["fields"]:
            if field["number"] in fieldIds:
                fields.append(field)
        return fields
                            
    def __makeSchemas(self):
        """
        Index schema - will force caching if not already in cache
        """
        logging.info("%s: Schema - building Schema Index ..." % self.vistaLabel)
        schemas = {}
        start = datetime.now()
        for i, dtResult in enumerate(self.__fmqlCacher.describeSchemaTypes()):
            fileId = dtResult["number"]
            fmqlFileId = re.sub(r'\.', '_', fileId)
            if "error" in dtResult:
                self.badSelectTypes.append(fileId)
                continue
            schemas[fmqlFileId] = dtResult
        logging.info("%s: ... building (with caching) took %s" % (self.vistaLabel, datetime.now()-start))
        self.__schemas = schemas

# ######################## Module Demo ##########################
                       
def demo():
    """
    Simple Demo of this Module
    
    Equivalent from command line:
    $ python
    ...
    >>> from copies.fmqlCacher import FMQLCacher 
    >>> cacher = FMQLCacher("Caches")
    >>> cacher.setVista("CGVISTA") 
    >>> from vistaSchema import *
    >>> var = VistaSchema("CGVISTA", cacher)
    >>> str(vair)
    'Schema of CGVISTA'
    >>> vair.getSchema("2")
    {...
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from copies.fmqlCacher import FMQLCacher
    cacher = FMQLCacher("Caches")
    cacher.setVista("CGVISTA", "http://vista.caregraf.org/fmqlEP") 
    vair = VistaSchema("CGVISTA", cacher)
    print "Name of file 2: %s" % vair.getSchema("2")["name"]
    print vair.listFiles()
                
if __name__ == "__main__":
    demo()
