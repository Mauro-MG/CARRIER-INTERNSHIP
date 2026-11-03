using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.IO;
using System.Xml;
using System.ServiceModel;
using System.ServiceModel.Web;
using System.ServiceModel.Description;

namespace WcfEmersonEXE
{
    [ServiceContract]
    public interface IEmersonRest
    {
        [OperationContract, WebInvoke(BodyStyle = WebMessageBodyStyle.Bare)]
        Stream selectDrive(Stream s);
    }

    [ServiceBehavior(ConcurrencyMode = ConcurrencyMode.Multiple, IncludeExceptionDetailInFaults = true)]
    public class Service1 : IEmersonRest
    {
        internal static String configDirectory;

        Object LockObject = new Object();
        public Stream selectDrive(Stream s)
        {
            StreamReader sr = new StreamReader(s);
            string ss = sr.ReadToEnd();

            Console.WriteLine("Processing Request " + ss.length());
            
           // Console.WriteLine("got " + ss);

           // Console.WriteLine("path " + configDirectory);
            ss = ss.Replace("PATHPATHPATH", configDirectory);

            XmlDocument doc = new XmlDocument();
            doc.LoadXml(ss);
            MemoryStream stream = null;
            String output = "unknown";
            lock (LockObject)
            {
                PTS.Library.VbeltDriveLibrary.Configurator config = new PTS.Library.VbeltDriveLibrary.Configurator(doc);
                StringWriter sw = new StringWriter();
                XmlTextWriter xw = new XmlTextWriter(sw);

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
                stream = new MemoryStream(byteArray);
                Console.WriteLine("Processed Request " + output.length());

            }
            return stream;
        }


    }
    class Program
    {
        public static void Main(string[] args)
        {
            // args[0] = directory where emerson xml files are located
            // args[1] = base url = "http://127.0.0.1:8020"
            // args[2] = end point = "http://127.0.0.1:8020/SelectDrive"
            Service1.configDirectory = args[0];
            WebServiceHost host = new WebServiceHost(typeof(Service1), new Uri(args[1]));

            host.AddServiceEndpoint(typeof(IEmersonRest), new WebHttpBinding(), args[2]);
            host.Open();
            Thread.Sleep(Timeout.Infinite);
            host.Close();
        }
    }
}

