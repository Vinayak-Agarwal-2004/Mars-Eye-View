<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# I wish to collect data from a bunch of news sources

RSS feeds provides summaries
So how do I get full length content for code

You use the RSS feed only to discover article links, then fetch and parse each article page yourself to get the full text.[^1_1][^1_2][^1_3]

### Overall approach

1. Parse the RSS feed to get items.
2. For each item, grab the `<link>` URL.
3. For each URL, download the HTML and run a full‑text extractor (e.g. `newspaper3k` or `readability-lxml`).[^1_4][^1_3][^1_5][^1_6][^1_7]

### Minimal working example (Python)

```python
import feedparser
from newspaper import Article  # pip install newspaper3k

def fetch_full_articles(rss_url: str):
    feed = feedparser.parse(rss_url)  # parse RSS. [web:2][web:3]
    articles = []

    for entry in feed.entries:
        url = entry.link

        art = Article(url)            # create article object. [web:6][web:12]
        art.download()                # download HTML. [web:6][web:12]
        art.parse()                   # extract main text & metadata. [web:6][web:12]

        articles.append({
            "title": art.title,
            "url": url,
            "authors": art.authors,
            "published": art.publish_date,
            "text": art.text,
        })

    return articles

if __name__ == "__main__":
    feed_url = "https://feeds.bbci.co.uk/news/rss.xml"
    for art in fetch_full_articles(feed_url):
        print(art["title"])
        print(art["text"][:500], "...\n")
```

`newspaper3k` handles boilerplate stripping, multi‑language, and metadata, which is why it’s commonly paired with `feedparser` for “RSS → full article” workflows.[^1_3][^1_6][^1_7][^1_4]

### Alternative: readability-lxml

If you want more control or to plug into your own requests stack:

```python
import feedparser
import requests
from readability import Document  # from readability-lxml. [web:10]

def fetch_full_articles_readability(rss_url: str):
    feed = feedparser.parse(rss_url)
    articles = []

    for entry in feed.entries:
        url = entry.link
        html = requests.get(url, timeout=10).text

        doc = Document(html)              # build readability doc. [web:10][web:13]
        title = doc.short_title()
        content_html = doc.summary()      # main content HTML. [web:10][web:13]

        articles.append({
            "title": title,
            "url": url,
            "content_html": content_html,
        })

    return articles
```

This pattern generalizes to “bunch of news sources”: just loop over a list of RSS URLs and aggregate the outputs into your datastore.[^1_6][^1_3]
<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://www.geeksforgeeks.org/python/extract-feed-details-from-rss-in-python/

[^1_2]: https://dataimpulse.com/blog/how-to-parse-xml-and-rss-feeds-in-python/

[^1_3]: https://www.geeksforgeeks.org/python/automatic-news-scraping-with-python-newspaper-and-feedparser/

[^1_4]: https://github.com/vectoroid/newspaper3k

[^1_5]: https://pypi.org/project/readability-lxml/

[^1_6]: https://www.newscatcherapi.com/blog-posts/python-web-scraping-libraries-to-mine-news-data

[^1_7]: https://newspaper.readthedocs.io/en/latest/

[^1_8]: https://stackoverflow.com/questions/56829861/how-to-scrape-google-news-articles-content-from-google-news-rss

[^1_9]: https://www.youtube.com/watch?v=2JGU9S2gCMg

[^1_10]: https://www.reddit.com/r/Python/comments/q8hm0q/pysimplerss_an_rss_reader_made_with_python_that/

[^1_11]: https://generalistprogrammer.com/tutorials/readability-lxml-python-package-guide

[^1_12]: https://newspaper.readthedocs.io

[^1_13]: https://github.com/predatell/python-readability-lxml/blob/master/readability_lxml/readability.py

[^1_14]: https://alexmiller.phd/posts/python-3-feedfinder-rss-detection-from-url/

[^1_15]: https://www.scraperapi.com/blog/python-newspaper3k/

