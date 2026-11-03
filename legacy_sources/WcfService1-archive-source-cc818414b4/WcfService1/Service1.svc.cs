using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.Serialization;
using System.ServiceModel;
using System.ServiceModel.Web;
using System.ServiceModel.Description;
using System.Text;
using System.Xml;

using System.IO;


namespace WcfEmerson
{
    [ServiceContract]
    public interface IEmersonRest
    {
        [OperationContract]
        [WebInvoke(BodyStyle = WebMessageBodyStyle.Bare)]
        Stream selectDrive(Stream  s);
    }



    // NOTE: You can use the "Rename" command on the "Refactor" menu to change the class name "Service1" in code, svc and config file together.
    // NOTE: In order to launch WCF Test Client for testing this service, please select Service1.svc or Service1.svc.cs at the Solution Explorer and start debugging.
    public class Service1 : IEmersonRest
    {
        public Stream selectDrive(Stream s)
        {
            StreamReader sr = new StreamReader(s);
            string ss = sr.ReadToEnd();
            Console.WriteLine("got " + ss);

            string path = Directory.GetCurrentDirectory();
            Console.WriteLine("path " + path);
            ss =ss.Replace("PATHPATHPATH", path);

            XmlDocument doc = new XmlDocument();
            doc.LoadXml(ss);

            PTS.Library.VbeltDriveLibrary.Configurator config = new PTS.Library.VbeltDriveLibrary.Configurator(doc);
            StringWriter sw = new StringWriter();
            XmlTextWriter xw = new XmlTextWriter(sw);

            String output = "unknown";

            if (config.SolveAndValidate())
            {

                config.Results.WriteTo(xw);
                output = "GOOD:" + sw.ToString();
            }
            else
            {
                config.Validator.WriteTo(xw);
                output = "BAD :" + sw.ToString();
            }

            // convert string to stream
            byte[] byteArray = Encoding.UTF8.GetBytes(output);
            //byte[] byteArray = Encoding.ASCII.GetBytes(contents);
            MemoryStream stream = new MemoryStream(byteArray);


            return stream;
        }

        
    }
    class Program
    {
        static void Main(string[] args)
        {
            WebServiceHost host = new WebServiceHost(typeof(Service1), new Uri("http://127.0.0.1:8020"));
            try
            {
                ServiceEndpoint ep = host.AddServiceEndpoint(typeof(IEmersonRest), new WebHttpBinding(), "");
                host.Open();
                Console.WriteLine("press <ENTER> to end");
                Console.ReadLine();
                host.Close();

            }
            catch (CommunicationException ce)
            {
                Console.WriteLine("Exception " + ce.Message);
                Console.WriteLine(ce.StackTrace);
                host.Abort();
            }
        }
    }

}
