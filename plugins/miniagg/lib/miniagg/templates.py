""" """

UNICODE_ENC  = 'utf-8'

TMPL_INDEX = """
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <title>MiniAgg!</title>
        <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
        <link rel="stylesheet" href="css/styles.css" type="text/css" />
        <script src="js/main.js" type="text/javascript"></script>
    </head>
    <body>
    </body>
</html>
"""

TMPL_NEWS_PAGE  = """
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <title>News for %(now)s</title>
        <meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
        <link rel="stylesheet" href="css/styles.css" type="text/css" />
        <script src="js/main.js" type="text/javascript"></script>
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

