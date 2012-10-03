#
## FMQL Cacher
#
# (c) 2012 Caregraf
#
# Apache License Version 2.0, January 2004
#

"""
Module for managing a Cache of FMQL responses. Responses can come from a full RESTful FMQL endpoint or directly from an FMQL RPC. Caches for named VistAs are managed in a named "cacheLocation" directory.

TODO - Changes/Additions Planned:
- finish thread FMQL EP calls for schema and add for 
- support read/write from ZIPs
- remove support for many Vistas at once ie/ many labels ie/ one Cacher per VistA
- support Application Proxy mechanism once added to brokerRPC
"""

import os
import re
import urllib
import urllib2
import threading
import Queue
import time
import json
import sys
import logging
from brokerRPC import RPCConnectionPool        

__all__ = ['FMQLCacher']

class FMQLCacher:
    """
    Manage Cache of FMQL responses for a named VistA. Works with both a web hosted FMQL endpoint and directly with the FMQL RPC.
    
    TODO:
    - break in two: RPC Cacher and EP Cacher
    - make it specializer FMQLAccessor which will work without a Cache
    """
    def __init__(self, cachesLocation, poolSize=5):
        self.__poolSize = poolSize
        try:
            if not os.path.exists(cachesLocation):
                os.mkdir(cachesLocation) 
        except:
            logging.critical(sys.exc_info()[0])
            raise
        self.__cachesLocation = cachesLocation
            
    def setVista(self, vistaLabel, fmqlEP="", host="", port=-1, access="", verify=""):
        self.vistaLabel = vistaLabel
        try:
            self.__cacheLocation = self.__cachesLocation + "/" + re.sub(r' ', '_', vistaLabel)
            if not os.path.exists(self.__cacheLocation):
                os.mkdir(self.__cacheLocation)
        except:
            logging.critical(sys.exc_info()[0])
            raise
        self.__fmqlEP = fmqlEP
        self.__rpcCPool = RPCConnectionPool("VistA", self.__poolSize, host, port, access, verify, "CG FMQL QP USER", RPCLogger()) if host else None     
    
    def clearCache(self, vistaLabel):
        pass
        
    def query(self, vistaLabel, query):
        """
        Dispatch and cache any query. Blocks.
        """
        queryFile = self.__cacheLocation + "/" + query + ".json"
        if os.path.isfile(queryFile):
            reply = json.load(open(queryFile, "r"))
            return reply
        if self.__fmqlEP:
            return self.__epCache(query)
        elif self.__rpcCPool:
            return self.__rpcCache(query)
        logging.critical("Don't know FMQL EP or Access/Verify for %s, so can't do <%s> - exiting" % (self.vistaLabel, str(query)))
        raise Exception("Need FMQL EP or Access/Verify")
        
    DESCRIBE_TYPE_TEMPL = "DESCRIBE TYPE %s"
        
    def describeSchemaTypes(self, schemaTypes):
        """
        Generator, returns one type at a time. 
        
        TODO:
        - change schema grab to be threaded.
        - return an iterator. Then can enumerate(x) on it.
        """
        pass
        
    def __cacheDescribeTypes(self):
        pass
        
    DESCRIBE_TEMPL = "DESCRIBE %s CSTOP %s LIMIT %d OFFSET %d"
        
    def describeFileEntries(self, file, limit=200, cstop=100):
        """
        This is a generator object that avoids the need for every one
        of the results of a query to be in memory for processing. 
                
        for result in describe(file ...):
            print result
            
        Ex time: Elapsed Time to cache file 9_6 in 35 pieces: 23.8363921642
            
        TODO: 
        - break out as iterator (__iter__) that calls this method as its
        generator, 
          for i, result in enumerate(fmqlCacher.fmqlResultIterator(query, limit))
        """
        if not self.__isDescribeCached(file, limit, cstop):
            self.__cacheDescribe(file, limit, cstop)
        offset = 0
        # Ensure all wanted are in Cache. If not, recache EVERYTHING!
        while True:
            loquery = FMQLCacher.DESCRIBE_TEMPL % (file, cstop, limit, offset)
            queryFile = self.__cacheLocation + "/" + loquery + ".json"
            if not os.path.isfile(queryFile):
                raise Exception("Thought file was in Cache but it vanished - exiting")
            reply = json.load(open(queryFile, "r"))
            logging.info("Reading - %s (%d results) - from cache" % (loquery, int(reply["count"])))
            for result in reply["results"]:
                yield result
            if int(reply["count"]) != limit:
                break
            offset += limit
                    
    def __isDescribeCached(self, file, limit, cstop):
        offset = 0
        while True:
            loquery = FMQLCacher.DESCRIBE_TEMPL % (file, cstop, limit, offset)
            print loquery
            queryFile = self.__cacheLocation + "/" + loquery + ".json"
            if not os.path.isfile(queryFile):
                return False
            reply = json.load(open(queryFile, "r"))
            if int(reply["count"]) != limit:
                break
            offset += limit
        return True
            
    def __cacheDescribe(self, file, limit, cstop):
        start = time.time()
        reply = urllib2.urlopen(self.__fmqlEP + "?" + urllib.urlencode({"fmql": "COUNT " + file})).read()
        total = int(json.loads(reply)["count"])
        goes = total/limit + 1
        logging.info("Caching complete file %s in %d pieces" % (file, goes))
        queriesQueue = Queue.Queue()
        offset = 0
        for i in range(goes):
            t = ThreadedEPQueriesCacher(self.__fmqlEP, queriesQueue, self.__cacheLocation)
            t.setDaemon(True)
            t.start()
        for i in range(goes):
            queriesQueue.put(FMQLCacher.DESCRIBE_TEMPL % (file, cstop, limit, offset))
            offset += limit
        queriesQueue.join()
        logging.info("Elapsed Time to cache file %s in %d pieces: %s" % (file, goes, time.time() - start))
            
    def __epCache(self, query):
        logging.info("%s: Sending FMQL EP Query <%s> as not in Cache" % (self.vistaLabel, query))
        reply = urllib2.urlopen(self.__fmqlEP + "?" + urllib.urlencode({"fmql": query})).read()
        return self.__cacheReply(query, reply)

    def __rpcCache(self, query):
        logging.info("%s: Invoking FMQL RPC <%s> as not in Cache" % (self.vistaLabel, query))
        if re.match(r'DESCRIBE TYPE', query):
            rpcArg = "OP:DESCRIBETYPE^TYPE:%s" % re.split("TYPE ", query)[1]
        else:
            rpcArg = "OP:SELECTALLTYPES"
        reply = self.__rpcCPool.invokeRPC("CG FMQL QP", [rpcArg])
        return self.__cacheReply(query, reply)
        
    def __cacheReply(self, query, reply):
        jreply = json.loads(reply)
        jcache = open(self.__cacheLocation + "/" + query + ".json", "w")
        json.dump(jreply, jcache)
        jcache.close()
        return jreply
        
class FMQLDescribeResult(object):
    """
    TODO: 
    - will move out: not intrinsic to Cache
    - jsona, qualify uri's, container name, typed fields
    """
    def __init__(self, result):
        self.__result = result
        
    @property
    def id(self):
        return self.__result["uri"]["value"]
        
    def cstopped(self, flatten=False):
        """Return as if CSTOP=0"""
        return self.__flatten(self.__result, False)
            
    def cnodeFields(self):
        return [field for field, value in self.__result.items() if value["type"] == "cnodes"]
        
    def cnodes(self, cnodeField):
        if cnodeField not in self.__result:
            return None
        cnodes = []
        # TODO: may exception
        if "stopped" in self.__result[cnodeField]:
            return cnodes
        for cr in self.__result[cnodeField]["value"]:
            fcnode = self.__flatten(cr, nixURI=True)
            fcnode["vse:container"] = self.id
            cnodes.append(fcnode)
        return cnodes
        
    def __flatten(self, dr, includeCNodes=True, nixURI=False):
        fdr = {}
        for field, value in dr.items():
            if nixURI and field == "uri": # CNodes - no need
                continue
            if value["type"] == "cnodes":
                if includeCNodes and "stopped" not in value:
                    fdr[field] = [self.__flatten(cnode, nixURI=True) for cnode in value["value"]]
                continue
            fdr[field] = value["value"]
        return fdr
                
class RPCLogger:
    def __init__(self):
        pass
    def logInfo(self, tag, msg):
        pass
    def logError(self, tag, msg):
        self.__log(tag, msg)
        logging.critical("BROKERRPC Problem -- %s %s" % (tag, msg))
        
class ThreadedEPQueriesCacher(threading.Thread):

    def __init__(self, fmqlEP, queriesQueue, cacheLocation):
        threading.Thread.__init__(self)
        self.__fmqlEP = fmqlEP
        self.__queriesQueue = queriesQueue
        self.__cacheLocation = cacheLocation
        
    def run(self):
        while True:
            query = self.__queriesQueue.get()
            reply = urllib2.urlopen(self.__fmqlEP + "?" + urllib.urlencode({"fmql": query})).read()
            jcache = open(self.__cacheLocation + "/" + query + ".json", "w")
            jcache.write(reply)
            jcache.close()
            logging.info("Cached " + query)
            self.__queriesQueue.task_done()
        
# ######################## Module Demo ##########################
            
def demo():
    """
    Simple Demo of this Module
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    fcm = FMQLCacher("Caches")
    fcm.setVista("CGVISTA", "http://vista.caregraf.org/fmqlEP")
    for entry in fcm.describeFileEntries("9_6"):
        print entry["uri"]["label"]
                
if __name__ == "__main__":
    demo()
