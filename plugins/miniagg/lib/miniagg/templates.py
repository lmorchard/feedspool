""" """

UNICODE_ENC  = 'utf-8'

TMPL_MAIN_PAGE = """
    <html>

      <head> <title>feedReactor</title> </head>

      <frameset name="frameset" cols="125,*" framespacing="3" topmargin="0" 
                leftmargin="0" marginheight="0" marginwidth="0" border="1" 
                bordercolor="#dddddd">

        <frame src="nav.html" name="nav" topmargin="0" leftmargin="10" marginheight="0" marginwidth="10" frameborder="1" border="1" scrolling="yes" target="main" />

        <frame src="%(path)s" name="main" topmargin="0" leftmargin="10" marginheight="0" marginwidth="10" frameborder="1" border="1" scrolling="yes" />
        
      </frameset>
      
    </html>
"""

TMPL_INDEX_PAGE = """
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <title>MiniAgg!</title>
        <base target="main" />
        <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
        <link rel="stylesheet" href="css/styles.css" type="text/css" />
        <script src="js/main.js" type="text/javascript"></script>
    </head>
    <body>
        %(page_list)s
    </body>
</html>
"""

TMPL_LIST_START = """
    <ul class="newsindex">
        <h1><a href="%(yy)s/%(mm)s/%(dd)s/">%(yy)s-%(mm)s-%(dd)s</a></h1>
"""

TMPL_INDEX_PAGE_ITEM  = """
        <li>
            <a href="%(path)s">
                <abbr title="%(yy)s-%(mm)s-%(dd)sT%(h)s:%(m)s:%(s)s">
                    %(h)s:%(m)s:%(s)s
                </abbr>
            </a>
        </li>
"""

TMPL_LIST_END = """
    </ul>
"""

TMPL_NEWS_PAGE  = """
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <title>News for %(now)s</title>
        <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
        <link rel="stylesheet" href="../../../css/styles.css" type="text/css" />
        <script type="text/javascript" src="../../../js/main.js"></script>
    </head>
    <body>
        <h1>News for %(now)s</h1>
        <ul class="feeds">
            %(feeds)s
        </ul>
    </body>
</html>
"""

TMPL_NEWS_FEED  = """
    <li class="feed expanded">
        <h2><a href="%(feed.link)s">%(feed.title)s</a></h2>
        <ul class="entries">
            %(feed.entries)s
        </ul>
    </li>
"""

TMPL_NEWS_ENTRY = """
    <li class="entry">
        <h3 class="entryheader">
            <span class="entrydate">%(entry.date)sT%(entry.time)s</span> 
            <a class="entrylink" href="%(entry.link)s">%(entry.title)s</a>
        </h3>
        <ul class="entrycontent">
            <li class="summary">%(entry.summary)s</li>
            <li class="content">%(entry.content)s</li>
        </ul>
    </li>
"""

