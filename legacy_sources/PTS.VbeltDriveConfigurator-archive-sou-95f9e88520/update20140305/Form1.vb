Imports System.Text
Imports System.Xml
Imports PTS.Library

Public Class Form1

    ''' <summary>
    ''' Creates a sample XML document in the format that is needed by the PTS v-belt drive configurator. (The document that is passed to the PTS.Library.VbeltDriveLibrary.Configurator constructor.)
    ''' </summary>
    ''' <param name="DirectoryContainingProductXmlFiles">The name of the directory containing the six XML files containing product data.</param>
    ''' <returns>A sample XML document in the format that is needed by the PTS v-belt drive configurator. (The document that is passed to the PTS.Library.VbeltDriveLibrary.Configurator constructor.)</returns>
    ''' <remarks>Instead of hardcoding this XML, typically you would programmatically create it based on user input or the results of another program's calculations. This is just a sample to show all of the possible elements in the XML document.</remarks>
    Private Function XmlDocumentForConfigurator(ByVal DirectoryContainingProductXmlFiles As String) As XmlDocument

        Dim XmlString As New StringBuilder()

        XmlString.Append("<Main>")

        XmlString.Append("  <Settings>")
        XmlString.Append("    <IgnoreNEMAStandards>True</IgnoreNEMAStandards>") ' If true, then the configurator will NOT report as an error inputs that do not meet NEMA standards. If false, inputs that do not meet NEMA standards WILL be reported as an error.

        ' The Data element is used to point the configurator to the directory containing the six XML files containing product data
        ' ("Belts.xml", "Bushings.xml", "DesignatedParts.xml", "FixedPitchSheaves.xml", "Multipliers.xml" and "VariablePitchSheaves.xml")

        XmlString.Append("    <Data>XML</Data>")
        XmlString.Append("    <Data>")
        XmlString.Append("      <XMLPath>" & DirectoryContainingProductXmlFiles & "</XMLPath>")
        XmlString.Append("    </Data>")

        XmlString.Append("  </Settings>")

        XmlString.Append("  <InputString>")

        ' The RequiredInputs element is mandatory, and will contain elements specifying all of the basic inputs

        XmlString.Append("    <RequiredInputs>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_DoNotExceedSpeed</ID>")            ' For variable speed drives where the driven speed is specified as the middle of a speed range, this is the maximum driven speed (in RPM) allowed when the driver sheave is fully closed (that is, at the driver sheave's maximum pitch diameter).
        XmlString.Append("        <Value>9999</Value>")                         ' For fixed speed drives, and variable speed drives where the driven speed is NOT specified as the middle of a speed range, it is not meaningful.
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_DrivenDiameter</ID>")              ' The driven shaft diameter.
        XmlString.Append("        <Value>0.875</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_DrivenDiameterIsMetric</ID>")      ' True if the driven shaft diameter is specified in millimeters, false if the driven shaft diameter is specified in inches.
        XmlString.Append("        <Value>False</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_DrivenSpeed</ID>")                 ' The desired driven speed in RPM.
        XmlString.Append("        <Value>875</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_DrivenSpeedIsMidrange</ID>")       ' For variable speed drives, this is true if the driven speed is specified as the middle of a speed range.  It is false if the driven speed is specified as the maximum speed desired.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_DriverDiameter</ID>")              ' The driver shaft diameter.
        XmlString.Append("        <Value>0.875</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_DriverDiameterIsMetric</ID>")      ' True if the driver shaft diameter is specified in millimeters, false if the driver shaft diameter is specified in inches.
        XmlString.Append("        <Value>False</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_DriverSpeed</ID>")                 ' The driver speed in RPM.
        XmlString.Append("        <Value>1750</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_Horsepower</ID>")                  ' The horsepower (if ReqInp_InputPowerMode = 1) or Kilowatts (if ReqInp_InputPowerMode = 2)
        XmlString.Append("        <Value>1</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_MinCenterDistance</ID>")           ' The minimum center distance allowed, in inches (if ReqInp_CenterDistanceMode = 1) or millimeters (if ReqInp_CenterDistanceMode = 2)
        XmlString.Append("        <Value>10</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_MaxCenterDistance</ID>")           ' The maximum center distance allowed, in inches (if ReqInp_CenterDistanceMode = 2) or millimeters (if ReqInp_CenterDistanceMode = 2)
        XmlString.Append("        <Value>300</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_OptionsInvoked</ID>")              ' If True, then the XML document MUST also contain a valid OptionalInputs element. If it's false, you don't need the OptionalInputs element.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_OrderDrive</ID>")                  ' Always set ReqInp_OrderDrive to False. It is intended to be used by internal PTS applications only.
        XmlString.Append("        <Value>False</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_ServiceFactor</ID>")               ' The service factor.
        XmlString.Append("        <Value>1.5</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_VariableSpeed</ID>")               ' True to generate variable speed drive solutions, false to generate fixed speed drive solutions.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_OutputMode</ID>")                  ' If this is 1, then then the optional minimum and maximum pitch diameter limits and the maximum face width are specified in inches, the minimum and maximum belt speed are specified in feet per minute, and the maximum hub load is specified in pounds. If this is 2, then the units of measure are respectively millimeters, meters per second, and Newtons.
        XmlString.Append("        <Value>1</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_InputPowerMode</ID>")              ' If this is 1, then ReqInp_Horsepower contains a value in horsepower. If it is 2, then ReqInp contains a value in Kilowatts.
        XmlString.Append("        <Value>1</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_CenterDistanceMode</ID>")          ' If this is 1, then ReqInp_MinCenterDistance and ReqInp_MaxCenterDistance contain values in inches. If it is 2, then they contain values in millimeters.
        XmlString.Append("        <Value>1</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>SelectedMultID</ID>")                     ' Set this to zero. It is intended to be used by internal PTS applications only.
        XmlString.Append("        <Value>0</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_ProvideNetPrice</ID>")             ' True to provide dollar costs with the solutions, false to provide  "relative" costs.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>ReqInp_ProvideInterchanges</ID>")         ' True to provide interchanges with the solutions.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("    </RequiredInputs>")

        ' If ReqInp_OptionsInvoked is True, then the XML document MUST also contain a valid OptionalInputs element. If it's false, you don't need the OptionalInputs element.

        XmlString.Append("    <OptionalInputs>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_Allow3VXBelts</ID>")               ' True if solutions with 3VX belts are allowed, false otherwise. 
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_Allow4LBelts</ID>")                ' True if solutions with 4L belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_Allow5LBelts</ID>")                ' True if solutions with 5L belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_Allow5VBelts</ID>")                ' True if solutions with 5V belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_Allow5VXBelts</ID>")               ' True if solutions with 5VX belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_Allow8VBelts</ID>")                ' True if solutions with 8V belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_AllowABelts</ID>")                 ' True if solutions with A belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_AllowAXBelts</ID>")                ' True if solutions with AX belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_AllowBBelts</ID>")                 ' True if solutions with B belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_AllowBrowningBushedSheaves</ID>")  ' True if solutions with Browning bushed Sheaves are allowed, false otherwise. Note that this is meaningful for fixed speed drives only. For variable speed drives, all mounting styles are always considered.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_AllowBXBelts</ID>")                ' True if solutions with BX belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_AllowCBelts</ID>")                 ' True if solutions with C belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_AllowCXBelts</ID>")                ' True if solutions with CX belts are allowed, false otherwise.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_AllowFinishedBoreSheaves</ID>")    ' True if solutions with finished bore sheaves are allowed, false otherwise. Note that this is meaningful for fixed speed drives only. For variable speed drives, all mounting styles are always considered.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_AllowQDBushedSheaves</ID>")        ' True if solutions with QD bushed sheaves are allowed, false otherwiae. Note that this is meaningful for fixed speed drives only. For variable speed drives, all mounting styles are always considered.
        XmlString.Append("        <Value>True</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_ConformToNEMAStandard</ID>")       ' True if solutions must conform to NEMA standards, false otherwise.
        XmlString.Append("        <Value>False</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_LimitHubLoad</ID>")                ' True if solutions must have a hub load less than or equal to a specified maximum value. False otherwise.
        XmlString.Append("        <Value>False</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MaxBeltFPM</ID>")                  ' Maximum belt speed allowed. If ReqInp_OutputMode = 1, then the value is in feet per minute. If ReqInp_OutputMode = 2, then the value is in meters per second.
        XmlString.Append("        <Value>6500</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MaxDrivenPD</ID>")                 ' Maximum pitch diameter of driven sheaves allowed. If ReqInp_OutputMode = 1, then the value is inches. If ReqInp_OutputMode = 2, then the value is in millimeters.
        XmlString.Append("        <Value>63.8</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MaxDriverPD</ID>")                 ' Maximum pitch diameter of driver sheaves allowed. If ReqInp_OutputMode = 1, then the value is inches. If ReqInp_OutputMode = 2, then the value is in millimeters.
        XmlString.Append("        <Value>63.8</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MaxFaceWidth</ID>")                ' Maximum face width of sheaves allowed. If ReqInp_OutputMode = 1, then the value is inches. If ReqInp_OutputMode = 2, then the value is in millimeters.
        XmlString.Append("        <Value>19</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MaxHubLoad</ID>")                  ' Maximum hub load allowed, if OptInp_LimitHubLoad is true. Not meaningful if OptInp_LimitHubLoad is false.
        XmlString.Append("        <Value>9999</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MaxNumGrooves</ID>")               ' Minimum number of sheave grooves allowed.
        XmlString.Append("        <Value>16</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MinBeltFPM</ID>")                  ' Minimum belt speed allowed. If ReqInp_OutputMode = 1, then the value is in feet per minute. If ReqInp_OutputMode = 2, then the value is in meters per second.
        XmlString.Append("        <Value>900</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MinDrivenPD</ID>")                 ' Minimum pitch diameter of driven sheaves allowed. If ReqInp_OutputMode = 1, then the value is inches. If ReqInp_OutputMode = 2, then the value is in millimeters.
        XmlString.Append("        <Value>1.5</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MinDriverPD</ID>")                 ' Minimum pitch diameter of driver sheaves allowed. If ReqInp_OutputMode = 1, then the value is inches. If ReqInp_OutputMode = 2, then the value is in millimeters.
        XmlString.Append("        <Value>1.5</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MinNumGrooves</ID>")               ' Minimum number of sheave grooves allowed.
        XmlString.Append("        <Value>1</Value>")
        XmlString.Append("      </Input>")

        ' Explanation of the Optinp_MaxSpeedVariation and OptInp_MinSpeedVariation elements:

        ' For fixed speed drives (ReqInp_VariableSpeed = False), these percentage values establish the highest and lowest acceptable actual driven speed for solutions.
        ' For example, if the max value is 5% and the min value is 3%, and the desired driven speed is 1000 RPM, then only solutions whose actual driven speeds are between 970 (1000 - 3%) and 1050 (1000 + 5%) will be included.

        ' For variable speed drives where the driven speed is specified as the maximum speed desired (ReqInp_VariableSpeed = True and ReqInp_DrivenSpeedIsMidrange = False), it works similarly as fixed speed drives, but the actual driven speed calculation is done using the driver sheave's maximum PD.

        ' Note that for these two cases, as these two percentage values get LARGER, more solutions will be included. As these values get SMALLER, fewer solutions will be included.

        ' For variable speed drives where the driven speed is specified as the middle of a speed range (ReqInp_VariableSpeed = True and ReqInp_DrivenSpeedIsMidrange = True), these elements mean something different: They mean that the driver sheave must be adjustable enough to achieve driven speeds that FULLY COVER the range.
        ' For example, if the max value is 5% and the min value is 3%, and the desired driven speed is 1000 RPM, then only solutions whose driver sheaves can be adjusted enough to achieve both 970 RPM *AND* 1050 RPM will be included.
        ' Note that for this case, this means that as these two percentage values get LARGER, fewer solutions will be included (since there will be fewer driver/driven sheave combinations where the driver sheave can be adjusted enough.)

        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MaxSpeedVariation</ID>")
        XmlString.Append("        <Value>3</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_MinSpeedVariation</ID>")
        XmlString.Append("        <Value>3</Value>")
        XmlString.Append("      </Input>")

        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_NEMANumber</ID>")                  ' NEMA frame size that solutions must conform to, if OptInp_ConformToNEMAStandard is true. Not meaningful if OptInp_ConformToNEMAStandard is false.
        XmlString.Append("        <Value>0</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_UseDesignatedPartsOnly</ID>")      ' True if solutions must contain "designated" parts only; false otherwise.
        XmlString.Append("        <Value>False</Value>")
        XmlString.Append("      </Input>")
        XmlString.Append("      <Input>")
        XmlString.Append("        <ID>OptInp_UseMinSpeedInHorsepowerCalculation</ID>")  ' For variable speed drives, this is true if the horsepower should be calculated using the pitch diameter of the driver sheave fully opened (the driver sheave's minimum pitch diameter).
        XmlString.Append("        <Value>False</Value>")                                ' It is false if the horsepower should be calculated using the pitch diameter of the driver sheave fully closed (the driver sheave's maximum pitch diameter).
        XmlString.Append("      </Input>")                                              ' It is not meaningful for fixed speed drives.
        XmlString.Append("    </OptionalInputs>")
        XmlString.Append("  </InputString>")
        XmlString.Append("</Main>")


        Dim XmlDocument As New XmlDocument()
        XmlDocument.LoadXml(XmlString.ToString())

        Return XmlDocument

    End Function

    ''' <summary>
    ''' Creates a formatted string version (suitable for displaying in a textbox) of the supplied XmlDocument.
    ''' </summary>
    ''' <param name="XmlDocument">The XML document.</param>
    ''' <param name="IndentChar">The character to use for indenting.</param>
    ''' <param name="Indentation">How many IndentChars to write for each level in the hierarchy.</param>
    ''' <returns>A formatted string version (suitable for displaying in a textbox) of the supplied XmlDocument.</returns>
    Private Function FormattedXmlString(ByVal XmlDocument As XmlDocument, ByVal IndentChar As Char, ByVal Indentation As Integer) As String
        Using StringWriter As New System.IO.StringWriter()

            Using XmlWriter As New XmlTextWriter(StringWriter)
                XmlWriter.Formatting = Formatting.Indented
                XmlWriter.IndentChar = IndentChar
                XmlWriter.Indentation = Indentation

                XmlDocument.WriteTo(XmlWriter)
                XmlWriter.Flush()

                Return StringWriter.ToString()
            End Using

        End Using

    End Function


    ''' <summary>
    ''' Takes a Solution element from the Results XML document returned by the PTS configurator, and returns a new DriveSolution object.
    ''' </summary>
    ''' <param name="SolutionElement">A Solution element from the Results XML document returned by the PTS configurator</param>
    Private Function DriveSolutionExtractedFromSolutionElement(ByVal SolutionElement As XmlNode) As DriveSolution

        ' Look at all of the Property elements, and build a dictionary of all the name/value pairs.

        Dim NameValuePairs As New Dictionary(Of String, String)

        For Each Element As XmlNode In SolutionElement.SelectNodes("Property")
            NameValuePairs.Add(Element.SelectSingleNode("Name").InnerText, Element.SelectSingleNode("Value").InnerText)
        Next

        ' The driven speed returned in the PTS configurator Results XML is actually two values separated by a forward slash ("/"). 
        ' For fixed speed drives, these two values are always identical. For variable speed drives, the first value is the actual driven speed
        ' at the driver sheave fully opened, and the second value is the actual driven speed at the driver sheave fully closed.

        Dim ActualDrivenSpeeds() As String = NameValuePairs("ActualDrivenShaftSpeed").Split("/"c)

        ' Now extract the interchanges.

        Dim Interchanges As New List(Of Interchange)

        For Each Element As XmlNode In SolutionElement.SelectNodes("Interchanges/Interchange")
            Interchanges.Add(New Interchange(Element.SelectSingleNode("DriverSheave").InnerText, Element.SelectSingleNode("DriverBushing").InnerText, Element.SelectSingleNode("DrivenSheave").InnerText, Element.SelectSingleNode("DrivenBushing").InnerText))
        Next

        Return New DriveSolution(SolutionElement.SelectSingleNode("ID").InnerText, NameValuePairs("DriverSheave"), NameValuePairs("DriverBushing"), NameValuePairs("DrivenSheave"), NameValuePairs("DrivenBushing"), NameValuePairs("Belt"), Convert.ToInt32(NameValuePairs("BeltQty")), Convert.ToDouble(NameValuePairs("ActualCenterDistance")), Convert.ToDouble(NameValuePairs("ActualServiceFactor")), Convert.ToInt32(ActualDrivenSpeeds(0)), Convert.ToInt32(ActualDrivenSpeeds(1)), Convert.ToDecimal(NameValuePairs("Cost")), NameValuePairs("Comment1"), NameValuePairs("Comment2"), Interchanges)

    End Function

    ''' <summary>
    ''' Takes a DriveSolution object and generates a string of HTML suitable for inclusion in the formatted table of solutions.
    ''' </summary>
    ''' <param name="DriveSolution">The drive solution.</param>
    ''' <param name="IncludeSolutionId">True to include the solution ID in the first column of the row; false to not include it. This is to handle the "EPT Solution" case, where we don't want to show the "EPTSolution" ID.</param>
    ''' <returns>A string of HTML suitable for inclusion in the formatted table of solutions.</returns>
    Private Function FormattedDriveSolution(ByVal DriveSolution As DriveSolution, ByVal IncludeSolutionId As Boolean) As String

        With DriveSolution

            Dim Rows As New StringBuilder()

            Rows.Append("<tr>")
            Rows.Append("<td>" & If(IncludeSolutionId, .SolutionId, "") & "</td>")
            Rows.Append("<td>" & .DriverSheave & "</td>")
            Rows.Append("<td>" & .DriverBushing & "</td>")
            Rows.Append("<td>" & .DrivenSheave & "</td>")
            Rows.Append("<td>" & .DrivenBushing & "</td>")
            Rows.Append("<td>" & .Belt & "</td>")
            Rows.Append("<td>" & .BeltQuantity.ToString() & "</td>")
            Rows.Append("<td>" & .ActualCenterDistance.ToString() & "</td>")
            Rows.Append("<td>" & .ActualServiceFactor.ToString() & "</td>")
            Rows.Append("<td>" & .ActualDrivenSpeedAtSheaveFullyClosed.ToString() & "/" & .ActualDrivenSpeedAtSheaveFullyOpened.ToString() & "</td>")
            Rows.Append("<td>" & .Cost.ToString() & "</td>")
            Rows.Append("</tr>")

            Rows.AppendLine()

            Rows.AppendLine("<tr><td></td><td colspan='10' class='Comment'>" & .VariableSpeedDriveAdjustmentComment & "</tr>")
            Rows.AppendLine("<tr><td></td><td colspan='10' class='Comment'>" & .TensioningInstructionsComment & "</tr>")

            ' Interchanges.

            Rows.AppendLine("<tr><td colspan='11'></td></tr>")

            For Each Interchange In .Interchanges
                Rows.AppendLine("<tr><td></td><td>" & Interchange.DriverSheave & "</td><td>" & Interchange.DriverBushing & "</td><td>" & Interchange.DrivenSheave & "</td><td>" & Interchange.DrivenBushing & "</td></tr>")
            Next

            Return Rows.ToString()
        End With

    End Function

    ''' <summary>
    ''' Takes the Results XmlDocument created by the configurator, and generates an HTML table.
    ''' </summary>
    ''' <param name="ConfiguratorResults">The results produced by the configurator.</param>
    ''' <returns>A formatted version of the results.</returns>
    Private Function FormattedConfiguratorResults(ByVal ConfiguratorResults As XmlDocument) As String

        Dim ResultsHtml As New StringBuilder()

        Dim DriveSolutions As New List(Of DriveSolution)

        For Each SolutionElement As XmlNode In ConfiguratorResults.SelectNodes("SolutionString/Solutions/Solution")
            DriveSolutions.Add(DriveSolutionExtractedFromSolutionElement(SolutionElement))
        Next

        ResultsHtml.AppendLine("<table border='0' with='100%'>")
        ResultsHtml.AppendLine("<tr><th>No.</th><th>Driver Sheave</th><th>Driver Bushing</th><th>Driven Sheave</th><th>Driven Bushing</th><th>Belt</th><th>Qty</th><th>Actual C.D.</th><th>Actual S.F.</th><th>Driven Speed</th><th>Cost</th></tr>")

        For Each DriveSolution In DriveSolutions
            ResultsHtml.AppendLine(FormattedDriveSolution(DriveSolution, True))
        Next

        Dim EptSolutionElement = ConfiguratorResults.SelectSingleNode("SolutionString/EPTSolution/Solution")

        If Not EptSolutionElement Is Nothing Then
            ResultsHtml.AppendLine("<tr><td colspan=11>Drives above meet your criteria - Selection below is best disregarding options</td></tr>")
            ResultsHtml.Append(FormattedDriveSolution(DriveSolutionExtractedFromSolutionElement(EptSolutionElement), False))
        End If
        ResultsHtml.AppendLine("</table>")

        Return ResultsHtml.ToString()

    End Function


    Private Sub Button1_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Button1.Click

        Dim WebDocumentPrefix = "<html><head><style type='text/css'>body, table, tr, td {font-family: verdana; font-size: 8pt;} .Comment {font-family: verdana; font-size: 7pt;}</style></head><body>"
        Dim WebDocumentSuffix = "</body></html>"

        Try

            Dim InputsXmlDocument As New XmlDocument

            ' Load the XML from the text box.

            InputsXmlDocument.LoadXml(txtInputXml.Text)

            ' Create an instance of the configurator, passing the Inputs XML document we just created from the text box.

            Dim Configurator As New PTS.Library.VbeltDriveLibrary.Configurator(InputsXmlDocument)

            ' Call the SolveAndValidate method of the configurator to actually configure ("solve") the drive. This method will validate the inputs in InputsXmlDocument, and, if there are no problems 
            ' with the inputs, will then solve the drive, place the results in the Results property, and return true. If there ARE problems with the inputs, the method will place the appropriate error messages in
            ' the Validator property, and return false. It is important to check the return code of SolveAndValidate(), and, if it is false, NOT try to reference Results - in that case, it will be null.

            If Configurator.SolveAndValidate() Then

                ' There were no problems with the inputs. Now we can extract the drive solutions from the XML document contained in the Results property.

                webResults.DocumentText = WebDocumentPrefix & FormattedConfiguratorResults(Configurator.Results) & WebDocumentSuffix
                txtResultsXml.Text = FormattedXmlString(Configurator.Results, " "c, 2)
            Else
                ' There was at least one problem with our inputs (they failed the validation tests.) There will be a set of error messages associated with the "main" inputs, 
                ' a set of error messages associated with the "optional" inputs, and a set of errors associated with the NEMA Standards check.

                Dim ResultsHtml As New StringBuilder()

                ResultsHtml.AppendLine("Your input has the following problem(s):<br /><br />")

                For Each Element As XmlNode In Configurator.Validator.SelectNodes("Validator/CheckMainInputs/Errors/Error/Description")
                    ResultsHtml.AppendLine(Element.InnerText & "<br />")
                Next
                For Each Element As XmlNode In Configurator.Validator.SelectNodes("Validator/CheckOptionalInputs/Errors/Error/Description")
                    ResultsHtml.AppendLine(Element.InnerText & "<br />")
                Next

                ' NEMA validation results are reported differently than the validation of the main and optional inputs.

                If Configurator.Validator.SelectSingleNode("Validator/CheckNEMAStandards/Validated").InnerText.ToLower() = "false" Then
                    Dim element = Configurator.Validator.SelectSingleNode("Validator/CheckNEMAStandards/Reason")
                    ResultsHtml.AppendLine(element.InnerText & "<br />")
                End If

                webResults.DocumentText = WebDocumentPrefix & ResultsHtml.ToString() & WebDocumentSuffix

                ' Clear out the Results XML text box, since there were validation errors.

                txtResultsXml.Text = String.Empty
            End If


            ' If the XML we pass to the configurator is badly formed, Configurator.SolveAndValidate() might throw an exception, so catch and show the exception info to the user.
            ' (This can happen if, for example, a required element is missing. Those kinds of problems will not be reported via the Configurator.Validator object.)

        Catch ex As Exception
            webResults.DocumentText = WebDocumentPrefix & ex.ToString() & WebDocumentSuffix
            txtResultsXml.Text = String.Empty
        End Try



    End Sub

    Private Sub Form1_Load(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles MyBase.Load

        ' Load the text box with some sample XML.

        ' NOTE: Replace "c:\XmlDataFiles" with the name of the directory containing the six XML files containing product data
        ' ("Belts.xml", "Bushings.xml", "DesignatedParts.xml", "FixedPitchSheaves.xml", "Multipliers.xml" and "VariablePitchSheaves.xml")

        txtInputXml.Text = FormattedXmlString(XmlDocumentForConfigurator("c:\XmlDataFiles"), " "c, 2)

    End Sub
End Class
