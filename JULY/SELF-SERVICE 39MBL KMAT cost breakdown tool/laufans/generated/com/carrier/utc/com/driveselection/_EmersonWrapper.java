//  ******* THIS FILE IS MACHINE GENERATED 03/25/2013 13:12 *******  
//  ******* Java2COM Wizard 2.01 ******* 
package com.carrier.utc.com.driveselection;
import com.neva.*;
import java.util.*;
import java.lang.reflect.*;

/**
 * <i>Generated from type library EmersonWrapper.tlb {E3478263-F9FA-4E97-B283-3AE9589CF8AB}, version 1.0. GUID={A081BB27-ACDD-3609-8176-BD8316E2E5B3}</i>
 * @author Java2COM Automation Wizard (2.01)
 */
public class _EmersonWrapper extends com.neva.COMIDispatch {

public float _J2C_WIZ_VER() { return 2.01f;}

void __J2C_Exception_Handler(COMHResult res, com.neva.COMExcepInfo ei) throws com.neva.COMException {
  if(res.success()) return;
  COMException exc;
  if(res.getValue()==com.neva.COMHResult.DISP_E_EXCEPTION)
    exc=new com.neva.COMException("COM IDispatch exception:"+ei.getDescription(),res,ei);
  else 
    exc=new com.neva.COMException("COM exception "+Integer.toString((int)(res.getValue()<0?0x100000000L+res.getValue():res.getValue()),16),res,null);
  throw exc;
}

public _EmersonWrapper() {this.setIfPtr(0);}
public _EmersonWrapper(com.neva.COMIUnknown unk) {this.setIfPtr(unk.ifPtr());}
public _EmersonWrapper(com.neva.COMIDispatch dsp) {this.setIfPtr(dsp.ifPtr()); axcontainer=dsp.axcontainer;}

public static com.neva.GUID _TypeLibGUID() {return new GUID("{E3478263-F9FA-4E97-B283-3AE9589CF8AB}");}
public static int _TypeLibMajorVersion() {return 1;}
public static int _TypeLibMinorVersion() {return 0;}
public static com.neva.GUID _TypeGUID() {return new GUID("{A081BB27-ACDD-3609-8176-BD8316E2E5B3}");}
public com.neva.GUID _TypeLibGUID2() {return new GUID("{E3478263-F9FA-4E97-B283-3AE9589CF8AB}");}
public com.neva.GUID _TypeGUID2() {return new GUID("{A081BB27-ACDD-3609-8176-BD8316E2E5B3}");}
private int _toInt(int p) {return p;}
private int  _toInt(com.neva.COMIUnknown p) {return (int)p.ifPtr();}

}
