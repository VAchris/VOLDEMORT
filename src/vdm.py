#!/usr/bin/env python
#
## VOLDEMORT (VDM) VistA Comparer, command line driver
#
# (c) 2012 Caregraf, Ray Group Intl
# For license information, see LICENSE.TXT
#

"""
VOLDEMORT (VDM)

-h, --help: this help text
-v, --vista: name of VistA. Defaults to "CGVISTA", Caregraf's publicly hosted demo VistA
-f, --fmqlep: FMQL endpoint. For example, "http://vista.caregraf.org/fmqlEP". If set, then no need for --host, --port, --access, --verify
--host: host of VistA
--port: port of VistA
--access: access for FMQL RPC
--verify: verify for FMQL RPC
-r, --report: only 'schema' for now. If report isn't specified then only caching runs.

Example using a full FMQL RESTful endpoint ...
$ python vdm.py -v CGVISTA -f http://vista.caregraf.org/fmqlEP -r schema
or to use the FMQL RPC directly ...
$ python vdm.py -v CGVISTA --host "xx.xx.xx" --port 9201 --access "XXX" --verify "YYY" -r schema

The first time VDM runs against a VistA, the majority of time taken is downloading meta data. Subsequent runs of VDM for that VistA will be much faster as they'll run off a cache. 

Any VistA being reported on must have FMQL installed. 
For install instructions for FMQL, see http://repository.caregraf.org/fmql/raw-file/tip/Releases/v0.9/installFMQLV0_9.html.

Note: you DO NOT have to install the full, RESTful FMQL endpoint. The RPC is enough.
"""

import os
import sys
import re
import getopt
import logging
from vistaSchema import VistaSchema
from vistaSchemaComparer import VistaSchemaComparer
from fmqlCacher import FMQLCacher

def main():
    """
    TODO: 
    - play with pool size to see speed of Caching
    - crude: move to argparse and a VistA directory file
    - if GOLD zip and not in Cache, move to Cache
    - when more than Schema reports, add option for --report
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hv:f:r:", ["help", "vista=", "fmqlep=", "report=", "host=", "port=", "access=", "verify="])
    except getopt.GetoptError, err:
        print str(err)
        print __doc__
        sys.exit(2)
    # Default VistA to Caregraf Demo VistA
    vista = "CGVISTA"
    # Will match to CGVISTA's if no other VistA name is specified
    fmqlEP = ""
    host = ""
    port = -1
    access = ""
    verify = ""
    report = ""
    for o, a in opts:
        if o in ("-v", "--vista"):
            vista = a
        elif o in ("-f", "--fmqlep"):
            fmqlEP = a
        elif o in ("--host"):
            host = a
        elif o in ("--port"):
            port = a            
        elif o in ("--access"):
            access = a
        elif o in ("--verify"):
            verify = a
        elif o in ("-r", "--report"):
            report = a
        elif o in ("-h", "--help"):
            print __doc__
            sys.exit()
    print "VDM - comparing a VistA's schema against GOLD. -h for help."
    if vista == "CGVISTA":
        print "Defaulting to Caregraf's demo VistA, 'CGVISTA'"
        fmqlEP = "http://vista.caregraf.org/fmqlEP"
    goldCacher = FMQLCacher("Caches")
    goldCacher.setVista("GOLD")
    goldVistA = VistaSchema("GOLD", goldCacher)
    ovCacher = FMQLCacher("Caches")
    ovCacher.setVista(vista, fmqlEP=fmqlEP, host=host, port=int(port), access=access, verify=verify)
    otherVistA = VistaSchema(vista, ovCacher)
    vsr = VistaSchemaComparer(goldVistA, otherVistA)
    # Cache Only means no comparison. Just cache.
    if not report:
        print "Complete Schema Cached"
        sys.exit()
    reportLocation = vsr.compare()
    print "Schema Report written to %s" % os.path.abspath(reportLocation)
    
if __name__ == "__main__":
    main()
