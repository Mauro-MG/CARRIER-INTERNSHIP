rem place the emerson dlls in the cd directory. Place the xml files in the directory listed as the 1st parameter
rem binds to port 8020 localhost
rem requires net 4
rem and: The .NET assemblies that comprise the PTS V-Belt Drive Configurator software:
rem   PTS.VbeltDriveLibrary.dll
rem   PTS.VbeltDriveConfigurator.dll
rem   EPT.Internet.ProductSelection.dll
rem   log4net.dll
cd C:\Users\jareddavis\Documents\prj\ahu\costcheck\laufans\emerson
WcfEmersonEXE.exe C:\Users\jareddavis\Documents\prj\ahu\costcheck\laufans http://127.0.0.1:8020 http://127.0.0.1:8020/SelectDrive