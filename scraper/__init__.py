"""web-scraper toolkit: fetch + extract data from static pages, JS-rendered
pages, and JSON/XML APIs.

Public surface::

    from scraper.fetchers import fetch, FetchResult
    from scraper import extractors, output
"""

from .fetchers import FetchResult, fetch  # noqa: F401

__all__ = ["fetch", "FetchResult"]
__version__ = "1.0.0"
