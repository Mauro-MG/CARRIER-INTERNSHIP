<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="text" encoding="iso-8859-1"/>


 <xsl:template match="/">
 <xsl:apply-templates select="//*"/>
</xsl:template>

<xsl:template match="//*">
        <xsl:value-of select="@PartNumber"/>
 <xsl:text>&#x9;</xsl:text>
        <xsl:value-of select="@ListPrice"/>
 <xsl:text>&#x9;</xsl:text>
        <xsl:value-of select="@MultiplierSequence"/>
 <xsl:text>&#x9;</xsl:text>
        <xsl:value-of select="@Sequence"/>
 <xsl:text>&#x9;</xsl:text>
        <xsl:value-of select="@Value"/>
 <xsl:text>&#x9;</xsl:text>
        <xsl:value-of select="@Description"/>
 <xsl:text>&#x0D;</xsl:text> <xsl:text>&#x0a;</xsl:text>
</xsl:template>



</xsl:stylesheet>
