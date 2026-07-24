# SPDX-License-Identifier: MPL-2.0
# Inspired by https://github.com/comp-rob2b/kindyngen/ (kindyngen.utility.resolver)
import pathlib
import urllib.request
import urllib.response
from email.message import EmailMessage
from os.path import join
from socket import _GLOBAL_DEFAULT_TIMEOUT

import platformdirs

from rdf_utils import __version__
from rdf_utils.namespace import URL_COMP_ROB2B, URL_SECORO

PKG_CACHE_ROOT = join(platformdirs.user_cache_dir(), "rdf-utils")


class IriToFileResolver(urllib.request.OpenerDirector):
    """
    An [`OpenerDirector`](urllib.request.OpenerDirector) that remaps specific URLs to local files.

    Parameters:
        url_map: Mapping from a prefix of a URL to a local location.
                 For example, `{ "http://example.org/": "foo/bar/" }` would remap any
                 urllib open request for any resource under `http://example.org/`
                 to a local directory `foo/bar/`.
        download: If true and the mapped local file does not exist, will attempt to download
                  to the mapped location.
        quiet: If `False` and `download` is `True` will print where the file will be
               downloaded to.
    """

    def __init__(self, url_map: dict, download: bool = True, quiet: bool = False):
        super().__init__()
        self.default_opener = urllib.request.build_opener()
        self.url_map = url_map
        self._download = download
        self._quiet = quiet
        self._empty_header = EmailMessage()  # header expected by addinfourl

    def open(self, fullurl, data=None, timeout=_GLOBAL_DEFAULT_TIMEOUT):
        if isinstance(fullurl, str):
            url_req = urllib.request.Request(fullurl)
            url_req.add_header("User-Agent", f"rdf-utils/{__version__}")
        elif isinstance(fullurl, urllib.request.Request):
            url_req = fullurl
        else:
            raise TypeError(
                f"expected URL of type 'str' or 'urllib.request.Request', got type '{type(fullurl)}'"
            )

        url = pathlib.Path(url_req.full_url)

        # If the requested URL starts with any key in the url_map, fetch the file from a
        # local file that is derived from the URL and the value in the map
        for prefix, directory in self.url_map.items():
            if not url.is_relative_to(prefix):
                continue

            # Wrap the directory in a pathlib.Path to get access to convenience functions
            path = pathlib.Path(directory).joinpath(url.relative_to(prefix))

            # Download file if not exist in system and `download` is specified.
            # If `download` not specified, break from loop to open URL using default opener.
            if not path.exists():
                if not self._download:
                    break

                parent_path = path.parent
                if not parent_path.exists():
                    parent_path.mkdir(parents=True)
                assert parent_path.is_dir(), f"not a directory: {parent_path}"

                if not self._quiet:
                    print(f"Dowloading '{url}' & caching to '{parent_path}'")

                with (
                    self.default_opener.open(url_req, data=data, timeout=timeout) as url_data,
                    path.open("wb") as cache_file,
                ):
                    cache_file.write(url_data.read())
                assert path.exists(), f"File '{path}' not cached for URL '{url_req.full_url}'"

            # Open the file and wrap it in an urllib response
            fp = path.open("rb")
            resp = urllib.response.addinfourl(
                fp, headers=self._empty_header, url=url_req.full_url, code=200
            )
            return resp

        # If we did not find any match above just continue with the default opener
        # which has the behaviour as initially expected by rdflib.
        return self.default_opener.open(url_req, data=data, timeout=timeout)


def install_resolver(
    resolver: urllib.request.OpenerDirector | None = None,
    url_map: dict | None = None,
    download: bool = True,
    quiet: bool = False,
) -> None:
    """Implements default behaviours for resolver installation

    Parameters:
        resolver: Resolver to install. If none specified, the default behaviour
                  (using [`IriToFileResolver`](rdf_utils.resolver.IriToFileResolver)) is to
                  download the requested files to the user cache directory using
                  [`platformdirs`](https://github.com/tox-dev/platformdirs).
                  For Linux this should be `$HOME/.cache/rdf-utils/`.
        url_map: URL to local path mapping to pass to
                 [`IriToFileResolver`](rdf_utils.resolver.IriToFileResolver)
        download: Download file if true
        quiet: Option for more verbose output, created for printing caching location in
               [`IriToFileResolver`](rdf_utils.resolver.IriToFileResolver)

    Note:
        Only a single opener can be globally installed in urllib.
        Only the latest installed resolver will be active.
    """
    if resolver is None:
        if url_map is None:
            url_map = {
                URL_SECORO: join(PKG_CACHE_ROOT, "secoro"),
                URL_COMP_ROB2B: join(PKG_CACHE_ROOT, "comp-rob2b"),
            }
        resolver = IriToFileResolver(url_map=url_map, download=download, quiet=quiet)

    urllib.request.install_opener(resolver)
