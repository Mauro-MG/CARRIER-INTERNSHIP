using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Xml;
using System.IO;


namespace EmersonWrapper
{
    public class EmersonWrapper {


        public string EmitResults(string input)
        {

           // string input = "<Main><Settings><IgnoreNEMAStandards>True</IgnoreNEMAStandards><Data>XML</Data><Data><XMLPath>C:\\Users\\jareddavis\\Documents\\prj\\ahu\\costcheck\\laufans\\emerson\\update20140305</XMLPath></Data></Settings><InputString><RequiredInputs><Input><ID>ReqInp_DoNotExceedSpeed</ID><Value>9999</Value></Input><Input><ID>ReqInp_DrivenDiameter</ID><Value>2.4375</Value></Input><Input><ID>ReqInp_DrivenSpeed</ID><Value>0674</Value></Input><Input><ID>ReqInp_DriverDiameter</ID><Value>1.625</Value></Input><Input><ID>ReqInp_DriverSpeed</ID><Value>1750</Value></Input><Input><ID>ReqInp_Horsepower</ID><Value>15</Value></Input><Input><ID>ReqInp_MinCenterDistance</ID><Value>24.9</Value></Input><Input><ID>ReqInp_MaxCenterDistance</ID><Value>26.8</Value></Input><Input><ID>ReqInp_ServiceFactor</ID><Value>1.2</Value></Input><Input><ID>ReqInp_VariableSpeed</ID><Value>True</Value></Input><Input><ID>ReqInp_DrivenDiameterIsMetric</ID><Value>False</Value></Input><Input><ID>ReqInp_DrivenSpeedIsMidrange</ID><Value>True</Value></Input><Input><ID>ReqInp_DriverDiameterIsMetric</ID><Value>False</Value></Input><Input><ID>ReqInp_OptionsInvoked</ID><Value>True</Value></Input><Input><ID>ReqInp_OrderDrive</ID><Value>False</Value></Input><Input><ID>ReqInp_OutputMode</ID><Value>1</Value></Input><Input><ID>ReqInp_InputPowerMode</ID><Value>1</Value></Input><Input><ID>ReqInp_CenterDistanceMode</ID><Value>1</Value></Input><Input><ID>SelectedMultID</ID><Value>0</Value></Input><Input><ID>ReqInp_ProvideNetPrice</ID><Value>True</Value></Input><Input><ID>ReqInp_ProvideInterchanges</ID><Value>False</Value></Input></RequiredInputs><OptionalInputs><Input><ID>OptInp_MinNumGrooves</ID><Value>2</Value></Input><Input><ID>OptInp_MaxSpeedVariation</ID><Value>5</Value></Input><Input><ID>OptInp_MinSpeedVariation</ID><Value>5</Value></Input><Input><ID>OptInp_MaxDriverPD</ID><Value>10.625</Value></Input><Input><ID>OptInp_Allow3VXBelts</ID><Value>True</Value></Input><Input><ID>OptInp_Allow4LBelts</ID><Value>False</Value></Input><Input><ID>OptInp_Allow5LBelts</ID><Value>False</Value></Input><Input><ID>OptInp_Allow5VBelts</ID><Value>True</Value></Input><Input><ID>OptInp_Allow5VXBelts</ID><Value>True</Value></Input><Input><ID>OptInp_Allow8VBelts</ID><Value>False</Value></Input><Input><ID>OptInp_AllowABelts</ID><Value>True</Value></Input><Input><ID>OptInp_AllowAXBelts</ID><Value>True</Value></Input><Input><ID>OptInp_AllowBBelts</ID><Value>True</Value></Input><Input><ID>OptInp_AllowBrowningBushedSheaves</ID><Value>True</Value></Input><Input><ID>OptInp_AllowBXBelts</ID><Value>True</Value></Input><Input><ID>OptInp_AllowCBelts</ID><Value>False</Value></Input><Input><ID>OptInp_AllowCXBelts</ID><Value>False</Value></Input><Input><ID>OptInp_AllowFinishedBoreSheaves</ID><Value>True</Value></Input><Input><ID>OptInp_AllowQDBushedSheaves</ID><Value>True</Value></Input><Input><ID>OptInp_ConformToNEMAStandard</ID><Value>False</Value></Input><Input><ID>OptInp_LimitHubLoad</ID><Value>False</Value></Input><Input><ID>OptInp_MaxBeltFPM</ID><Value>6500</Value></Input><Input><ID>OptInp_MaxDrivenPD</ID><Value>63.8</Value></Input><Input><ID>OptInp_MaxFaceWidth</ID><Value>19</Value></Input><Input><ID>OptInp_MaxHubLoad</ID><Value>9999</Value></Input><Input><ID>OptInp_MaxNumGrooves</ID><Value>16</Value></Input><Input><ID>OptInp_MinBeltFPM</ID><Value>900</Value></Input><Input><ID>OptInp_MinDrivenPD</ID><Value>1.5</Value></Input><Input><ID>OptInp_MinDriverPD</ID><Value>1.5</Value></Input><Input><ID>OptInp_NEMANumber</ID><Value>0</Value></Input><Input><ID>OptInp_UseDesignatedPartsOnly</ID><Value>False</Value></Input><Input><ID>OptInp_UseMinSpeedInHorsepowerCalculation</ID><Value>False</Value></Input></OptionalInputs></InputString></Main>";
            XmlDocument doc = new XmlDocument();
            doc.LoadXml(input);

            PTS.Library.VbeltDriveLibrary.Configurator config = new PTS.Library.VbeltDriveLibrary.Configurator(doc);
            StringWriter  sw = new StringWriter();
            XmlTextWriter xw = new XmlTextWriter(sw);
            
            
            if (config.SolveAndValidate()) {
               
                config.Results.WriteTo(xw);
                return "GOOD:" + sw.ToString();
            } else {
                config.Validator.WriteTo(xw);
                return "BAD :" + sw.ToString();
            }
        }
    }
}

 