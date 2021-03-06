#-------------------------------------------------------------------------------
# rtlconverter.py
# 
# PyCoRAM RTL Converter
#
# Copyright (C) 2013, Shinya Takamaeda-Yamazaki
# License: Apache 2.0
#-------------------------------------------------------------------------------
from __future__ import absolute_import
from __future__ import print_function
import sys
import os
import collections

from pycoram.rtlconverter.convertvisitor import InstanceConvertVisitor
from pycoram.rtlconverter.convertvisitor import InstanceReplaceVisitor

import pyverilog.vparser.ast as vast
import pyverilog.utils.signaltype as signaltype
from pyverilog.vparser.parser import VerilogCodeParser
from pyverilog.dataflow.modulevisitor import ModuleVisitor
from pyverilog.utils.scope import ScopeLabel, ScopeChain

class RtlConverter(object):
    def __init__(self, filelist, topmodule='userlogic', include=None,
                 define=None, single_clock=False):
        self.filelist = filelist
        self.topmodule = topmodule
        self.include = include
        self.define = define
        self.single_clock = single_clock

        self.top_parameters = collections.OrderedDict()
        self.top_ioports = collections.OrderedDict()
        self.coram_object = collections.OrderedDict()

    def getTopParameters(self):
        return self.top_parameters
    
    def getTopIOPorts(self):
        return self.top_ioports

    def getCoramObject(self):
        return self.coram_object

    def dumpCoramObject(self):
        coram_object = self.getCoramObject()
        print("----------------------------------------")
        print("CoRAM Objects in User-defined RTL")
        for mode, coram_items in coram_object.items():
            print("  CoRAM %s" % mode)
            for threadname, idx, subid, addrwidth, datawidth in sorted(coram_items, key=lambda x:x[1]):
                print("    %s(ID:%d%s Thread:%s AddrWidth:%s DataWidth:%s)" %
                      (mode, idx, ( '' if subid is None else ''.join( ('[', str(subid), ']') ) ),
                       threadname, str(addrwidth), str(datawidth)))
        
    def generate(self):
        preprocess_define = []
        if self.single_clock:
            preprocess_define.append('CORAM_SINGLE_CLOCK')
        if self.define:
            preprocess_define.extend(self.define)

        code_parser = VerilogCodeParser(self.filelist,
                                        preprocess_include=self.include,
                                        preprocess_define=preprocess_define)
        ast = code_parser.parse()

        module_visitor = ModuleVisitor()
        module_visitor.visit(ast)
        modulenames = module_visitor.get_modulenames()
        moduleinfotable = module_visitor.get_moduleinfotable()

        instanceconvert_visitor = InstanceConvertVisitor(moduleinfotable, self.topmodule)
        instanceconvert_visitor.start_visit()

        replaced_instance = instanceconvert_visitor.getMergedReplacedInstance()
        replaced_instports = instanceconvert_visitor.getReplacedInstPorts()
        replaced_items = instanceconvert_visitor.getReplacedItems()        

        new_moduleinfotable = instanceconvert_visitor.get_new_moduleinfotable()
        instancereplace_visitor = InstanceReplaceVisitor(replaced_instance, 
                                                         replaced_instports,
                                                         replaced_items,
                                                         new_moduleinfotable)
        ret = instancereplace_visitor.getAST()

        # gather user-defined io-ports on top-module and parameters to connect external
        frametable = instanceconvert_visitor.getFrameTable()
        top_ioports = []
        for i in moduleinfotable.getIOPorts(self.topmodule):
            if signaltype.isClock(i) or signaltype.isReset(i): continue
            top_ioports.append(i)

        top_scope = ScopeChain( [ScopeLabel(self.topmodule, 'module')] )
        top_sigs = frametable.getSignals(top_scope)
        top_params = frametable.getConsts(top_scope)

        for sk, sv in top_sigs.items():
            if len(sk) > 2: continue
            signame = sk[1].scopename
            for svv in sv:
                if (signame in top_ioports and 
                    not (signaltype.isClock(signame) or signaltype.isReset(signame)) and
                    isinstance(svv, vast.Input) or isinstance(svv, vast.Output) or isinstance(svv, vast.Inout)):
                    port = svv
                    if port.width is not None:
                        msb_val = instanceconvert_visitor.optimize(instanceconvert_visitor.getTree(port.width.msb, top_scope))
                        lsb_val = instanceconvert_visitor.optimize(instanceconvert_visitor.getTree(port.width.lsb, top_scope))
                        width = int(msb_val.value) - int(lsb_val.value) + 1
                    else:
                        width = None
                    self.top_ioports[signame] = (port, width)
                    break

        for ck, cv in top_params.items():
            if len(ck) > 2: continue
            signame = ck[1].scopename
            param = cv[0]
            if isinstance(param, vast.Genvar): continue
            self.top_parameters[signame] = param

        self.coram_object = instanceconvert_visitor.getCoramObject()

        return ret
