# SPDX-License-Identifier: MPL-2.0
from socket import _GLOBAL_DEFAULT_TIMEOUT
import urllib.request


__FILE_LOADER_CACHE = {}
__URL_CONTENT_CACHE = {}


def read_file_and_cache(filepath: str) -> str:
    """Read and cache string contents of files for quick access and reducing IO operations.

    May need "forgetting" mechanism if too many large files are stored. Should be fine
    for loading JSON metamodels and SHACL constraints in Turtle format.
    """
    if filepath in __FILE_LOADER_CACHE:
        return __FILE_LOADER_CACHE[filepath]

    with open(filepath) as infile:
        file_content = infile.read()

    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8")

    __FILE_LOADER_CACHE[filepath] = file_content
    return file_content


def read_url_and_cache(url: str, timeout=_GLOBAL_DEFAULT_TIMEOUT) -> str:
    """Read and cache text responses from URL

    `timeout` specifies duration in seconds to wait for response. Only works for HTTP, HTTPS & FTP.
    By default `socket._GLOBAL_DEFAULT_TIMEOUT` will be used, which usually means no timeout.
    """
    if url in __URL_CONTENT_CACHE:
        return __URL_CONTENT_CACHE[url]

    with urllib.request.urlopen(url, timeout=timeout) as f:
        url_content = f.read()

    if isinstance(url_content, bytes):
        url_content = url_content.decode("utf-8")

    __URL_CONTENT_CACHE[url] = url_content
    return url_content
