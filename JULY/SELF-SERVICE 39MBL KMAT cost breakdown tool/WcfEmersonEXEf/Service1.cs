// Decompiled with JetBrains decompiler
// Type: WcfEmersonEXE.Service1
// Assembly: WcfEmersonEXE, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null
// MVID: 262039AD-1FF5-45A1-9262-B39C78D2708F
// Assembly location: C:\Users\montelma1\Desktop\JULY\SELF-SERVICE 39MBL KMAT cost breakdown tool\WcfEmersonEXE.exe

using PTS.Library.VbeltDriveLibrary;
using System;
using System.IO;
using System.ServiceModel;
using System.Text;
using System.Xml;

#nullable disable
namespace WcfEmersonEXE;

[ServiceBehavior(ConcurrencyMode = ConcurrencyMode.Multiple, IncludeExceptionDetailInFaults = true)]
public class Service1 : IEmersonRest
{
  internal static string configDirectory;
  private object LockObject = new object();

  public Stream selectDrive(Stream s)
  {
    string end = new StreamReader(s).ReadToEnd();
    Console.WriteLine("Processing Request " + (object) end.Length);
    string xml = end.Replace("PATHPATHPATH", Service1.configDirectory);
    XmlDocument xmlDocument = new XmlDocument();
    xmlDocument.LoadXml(xml);
    MemoryStream memoryStream = (MemoryStream) null;
    lock (this.LockObject)
    {
      Configurator configurator = new Configurator((XmlDocument) xmlDocument);
      StringWriter w1 = new StringWriter();
      XmlTextWriter w2 = new XmlTextWriter((TextWriter) w1);
      string s1;
      if (configurator.SolveAndValidate())
      {
        ((XmlNode) configurator.Results).WriteTo((XmlWriter) w2);
        s1 = "GOOD:" + w1.ToString();
      }
      else
      {
        ((XmlNode) configurator.Validator).WriteTo((XmlWriter) w2);
        s1 = "BAD :" + w1.ToString();
      }
      memoryStream = new MemoryStream(Encoding.UTF8.GetBytes(s1));
      Console.WriteLine("Processed Request " + (object) s1.Length);
    }
    return (Stream) memoryStream;
  }
}
