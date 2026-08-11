<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:sm="http://www.sitemaps.org/schemas/sitemap/0.9">
  <xsl:output method="html" encoding="UTF-8" indent="yes" />
  <xsl:template match="/">
    <html lang="en">
      <head>
        <title>Sitemap - Locus AI</title>
        <meta charset="UTF-8" />
        <style>
          body { font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 40px; color: #24242a; }
          h1 { font-size: 20px; margin-bottom: 4px; }
          p.count { color: #6b7280; margin-top: 0; font-size: 14px; }
          table { border-collapse: collapse; width: 100%; max-width: 760px; margin-top: 16px; }
          th { text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: #9ca3af; padding: 8px 12px; border-bottom: 2px solid #e5e7eb; }
          td { padding: 10px 12px; border-bottom: 1px solid #f0f0f4; font-size: 14px; }
          a { color: #5b52e8; text-decoration: none; }
          a:hover { text-decoration: underline; }
        </style>
      </head>
      <body>
        <h1>Locus AI - Sitemap</h1>
        <p class="count">
          <xsl:value-of select="count(//sm:url)" /> URL(s)
        </p>
        <table>
          <tr>
            <th>URL</th>
            <th>Change frequency</th>
            <th>Priority</th>
          </tr>
          <xsl:for-each select="//sm:url">
            <tr>
              <td><a href="{sm:loc}"><xsl:value-of select="sm:loc" /></a></td>
              <td><xsl:value-of select="sm:changefreq" /></td>
              <td><xsl:value-of select="sm:priority" /></td>
            </tr>
          </xsl:for-each>
        </table>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
