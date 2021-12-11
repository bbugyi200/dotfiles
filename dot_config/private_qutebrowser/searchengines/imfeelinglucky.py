"""Prints the URL of the First Google Search Result for the Given Query"""

##########################################################
#  http://edmundmartin.com/scraping-google-with-python/  #
##########################################################

import argparse
import re

from searchengines import utils


USER_AGENT = {
    "User-Agent": (
        "Mozilla/5.0 (X11; U; Linux i686; en-US) AppleWebKit/534.3 (KHTML, "
        "like Gecko) Chrome/6.0.472.63 Safari/534.3"
    )
}


def get_top_link(query: str) -> str:
    from bs4 import BeautifulSoup
    import requests  # pylint: disable=import-outside-toplevel

    try:
        html = _fetch_results(query)
    except requests.exceptions.HTTPError as e:
        result: str = e.response.url
        return result

    soup = BeautifulSoup(html, "html.parser")
    a_tags = soup.find_all("a", href=True)
    for a_tag in a_tags:
        match = re.match(r"^/url\?q=(.*?)&.*$", a_tag["href"])
        if match:
            result = match.group(1)
            return result

    div_tags = soup.find_all("div", attrs={"class": "g"})
    for div_tag in div_tags:
        a_tag = div_tag.find("a", href=True)
        if a_tag and a_tag != "#" and re.match("^http[s]?://", a_tag["href"]):
            result = a_tag["href"]
            return result

    return "https://www.google.com/search?q={}".format(utils.encode(query))


def _fetch_results(query: str) -> str:
    # dynamic import needed to work around weird qutebrowser bug with
    # 'cryptography' module
    import requests  # pylint: disable=import-outside-toplevel

    assert isinstance(query, str), "Search term must be a string"

    encoded_query = utils.encode(query)

    google_url = "https://www.google.com/search?q={}".format(encoded_query)
    response = requests.get(google_url, headers=USER_AGENT)
    response.raise_for_status()

    return response.text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Google Search Query")
    args = parser.parse_args()

    print(get_top_link(args.query))
