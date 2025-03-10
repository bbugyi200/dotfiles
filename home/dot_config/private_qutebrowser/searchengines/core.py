"""Core Classes of the 'searchengines' Package

This module is imported directly into the global scope of the 'searchengines'
package. All classes/functions must be added to __all__ or they will NOT be
made available.
"""

import re
from typing import Callable, Generator, List, Sequence, Type

from searchengines import imfeelinglucky as IFL
from searchengines import utils


# Custom Types
FilterType = Callable[[str], Sequence[str]]


class SearchEngine(str):
    """Dynamic SearchEngine for 'url.searchengines'

    Enables additional pattern matching

    Args:
        default_url: default URL to return from 'format'
        *url_objects: variable number of URL objects
    """

    def __new__(cls, default_url: str, *_url_objects: "URL") -> "SearchEngine":
        return super(SearchEngine, cls).__new__(cls, default_url)

    def __init__(self, default_url: str, *url_objects: "URL"):
        self.url_objects = url_objects + (URL(default_url, ".*"),)

    def format(self, *args: str, **kwargs: str) -> str:  # type: ignore
        args_list = list(args)

        term = args_list.pop(0)
        for url, pttrn, filter_ in self.url_objects:
            if re.match(pttrn, term):
                filtered = filter_(utils.filter_aliases(term))

                if isinstance(filtered, str):
                    filtered = (filtered,)

                try:
                    formatted_url = str.format(
                        url, *filtered, *args_list, **kwargs
                    )
                except Exception as e:
                    raise RuntimeError(
                        "There was an error when formatting the url. Printing"
                        " local variables...\n{}".format(
                            "\n".join(
                                "{}={}".format(k, repr(v))
                                for k, v in locals().items()
                            )
                        )
                    ) from e

                if LuckyURL.is_lucky(formatted_url):
                    formatted_url = LuckyURL.get_top_link(formatted_url)

                return formatted_url

        return str.format(term, *args_list, **kwargs)


class URL:
    """URL Object

    Used to initialize a SearchEngine object.

    Args:
        url (str):
            url string with braces ({}) to represent the search query
        pattern (str):
            regex pattern used to identify when this URL should be used.
        filter_ (callable, optional):
            used to filter out garbage in the search query.
    """

    def __init__(
        self, url: str, pattern: str = None, filter_: FilterType = None
    ):
        self.url = url

        if pattern is None:
            self.pattern = ".*"
        else:
            self.pattern = utils.encode(pattern)

        if filter_ is None:
            self.filter = lambda x: x
        else:
            self.filter = filter_

    def __iter__(self) -> Generator:
        return (x for x in [self.url, self.pattern, self.filter])


class LuckyURL(URL):
    """Queries that Utilize Google's 'I'm Feeling Lucky' Feature"""

    slash_pattern = r"^(\|/|%2F)"
    at_pattern = r"^.*(@|%40)$"
    pattern = rf"{slash_pattern}|{at_pattern}"

    # dummy url is needed to pass qutebrowser's validation checks
    start_mark = "https://imfeelinglucky/"
    end_mark = "@@@"

    def __init__(
        self,
        url: str,
        pattern: str = None,
        filter_: FilterType = None,
        suffix: str = "",
    ):
        if pattern is not None:
            self.pattern = pattern

        if filter_ is not None:
            self.filter = filter_  # type: ignore

        super().__init__(
            self.make_lucky(url, suffix=suffix), self.pattern, self.filter
        )

    @classmethod
    def make_lucky(cls, query: str, suffix: str = "") -> str:
        query = utils.encode(query)
        fmt_url = "{}{{}}{}{}".format(
            cls.start_mark,
            cls.end_mark,
            re.sub(r"\{(\d*)\}", r"{{\1}}", suffix),
        )
        return fmt_url.format(query)

    @classmethod
    def filter(cls, query: str) -> str:  # pylint: disable=method-hidden
        result = re.sub(cls.slash_pattern, "", query)

        if result.endswith("@"):
            result = result[:-1]

        if result.endswith("%40"):
            result = result[:-3]

        return result

    @classmethod
    def is_lucky(cls, url: str) -> bool:
        return url.startswith(cls.start_mark)

    @classmethod
    def get_top_link(cls, url: str) -> str:
        query, suffix = url[len(cls.start_mark) :].split(cls.end_mark)
        top_link = IFL.get_top_link(query)
        return "{}/{}".format(top_link, suffix) if suffix else top_link


def IntURLFactory(n: int) -> Type[URL]:
    """Factory for URL Objects with patterns that start with Int Arguments

    Args:
        n (int): number of integers that the pattern starts with
    """
    pttrn_fmt = "^{}[A-z]"
    int_pttrn = "[0-9]+ " * n

    class IntURL(URL):
        pattern = pttrn_fmt.format(int_pttrn)

        def __init__(self, url: str, filter_: FilterType = None):
            if filter_ is not None:
                self.filter = filter_  # type: ignore

            super().__init__(url, self.pattern, self.filter)

        @classmethod
        def filter(  # pylint: disable=method-hidden
            cls, query: str
        ) -> Sequence:
            nums: List = re.split(utils.encode(" "), query, maxsplit=n)

            result = nums[:]
            for i in range(n):
                result[i] = int(nums[i])

            return result

    return IntURL


OneIntURL = IntURLFactory(1)
TwoIntURL = IntURLFactory(2)
