"""Qutebrowser Configuration"""

from functools import partial, wraps
import os
from pathlib import Path
import platform
import re
from typing import Callable, Dict, Iterator, List, Tuple, Union

import yaml

import searchengines as SE
from searchengines import utils


os.environ[
    "PATH"
] = f"{os.getenv('HOME')}/.local/bin:/usr/local/bin:{os.getenv('PATH', '')}"


c = c  # type: ignore  # noqa: F821  # pylint: disable=undefined-variable,self-assigning-variable
config = config  # type: ignore  # noqa: F821  # pylint: disable=undefined-variable,self-assigning-variable

# Load autoconfig.yml
config.load_autoconfig(False)  # type: ignore

# Custom Types
SetupFunc = Callable[[], None]

PIRATE_BAY = "https://thepiratebay0.org"


#####################################################################
#  Utils                                                            #
#####################################################################
def is_macos() -> bool:
    return "Darwin" in platform.version()


class SetupMaster:
    """Setup Master Class

    All setup functions MUST register with this class or they will not be
    called.
    """

    # Registered setup functions.
    _SETUP_FUNC_REGISTRY: List[SetupFunc] = []

    @classmethod
    def register(
        cls, setup_func: SetupFunc = None, *, debug: bool = False
    ) -> Callable:
        if setup_func is None:
            return partial(cls.register, debug=debug)

        @wraps(setup_func)
        def wrapped_setup_func() -> None:
            if debug:
                import pudb

                pudb.set_trace()  # type: ignore

            assert setup_func is not None
            return setup_func()

        cls._SETUP_FUNC_REGISTRY.append(wrapped_setup_func)
        return wrapped_setup_func

    @classmethod
    def run_all(cls) -> None:
        for setup_func in cls._SETUP_FUNC_REGISTRY:
            setup_func()


#####################################################################
#  Search Aliases                                                   #
#####################################################################
@SetupMaster.register
def setup_search_aliases() -> None:
    # These aliases will be substituted with their definitions when found
    # anywhere in the query of an ':open' command.
    search_aliases = {
        "aco": "Assassin's Creed Odyssey",
        "acv": "Assassin's Creed Valhalla",
        "al": "Arch Linux",
        "b": "Bash",
        "bcs": "Better Call Saul",
        "bnn": "Brooklyn Nine-Nine",
        "cl": "command-line",
        "cs": "Computer Science",
        "de": "Debian",
        "fcl": "from the command-line",
        "fn": "Fortnite",
        "ge": "Gentoo",
        "gh": "GitHub",
        "gl": "GitLab",
        "ha": "Haskell",
        "js": "JavaScript",
        "ks": "keyboard shortcut",
        "lcl": "Linux from the command-line",
        "lx": "Linux",
        "mac": "MacOS",
        "n": "AND",
        "o": "OR",
        "prom": "prometheus",
        "py": "Python",
        "qb": "qutebrowser",
        "rnm": "Rick and Morty",
        "rl": "Rocket League",
        "ru": "Rutgers",
        "sal": "average salary",
        "sd": "San Diego",
        "se": "Software Engineer",
        "sg": "Samsung Galaxy",
        "v": "vim",
        "ys": "Young Sheldon",
    }

    # Google's AROUND(N) Search Operator
    for i in range(1, 51):
        search_aliases[f"a{i}"] = f"AROUND({i})"

    # Set the utils module's search alias dictionary.
    utils.SEARCH_ALIASES = search_aliases


#####################################################################
#  Search Engines                                                   #
#####################################################################
def bang_pttrn() -> str:
    """
    Returns regex pattern that matches DuckDuckGo bangs that I like to use.
    """
    one_letter_bangs = [
        "a",  # Amazon
        "d",  # Dictionary
        "g",  # Google
        "m",  # Google Maps
        "t",  # Thesaurus
    ]
    two_letter_bangs = [
        "ho",  # Hoogle
        "wa",  # WolframAlpha
        "yt",  # YouTube
    ]
    long_bangs = [
        "ddg",  # DuckDuckGo
        "bang",  # DuckDuckGo Bang Search
        "giphy",  # Giphy.com
    ]

    all_bangs = one_letter_bangs + two_letter_bangs + long_bangs

    bang_fmt = "^({}) "
    return bang_fmt.format("|".join(all_bangs))


def lucky_url_with_suffix_arg(
    query: str, *, suffix: str, sep: str = "@"
) -> SE.LuckyURL:
    return SE.LuckyURL(
        query,
        "({}){}".format(  # pylint: disable=consider-using-f-string
            SE.LuckyURL.pattern, rf"[A-z][A-z0-9-_ ]* {sep}"
        ),
        lambda x: re.split(
            SE.utils.encode(f" {sep}"), SE.LuckyURL.filter(x), maxsplit=1
        ),
        suffix=suffix,
    )


@SetupMaster.register
def setup_search_engines() -> None:
    searchengines = {
        "2": "https://www.google.com/maps/dir/417+Cripps+Dr,+Mt+Holly,+NJ+08060/{}",
        "A": "https://www.amazon.com/gp/your-account/order-history/ref=ppx_yo_dt_b_search?opt=ab&search={}",
        "b": SE.static.stackoverflow(10, prefix="Bash"),
        "badge_logo": "https://simpleicons.org/?q={}",
        "bb": "http://bburl/{}",
        "bdpkg": "https://dpkg.dx.bloomberg.com/packages?search_term={}",
        "benv": "https://env-brd.prod.bloomberg.com/cluster/{}",
        "bgh": SE.SearchEngine(
            "https://bbgithub.dev.bloomberg.com/search?q={}",
            SE.URL(
                "https://bbgithub.dev.bloomberg.com/{0}/{1}",
                "^[^ ]+/[^ ]+$",
                lambda s: s.split("/"),
            ),
        ),
        "bghc": "https://bbgithub.dev.bloomberg.com/ComplianceSRE/{}",
        "bghe": "https://bbgithub.dev.bloomberg.com/EquitySRE/{}",
        "bghp": "https://bbgithub.dev.bloomberg.com/python/{}",
        "bgo": "https://gogl.prod.bloomberg.com/search?q={}&p=0",
        "bguts": "https://guts.prod.bloomberg.com/machines-clusters/{}",
        "bi": "https://infr.prod.bloomberg.com/clusters/{}",
        "bj": "https://jira.prod.bloomberg.com/browse/CSRE-{}",
        "bjaas": SE.SearchEngine(
            "https://bvault.jaas.dev.bloomberg.com/job/sre/job/{}",
            SE.URL(
                "https://bvault.jaas.dev.bloomberg.com/blue/organizations/jenkins/sre%2F{}/activity",
                "^@",
                lambda x: x.replace(SE.utils.encode("@"), ""),
            ),
        ),
        "bmo": SE.SearchEngine(
            SE.static.google("best movies of 20{}"),
            SE.OneIntURL(SE.static.google("best {1} movies of 20{0}")),
        ),
        "bog": "https://code.dev.bloomberg.com/source/search?q={}&defs=&refs=&path=&hist=&type=&project=basmsg&project=bbgithub&project=devsvn&project=dpkg&project=rapid&project=robo_svn",
        "bp": "https://bbgithub.dev.bloomberg.com/pages/ComplianceSRE/{}.html",
        "btu": "https://tutti.prod.bloomberg.com/search/?q={}",
        "bte": "https://cms.prod.bloomberg.com/team/dosearchsite.action?queryString={}",
        "bso": "https://engx.prod.bloomberg.com/search?q={}",
        "bsor": "https://sor.bdns.bloomberg.com/ui/servers/group/{}",
        "c": SE.static.stackoverflow(7, prefix="C"),
        "cc": SE.static.stackoverflow(5, prefix="C\\+\\+"),
        "DEFAULT": SE.SearchEngine(
            SE.static.google("{}"),
            SE.URL(SE.static.duckduckgo("{}"), "^!"),
            SE.URL(SE.static.duckduckgo("!{}"), bang_pttrn()),
            SE.LuckyURL("{}"),
        ),
        "dep": "https://packages.debian.org/search?keywords={}",
        "dvd": SE.static.google("{} DVD release date"),
        "eda": SE.SearchEngine(
            "http://web-prod.pr.edgelp.net:22051/find?names={}&days=3",
            SE.OneIntURL(
                "http://web-prod.pr.edgelp.net:22051/find?names={1}&days={0}"
            ),
        ),
        "edb": SE.SearchEngine(
            "http://web-prod.pr.edgelp.net:22052/find?names={}&days=3",
            SE.OneIntURL(
                "http://web-prod.pr.edgelp.net:22052/find?names={1}&days={0}"
            ),
        ),
        "eip": "https://gitlab.pr.edgelp.net/edgelp/prod/issues?scope=all&utf8=✓&state=opened&search={}",
        "emo": "https://emojipedia.org/search/?q={}",
        "emp": "https://gitlab.pr.edgelp.net/edgelp/prod/merge_requests/{}",
        "emw": "https://gitlab.pr.edgelp.net/edgelp/website/merge_requests/{}",
        "ep": SE.SearchEngine(
            SE.static.google("{} episodes"),
            SE.OneIntURL(SE.static.google("Season {0} {1} episodes")),
        ),
        "ew": "https://www.edgestreamlp.com/{}",
        "ews": "https://edgestream-staging.herokuapp.com/{}",
        "g4g": SE.static.site("www.geeksforgeeks.org"),
        "geb": "https://bugs.gentoo.org/buglist.cgi?bug_status=__open__&content={}&list_id=4089892&order=Importance&query_format=specific",
        "gep": SE.SearchEngine(
            SE.static.site("packages.gentoo.org", "gpo.zugaina.org"),
            SE.LuckyURL("{} site:packages.gentoo.org"),
        ),
        "gh": SE.SearchEngine(
            SE.static.site("github.com"),
            SE.LuckyURL("{} site:github.com"),
            SE.URL(
                "https://github.com/bbugyi200/{}",
                "^@",
                lambda x: x.replace(SE.utils.encode("@"), ""),
            ),
        ),
        "ghi": SE.SearchEngine(
            "https://github.com/bbugyi200/{}/issues",
            SE.URL(
                "https://github.com/bbugyi200/scripts/issues/{}", "^[0-9]+$"
            ),
            SE.OneIntURL("https://github.com/bbugyi200/{1}/issues/{0}"),
            lucky_url_with_suffix_arg(
                "{0} site:github.com",
                suffix="issues?&q=is%3Aissue+{1}",
                sep="@",
            ),
            lucky_url_with_suffix_arg(
                "{0} site:github.com", suffix="issues/{1}", sep="#"
            ),
            SE.LuckyURL("{} site:github.com", suffix="issues"),
        ),
        "ght": "https://github.com/bbugyi200/{}/graphs/traffic",
        "hex": "https://www.colorhexa.com/{}",
        "i": SE.SearchEngine("https://www.google.com/search?&tbm=isch&q={}"),
        "j": (
            "https://www.google.com/search?q={}&ibp=htl;jobs#fpstate=tldetail"
        ),
        "l": SE.static.stackoverflow(7, prefix="Linux"),
        "L": "https://lobste.rs/t/{}",
        "lh": "http://localhost:{}",
        "lhs": "https://localhost:{}",
        "li": SE.SearchEngine(
            SE.static.site("linkedin.com"),
            SE.URL(
                SE.static.site("linkedin.com", prefix="software"),
                "^@",
                lambda x: x.replace(SE.utils.encode("@"), ""),
            ),
        ),
        "lib": "http://libgen.is/search.php?req={}",
        "Lib": "https://libgen.me/search?q={}",
        "mac": "http://C02DR3Z2MD6R.local:{}",
        "ma": SE.static.site(
            "math.stackexchange.com", "tex.stackexchange.com"
        ),
        "mfp": "https://www.myfitnesspal.com/nutrition-facts-calories/{}",
        "ne": "https://www.newegg.com/p/pl?d={}",
        "p": SE.static.stackoverflow(7, prefix="Python"),
        "pgh": "https://github.com/python-boltons/{}",
        "pi": "https://pypi.org/project/{}",
        "pib": "https://pypi.org/project/bolton-{}",
        "pyl": "https://docs.python.org/3/library/{}",
        "pyl2": "https://docs.python.org/2.7/library/{}",
        "pss": "https://store.playstation.com/en-us/search/{}",
        "r": SE.static.site("reddit.com"),
        "rlp": "https://rocketleague.tracker.network/profile/ps/{}",
        "rpy": "https://realpython.com/search?q={}",
        "rtd": "https://{}.readthedocs.io/en/latest/",
        "s": SE.static.site("stackoverflow.com"),
        "shr": "https://shop.shoprite.com/store/1627666/search?displayType=&query={}&recipe=0&sponsored=5",
        "snyk": "https://snyk.io/advisor/search?source=python&q={}",
        "st": SE.static.google("set timer for {}"),
        "sub": SE.SearchEngine(
            SE.static.google("{} inurl:english site:subscene.com"),
            SE.LuckyURL("{0} inurl:english site:subscene.com"),
            SE.LuckyURL(
                "{2} S{0:02d}E{1:02d} inurl:english site:subscene.com",
                SE.TwoIntURL.pattern,
                SE.TwoIntURL.filter,
            ),
        ),
        "T": SE.SearchEngine(
            "https://1337x.unblocked.vet/search/{}/1/",
            SE.TwoIntURL(
                "https://1337x.unblocked.vet/search/{2} S{0:02d}E{1:02d}/1/"
            ),
            SE.OneIntURL(
                "https://1337x.unblocked.vet/search/{1} Season {0}/1/"
            ),
        ),
        "TT": SE.SearchEngine(
            f"{PIRATE_BAY}/search/{{}}",
            SE.TwoIntURL(f"{PIRATE_BAY}/search/{{2}} S{{0:02d}}E{{1:02d}}"),
            SE.OneIntURL(f"{PIRATE_BAY}/search/{{1}} Season"),
        ),
        "tb": SE.static.site("teamblind.com"),
        "ud": SE.static.site(
            "idioms.thefreedictionary.com",
            "en.wiktionary.org",
            "urbandictionary.com",
        ),
        "q": SE.static.google('"{}"'),
        "w": SE.static.site("en.wikipedia.org"),
        "W": SE.static.google("weather in {}"),
        "ytt": "https://www.youtube.com/results?search_query={}+Trailer",
    }

    for i in range(1, 11):
        searchengines[f"s{i}"] = SE.static.stackoverflow(i)
        searchengines[f"g{i}"] = SE.static.google("{}", max_years_old=i)

    c.url.searchengines = searchengines


#####################################################################
#  Command Aliases                                                  #
#####################################################################
@SetupMaster.register
def setup_cmd_aliases() -> None:
    command_aliases = {
        "libget": 'jseval -q document.querySelector("h2").click()',
        "lic": "spawn --userscript linkedin_connect",
        "mkpdf": (
            "set-cmd-text :spawn -v wkhtmltopdf {url} /home/bryan/Downloads/"
        ),
        "P": "spawn -v pockyt-add {url}",
        "rss": "spawn --userscript openfeeds",
        "set-edgelp-proxy": "set content.proxy socks://localhost:8080",
        "Tsub": "spawn --userscript Tsub",
        "vs": "open -w",
        "wt": "spawn wtitle",
    }

    for i in range(1, 21):
        command_aliases[f"b{i}"] = f"tab-select {i}"

    c.aliases = command_aliases


#####################################################################
#  Bindings                                                         #
#####################################################################
def bind(keys: str, *commands: str, mode: str = "normal") -> None:
    config.bind(keys, " ;; ".join(commands), mode=mode)


@SetupMaster.register
def setup_binds() -> None:
    c.bindings.commands = {}  # Clears all previously set user bindings.

    ########## Unbinds
    unbound_nkeys: List[str] = [
        "<Ctrl+h>",
        "=",
        "+",
        "-",
        "[[",
        "]]",
        "ad",
        "b",
        "B",
        "co",
        "d",
        "D",
        "gd",
        "gf",
        "M",
    ]
    unbound_ikeys: List[str] = ["<Ctrl+e>"]

    for unbound_keys, mode in [
        (unbound_nkeys, "normal"),
        (unbound_ikeys, "insert"),
    ]:
        for keys in unbound_keys:
            config.unbind(keys, mode=mode)

    ########## Binds

    # bind functions for different modes
    cbind = partial(bind, mode="command")
    ibind = partial(bind, mode="insert")
    pbind = partial(bind, mode="prompt")
    ptbind = partial(bind, mode="passthrough")

    # >>>>>>> COMMAND
    cbind("<Alt-j>", "spawn --userscript add_quotes 1")
    cbind("<Alt-k>", "spawn --userscript add_quotes 2")
    cbind("<Alt-l>", "spawn --userscript add_quotes 3")
    cbind("<Alt-u>", "spawn --userscript add_quotes -1")
    cbind("<Alt-i>", "spawn --userscript add_quotes -2")
    cbind("<Alt-o>", "spawn --userscript add_quotes -3")
    cbind("<Ctrl-f>", "edit-command --run")
    cbind("<Ctrl-y>", "fake-key --global <Return>v$y")

    # >>>>>>> INSERT
    ibind("<Ctrl-f>", "edit-text")
    ibind("<Ctrl-i>", "spawn -d qute-pass-add {url}")
    ibind("<Ctrl-o>", "tab-focus last")
    ibind("<Alt-i>", "spawn --userscript qute-pass")
    ibind("<Ctrl-Alt-i>", "spawn --userscript qute-pass")
    ibind("<Ctrl-Shift-i>", "spawn --userscript qute-pass")
    ibind("<Ctrl-n>", "fake-key -g <Down>")
    ibind("<Alt-p>", "spawn --userscript qute-pass --password-only")
    ibind("<Ctrl-Alt-p>", "spawn --userscript qute-pass --password-only")
    ibind("<Ctrl-p>", "fake-key -g <Up>")
    ibind("<Alt-u>", "spawn --userscript qute-pass --username-only")
    ibind("<Ctrl-Alt-u>", "spawn --userscript qute-pass --username-only")

    # >>>>>>> PROMPT
    pbind("<Ctrl-o>", "prompt-open-download rifle {}")

    # >>>>>>> PASSTHROUGH
    ptbind("<Ctrl-[>", "mode-leave")
    ptbind("<Ctrl-]>", "fake-key --global <Escape>")
    ptbind("<Ctrl-o>", "tab-focus last")
    for i in range(10):
        if i == 0:
            tab = 10
        else:
            tab = i

        ptbind(f"<Ctrl-i>{i}", f"tab-select {tab}")

    # >>>>>>> NORMAL
    # ------------------------
    # ----- Alphanumeric -----
    # ------------------------
    bind("A", "set-cmd-text -s :quickmark-load -t")
    bind("a", "set-cmd-text -s :quickmark-load")
    bind(",b", 'set-cmd-text :bookmark-add {url} "')
    bind("-b", "hint all tab-bg")
    bind("b", "quickmark-save")
    bind("B", "bookmark-add --toggle")
    bind("c", "yank selection")
    bind("C", "tab-clone")
    bind("dd", "tab-close -f")
    bind("dD", "tab-only --pinned=close")
    bind("d,", "tab-close -f -p")
    bind("d<", "tab-only --pinned=close -n")
    bind("d.", "tab-close -f -n")
    bind("d>", "tab-only --pinned=close -p")
    bind(",d", "bookmark-del")
    bind(",e", "spawn --userscript searchbar-command")
    bind("-f", "hint all tab-fg")
    bind("gc", "tab-clone")
    bind(
        "gC",
        'spawn "{}" {{url}}'.format(  # pylint: disable=consider-using-f-string
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if is_macos()
            else "google-chrome"
        ),
    )
    bind(",gc", 'spawn "init-chrome"')
    bind("gf", "spawn firefox --new-window {url}")
    bind("gh", "home")
    bind("gs", "view-source --pygments")
    bind("gi", "hint inputs")
    bind(",h", "set-cmd-text -s :help")
    bind(",H", "set-cmd-text -s :help -t")
    bind("<Alt-i>", "mode-enter insert", "spawn --userscript qute-pass")
    bind("<Ctrl-l>", "edit-url")
    bind(",m", "spawn --userscript view_in_umpv -d")
    bind(
        "-m",
        "hint all spawn -v qb_umpv {hint-url}",
        'message-info "Select video to load with umpv."',
    )
    bind(
        "-M",
        "hint all spawn -v qb_umpv --append {hint-url}",
        'message-info "Select video to append to umpv playlist."',
    )
    bind("m", "mode-enter set_mark")
    bind("<Alt-o>", "set-cmd-text -s :open -t -r")
    bind("<Ctrl-o>", "tab-focus last")
    bind("-P", "hint links spawn -v pockyt put -f '{link}' -i {hint-url}")
    bind("p", "open -- {clipboard}")
    bind(",p", 'open -- "{clipboard}"')
    bind("P", "open -t -- {clipboard}")
    bind(",P", 'open -t -- "{clipboard}"')
    bind(
        "<Alt-p>",
        "mode-enter insert",
        "spawn --userscript qute-pass --password-only",
    )
    bind("<Ctrl-p>", "tab-pin")
    bind(
        ",q",
        "set-cmd-text :",
        "run-with-count 2 command-history-prev",
        "edit-command --run",
    )
    bind(",r", 'bookmark-add {url} "READ: {title}"')
    bind("-r", "hint --rapid links tab-bg")
    bind("<Ctrl-r>", "restart")
    bind("sd", "set-cmd-text -s :session-delete")
    bind("sl", "set-cmd-text -s :session-load -c")
    bind("sL", "set-cmd-text -s :session-load")
    bind("ss", "set-cmd-text -s :session-save -o")
    bind("sS", "set-cmd-text -s :session-save")
    bind("th", "back --tab", "tab-move -")
    bind("tH", "back --tab", "tab-move -", "tab-next")
    bind(
        ",tt",
        "set tabs.position top",
        'set tabs.title.format "{audio}{index}: {title}"',
        'set tabs.title.format_pinned "[{index}]"',
    )
    bind(
        ",tl",
        "set tabs.position left",
        'set tabs.title.format " * {audio}{index}: {title}"',
        'set tabs.title.format_pinned "[{index}]: {title}"',
    )
    bind(
        ",tr",
        "set tabs.position right",
        'set tabs.title.format " * {audio}{index}: {title}"',
        'set tabs.title.format_pinned "[{index}]: {title}"',
    )
    bind(
        "-Tm",
        "hint links spawn -d -v torrent -d {hint-url} -w "
        "/media/bryan/zeus/media/Entertainment/Movies",
        'message-info "Select movie to torrent."',
    )
    bind(
        "-TM",
        "hint links spawn --userscript add-to-torrent-file movies.txt "
        '"{hint-url}"',
        'message-info "Select movie to add to torrent list."',
    )
    bind(
        "-Tt",
        "hint links spawn -d -v torrent -d {hint-url} -w "
        "/media/bryan/zeus/media/Entertainment/TV",
        'message-info "Select TV show to torrent."',
    )
    bind(
        "-TT",
        "hint links spawn --userscript add-to-torrent-file tv.txt"
        ' "{hint-url}"',
        'message-info "Select TV show to add to torrent list."',
    )
    bind("tt", "set-cmd-text -s :tab-take")
    bind("tg", "set-cmd-text -s :tab-give")
    bind(
        "<Alt-u>",
        "mode-enter insert",
        "spawn --userscript qute-pass --username-only",
    )
    bind("w-", "window-only")
    bind(
        ",Y",
        "spawn ytcast {url}",
        'message-info "Casting YouTube to chromecast..."',
    )
    bind("-y", "hint links yank")
    bind(
        "-Y",
        "hint links spawn -v ytcast {hint-url}",
        'message-info "Casting YouTube to chromecast..."',
    )
    bind("Y", "fake-key --global v$y")
    bind("<Ctrl-y>", "fake-key --global v$y")
    # ----------------------------
    # ----- Non-Alphanumeric -----
    # ----------------------------
    bind("==", "zoom-in")
    bind("=0", "zoom 100%")
    bind("--", "zoom-out")
    bind("-0", "zoom 100%")
    bind(";", "set-cmd-text :")
    bind("\\", "set-cmd-text :open /")
    bind("|", "set-cmd-text :open -t /")
    bind("(", "navigate prev")
    bind(")", "navigate next")
    bind("{", "navigate prev -t")
    bind("}", "navigate next -t")
    bind("[", "run-with-count 10 scroll left")
    bind("]", "run-with-count 10 scroll right")
    bind(">", "tab-move +")
    bind("<", "tab-move -")
    # -------------------------
    # ----- Miscellaneous -----
    # -------------------------
    bind("<Escape>", "search", "clear-messages")

    # setup bindings for N- to go to tab N...
    for i in range(1, 31):
        bind(f"{i}-", f"tab-select {i}")

    # setup bindings for <Ctrl-i>N to go to tab N...
    for i in range(10):
        if i == 0:
            tab = 10
        else:
            tab = i

        bind(f"<Ctrl-i>{i}", f"tab-select {tab}")

    # setup bindings for zoom-in and zoom-out...
    for i in range(1, 10):
        bind(f"={i}", f"run-with-count {i} zoom-in")
        bind(f"-{i}", f"run-with-count {i} zoom-out")


#####################################################################
#  Load yaml Config                                                 #
#####################################################################
def dict_attrs(
    obj: Union[str, Dict], path: str = ""
) -> Iterator[Tuple[str, str]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from dict_attrs(v, f"{path}.{k}" if path else k)
    else:
        yield path, obj


@SetupMaster.register
def setup_config_from_yaml() -> None:
    config_yml = Path(__file__).parent.absolute() / "config.yml"
    with config_yml.open() as f:
        conf = yaml.load(f, Loader=yaml.FullLoader)

    for k, v in dict_attrs(conf):
        config.set(k, v)


# Call all setup functions.
SetupMaster.run_all()
