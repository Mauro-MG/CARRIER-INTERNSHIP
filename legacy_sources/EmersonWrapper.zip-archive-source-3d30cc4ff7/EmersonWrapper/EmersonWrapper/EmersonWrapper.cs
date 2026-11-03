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

 