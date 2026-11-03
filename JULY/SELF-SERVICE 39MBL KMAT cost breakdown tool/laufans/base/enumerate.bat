set CMDPREFIX=java  -Xmx800m -cp C:/Users/jareddavis/Documents/prj/REmanipulation/REmanipulation/dist/REmanipulation.jar

set OUTPATH=C:/Users/jareddavis/Documents/prj/ahu/costcheck/laufans/base/

set LOG=%OUTPATH%log.txt
set LENGTH=18

echo start of extract %date% %time% >%LOG%




%CMDPREFIX%  com.carrier.utc.eng.perfcalc.utility.AutomatonCommand UNION %OUTPATH%basere.txt OUTPUT=%OUTPATH%base.a>>%LOG%
%CMDPREFIX%  com.carrier.utc.eng.perfcalc.utility.AutomatonCommand UNION %OUTPATH%basere1.txt OUTPUT=%OUTPATH%base.a1>>%LOG%
rem %CMDPREFIX%  com.carrier.utc.eng.perfcalc.utility.AutomatonCommand UNION %OUTPATH%basere2.txt OUTPUT=%OUTPATH%base.a2>>%LOG%
rem %CMDPREFIX%  com.carrier.utc.eng.perfcalc.utility.AutomatonCommand UNION %OUTPATH%basere3.txt OUTPUT=%OUTPATH%base.a3>>%LOG%

%CMDPREFIX%  com.carrier.utc.eng.perfcalc.utility.AutomatonCommand INTERSECTION %OUTPATH%base.a %OUTPATH%base.a1 OUTPUT=%OUTPATH%base.b>>%LOG%
rem %CMDPREFIX%  com.carrier.utc.eng.perfcalc.utility.AutomatonCommand UNION %OUTPATH%base.b %OUTPATH%base.a2 OUTPUT=%OUTPATH%base.bb>>%LOG%
rem %CMDPREFIX%  com.carrier.utc.eng.perfcalc.utility.AutomatonCommand UNION %OUTPATH%base.bb %OUTPATH%base.a3 OUTPUT=%OUTPATH%base.bbb>>%LOG%

rem enumerate final automaton
%CMDPREFIX%  com.carrier.utc.eng.perfcalc.utility.EnumerateAutomaton %OUTPATH%base.b .................. %LENGTH% %OUTPATH%39mb.parts.txt >>%LOG%

pause


