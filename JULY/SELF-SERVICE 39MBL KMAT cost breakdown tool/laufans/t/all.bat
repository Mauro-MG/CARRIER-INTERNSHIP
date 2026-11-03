del out.txt
for %%1 in (*.XML) do \util\xalan %%1 totsv.xsl >>out.txt