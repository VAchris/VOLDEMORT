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
- exceptions in thread:
  except: sys.exit()
  and may need to put threads into an array to keep around (check 25 pool again)
- option to filter out (ex/ redundancies in builds etc.): can choose what to cache
  - yes/no -> TRUE FALSE ie/ boolean as standard 
  - apply default if field missing
  ... or add these first to Describe flattener
- uri level in flatten describe including keeping label ...
- < 1.1 check for Schema once FOIA GOLD has it
- support read/write from ZIPs
- /usr/share/vdm/cache and the equivalent on windows (will allow setting)
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
    - Break out iterators explicitly. They can take FMQLInterface which
    can hide the Cache as well as RPC vs FMQL EP.
    """
    def __init__(self, cachesLocation):
        try:
            if not os.path.exists(cachesLocation):
                os.mkdir(cachesLocation) 
        except:
            logging.critical(sys.exc_info()[0])
            raise
        self.__cachesLocation = cachesLocation
            
    """
    Pool size play (Schema Grab):
    - RPC:
      - Elapsed Time to cache schema in 5 pieces: 149.387557983
      - Elapsed Time to cache schema in 10 pieces: 70.3322050571
      - Elapsed Time to cache schema in 15 pieces: 50.4330279827
      TODO: if go to 20, stops once has them all. Doesn't depend on counting
      queue size but in print outs the queue does go to 0 for all the last elements.
    - EP:
      - Elapsed Time to cache schema in 10 pieces: 160.150575876
      - Elapsed Time to cache schema in 15 pieces: 134.057111025
      - Elapsed Time to cache schema in 20 pieces: 133.793686867 ie/ marginal
    For now, setting sweet spot to 15. Need to tweek for different boxes.
    """
    def setVista(self, vistaLabel, fmqlEP="", host="", port=-1, access="", verify="", poolSize=15):
        self.vistaLabel = vistaLabel
        try:
            self.__cacheLocation = self.__cachesLocation + "/" + re.sub(r' ', '_', vistaLabel)
            if not os.path.exists(self.__cacheLocation):
                os.mkdir(self.__cacheLocation)
        except:
            logging.critical(sys.exc_info()[0])
            raise
        rpcCPool = RPCConnectionPool("VistA", poolSize, host, port, access, verify, "CG FMQL QP USER", RPCLogger()) if host else None
        self.__poolSize = poolSize # if rpc then # threads == conn pool size
        self.__fmqlIF = FMQLInterface(fmqlEP, rpcCPool) if (fmqlEP or rpcCPool) else None         
    
    def clearCache(self, vistaLabel):
        pass
        
    def query(self, query):
        """
        Invoke any query. If not in cache then dispatch it and cache
        the reply. 
        
        Simple, blocking invocation. No generator, iterator or threading
        efficiencies.
        """
        queryFile = self.__cacheLocation + "/" + query + ".json"
        if os.path.isfile(queryFile):
            reply = json.load(open(queryFile, "r"))
            return reply
        reply = self.__fmqlIF.query(query)
        jreply = json.loads(reply)
        jcache = open(self.__cacheLocation + "/" + query + ".json", "w")
        json.dump(jreply, jcache)
        jcache.close()
        # logging.info("Cached " + query)
        return jreply
                    
    def describeSchemaTypes(self):
        """
        Generator, returns one type at a time. Takes "count" from 
        SELECT TYPES and moves into top file's description and
        flattens description.
       
        Invoke with:
            for cnt, schema in enumerate(.describeSchemaTypes()) 
            
        TODO:
        - make iteration more explicit with an FMQLSchemaIterator class.
        All this should move out of the Cacher class.
        - flatten field and file description ie/ remove "value"
        """
        if not self.__isSchemaCached():
            self.__cacheSchema()
        queryFile = self.__cacheLocation + "/SELECT TYPES.json"
        selectTypesReply = json.load(open(queryFile))
        for result in selectTypesReply["results"]:
            if float(result["number"]) < 1.1: 
                continue # TEMP - ignore under 1.1
            queryFile = self.__cacheLocation + "/DESCRIBE TYPE " + re.sub(r'\.', '_', result["number"]) + ".json"
            jreply = json.load(open(queryFile))
            if "count" in result:
                jreply["count"] = result["count"]
            yield jreply
            
    def __isSchemaCached(self):
        queryFile = self.__cacheLocation + "/SELECT TYPES.json"
        if not os.path.isfile(queryFile):
            return False
        selectTypesReply = json.load(open(queryFile))
        for result in selectTypesReply["results"]:
            if float(result["number"]) < 1.1: 
                continue # TEMP - ignore under 1.1
            queryFile = self.__cacheLocation + "/DESCRIBE TYPE " + re.sub(r'\.', '_', result["number"]) + ".json"
            if not os.path.isfile(queryFile):
                return False
        return True        
        
    # Elapsed Time to cache schema in 50 pieces: 136.819022894
    def __cacheSchema(self):
        start = time.time()
        reply = self.query("SELECT TYPES")
        queriesQueue = Queue.Queue()
        for i in range(self.__poolSize):
            fmqlIF = self.__fmqlIF # TODO: shared makes no speed difference (make sure)
            t = ThreadedQueriesCacher(fmqlIF, queriesQueue, self.__cacheLocation)
            t.setDaemon(True)
            t.start()
        # logging.info("Caching %d types at a time" % self.__poolSize)
        for result in reply["results"]:
            if float(result["number"]) < 1.1: 
                continue
            queriesQueue.put("DESCRIBE TYPE " + re.sub(r'\.', '_', result["number"]))
        queriesQueue.join()
        # logging.info("Elapsed Time to cache schema in %d pieces: %s" % (self.__poolSize, time.time() - start))        
        
    DESCRIBE_TEMPL = "DESCRIBE %s CSTOP %s LIMIT %d OFFSET %d"
        
    def describeFileEntries(self, file, limit=200, cstop=100):
        """
        This is a generator object that avoids the need for every one
        of the results of a query to be in memory for processing. 
                
        Invoke with:
            for cnt, entry in enumerate(.describeFileEntries()) 

        TODO: 
        - may make iterator/generator more explicit by returning one.
          ex/ FMQLFileIterator
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
            # logging.info("Reading - %s (%d results) - from cache" % (loquery, int(reply["count"])))
            for result in reply["results"]:
                yield result
            if int(reply["count"]) != limit:
                break
            offset += limit
                    
    def __isDescribeCached(self, file, limit, cstop):
        offset = 0
        while True:
            loquery = FMQLCacher.DESCRIBE_TEMPL % (file, cstop, limit, offset)
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
        # Never cache COUNT. Go direct.
        reply = self.__fmqlIF.query("COUNT " + file)
        total = int(json.loads(reply)["count"])
        goes = total/limit + 1
        # logging.info("Caching complete file %s in %d pieces" % (file, goes))
        queriesQueue = Queue.Queue()
        offset = 0
        noQueries = total/limit + 1
        noThreads = noQueries if noQueries < self.__poolSize else self.__poolSize
        for i in range(goes):
            fmqlIF = self.__fmqlIF # TODO: shared makes no speed difference (make sure)
            t = ThreadedQueriesCacher(fmqlIF, queriesQueue, self.__cacheLocation)
            t.setDaemon(True)
            t.start()
        for i in range(goes):
            queriesQueue.put(FMQLCacher.DESCRIBE_TEMPL % (file, cstop, limit, offset))
            offset += limit
        queriesQueue.join()
        # logging.info("Elapsed Time to cache file %s in %d pieces: %s" % (file, noThreads, time.time() - start))
                    
class FMQLDescribeResult(object):
    """
    TODO: 
    - uri label: preserve ex/ package label ("label") and ptr ("value")
    - apply filters: yes/no -> true/false, apply defaults etc.
    - will move out: not intrinsic to Cache
    - jsona, qualify uri's, container name, typed fields
      - ie/ don't just flatten uri to literal form ... use : ie/ vista:2-24 etc.
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
        
    def noSpecificValues(self):
        """
        How many specific values are explicitly asserted? Want to collect
        data points available. This does NOT count "uri" ie/ identity.
        """
        return self.__noSpecificValues(self.__result)
        
    def __noSpecificValues(self, dr):
        no = 0
        for field, value in dr.items():
            if field == "uri": # CNodes - no need
                continue
            if value["type"] == "cnodes":
                if "stopped" not in value:
                    for cnode in value["value"]:
                        no += self.__noSpecificValues(cnode)
                continue
            no += 1
        return no
        
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
            # TODO: if "uri" - preserve label ie field + "_Label" = "label" or
            # use () ie/ (9_6-2, "XXX")
            fdr[field] = value["value"]
        return fdr
                
class RPCLogger:
    def __init__(self):
        pass
    def logInfo(self, tag, msg):
        pass
    def logError(self, tag, msg):
        logging.critical("BROKERRPC Problem -- %s %s" % (tag, msg))
        
# Elapsed Time to cache file 9_6 in 35 pieces: 104.36938405
class ThreadedQueriesCacher(threading.Thread):
    """
    TODO:
    - go generic: http://code.activestate.com/recipes/577187-python-thread-pool/
      - pool manages the overall task queue ie/ queriesQueue ie/ ala tie in to rpc pool
    - check out Twisted as an alternative
    """
    def __init__(self, fmqlIF, queriesQueue, cacheLocation):
        threading.Thread.__init__(self)
        self.__fmqlIF = fmqlIF
        self.__queriesQueue = queriesQueue
        self.__cacheLocation = cacheLocation
        
    def run(self):
        while True:
            query = self.__queriesQueue.get()
            reply = self.__fmqlIF.query(query)
            jcache = open(self.__cacheLocation + "/" + query + ".json", "w")
            jcache.write(reply)
            jcache.close()
            logging.info("Caching data from query %s" % query)
            # Monitoring progress with self.__queriesQueue.qsize():
            # - Problem with pool == 20 or so. Get 0 for last ones and then a hang.
            self.__queriesQueue.task_done()
            
class FMQLInterface(object):
    """
    TODO: urllib2 etc timeout in seconds (instead of ? default)
    ... socket.setdefaulttimeout(default_timeout)
    
    Allow access to either the RPC directly (connection pool) or 
    to the FMQL EP. Note that you shouldn't invoke more RPCs than
    the RPC pool size at any one time.
    
    Note: copy of fmqlc utility. 
    """
    def __init__(self, fmqlEP=None, rpcCPool=None):
        self.fmqlEP = fmqlEP
        self.rpcCPool = rpcCPool
        if not (fmqlEP or rpcCPool):
            raise Exception("Must specific either an RPC CPool or an FMQL EP")
    
    def query(self, query):
        if self.rpcCPool:
            reply = self.rpcCPool.invokeRPC("CG FMQL QP", [self.__queryToRPCForm(query)])
            return reply
        return urllib2.urlopen(self.fmqlEP + "?" + urllib.urlencode({"fmql": query})).read()

    QUERYFORMS = { # TODO: enforce mandatory
        "COUNT": ["COUNT", [("TYPE", "COUNT ([\d\_]+)")]],
        "DESCRIBE TYPE": ["DESCRIBETYPE", [("TYPE", "DESCRIBE TYPE ([\d\_]+)")]],
        "DESCRIBE [\d\_]": ["DESCRIBE", [("TYPE", "DESCRIBE ([\d\_]+)"), ("LIMIT", "LIMIT (\d+)"), ("OFFSET", "OFFSET (\d+)"), ("CNODESTOP", "CSTOP (\d+)")]],
        "SELECT TYPES": ["SELECTALLTYPES", []]
    }
        
    def __queryToRPCForm(self, query):
        for qMatch, qPieces in FMQLInterface.QUERYFORMS.items():
            if re.match(qMatch, query):
                rpcForm = "OP:" + qPieces[0]
                for rpcArg, rpcArgSrch in qPieces[1]:
                    match = re.search(rpcArgSrch, query)
                    if match:
                        rpcForm += "^"
                        rpcForm += rpcArg + ":" + match.group(1)
                return rpcForm     
        raise Exception("Query %s can't be turned into RPC form" % query)
        
# ######################## Module Demo ##########################
            
def demo():

    """
    Simple Demo of this Module
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    fcm = FMQLCacher("Caches")
    fcm.setVista("CGVISTA", "http://vista.caregraf.org/fmqlEP")
    for i, scheme in enumerate(fcm.describeSchemaTypes()):
        if "count" in scheme:
            print "%d: %s (%s)" % (i, scheme["number"], scheme["count"])
        else:
            print "%d: %s" % (i, scheme["number"])
    for entry in fcm.describeFileEntries("9_6", cstop="1000"):
        print entry["uri"]["label"]
                
if __name__ == "__main__":
    demo()
