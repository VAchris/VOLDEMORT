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
- thread FMQL EP calls just like RPC calls are threaded.
- support read/write from ZIPs
- support many Vistas at once ie/ many labels 
- support Application Proxy mechanism once added to brokerRPC
"""

import os
import re
import urllib
import urllib2
import json
import sys
import logging
from brokerRPC import RPCConnectionPool        

__all__ = ['FMQLCacher']

class FMQLCacher:
    """
    Manage Cache of FMQL responses for a named VistA. Works with both a web hosted FMQL endpoint and directly with the FMQL RPC.
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
        
    def queryLimited(self, vistaLabel, query, limit=-1):
        """
        This is a generator object that avoids the need for every one
        of the results of a query to be in memory for processing. 
        
        Note that there is a speed tradeoff between # of queries and 'limit' 
        but this won't effect the caller which just sees only result at a time.
        
        for result in queryLimited("x", "QUERY ..."):
            print result
            
        TODO: 
        - break out as iterator (__iter__) that calls this method as its
        generator, FMQLQuery
          fmqlCacher.fmqlQueryIterator(query, limit)
          for result in fmqlCacher.fmqlQueryIterator(query, limit)
        or may just go straight into queue from threads ie/ queue.get()
        """
        if limit == -1:
            limit = 5000 if re.search(r'SELECT ', query) else 1000
        else:
            limit = int(limit) # just to be sure.
        offset = 0
        while True:
            loquery = query + " LIMIT %s OFFSET %s" % (limit, offset)
            queryFile = self.__cacheLocation + "/" + loquery + ".json"
            if os.path.isfile(queryFile):
                reply = json.load(open(queryFile, "r"))
            else:
                if not (self.__fmqlEP or self.__rpcCPool):
                    logging.critical("Don't know FMQL EP or Access/Verify for %s, so can't do <%s> - exiting" % (self.vistaLabel, str(loquery)))
                    raise Exception("Need FMQL EP or Access/Verify")            
                if self.__fmqlEP:
                    reply = self.__epCache(loquery)
                else: # self.__rpcCPool:
                    reply = self.__rpcCache(loquery)
            logging.info("Reading - %s (%d results) - from cache" % (loquery, int(reply["count"])))
            for result in reply["results"]:
                yield result
            if int(reply["count"]) != limit:
                break
            offset += limit
    
    def query(self, vistaLabel, query):
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
    """TODO: jsona, qualify uri's, container name, typed fields"""
    
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
                if includeCNodes:
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
        
# ######################## Module Demo ##########################
            
def demo():
    """
    Simple Demo of this Module
    """
    fcm = FMQLCacher("Caches")
    fcm.setVista("CGVISTA", "http://vista.caregraf.org/fmqlEP")
                
if __name__ == "__main__":
    demo()
