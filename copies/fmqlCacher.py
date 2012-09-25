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
        if host:
            verify = "CD1234!!"
            self.__rpcCPool = RPCConnectionPool("VistA", self.__poolSize, host, port, access, verify, "CG FMQL QP USER", RPCLogger())        
    
    def clearCache(self, vistaLabel):
        pass
    
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
        # verify = "CD1234!!"
        reply = self.__rpcCPool.invokeRPC("CG FMQL QP", [rpcArg])
        return self.__cacheReply(query, reply)
        
    def __cacheReply(self, query, reply):
        jreply = json.loads(reply)
        jcache = open(self.__cacheLocation + "/" + query + ".json", "w")
        json.dump(jreply, jcache)
        jcache.close()
        return jreply      
        
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