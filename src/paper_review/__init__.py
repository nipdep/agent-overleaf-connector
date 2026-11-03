"""paper-review: comments, agent edits, redlines and change logs for LaTeX papers."""

from importlib import metadata

try:  # pyproject.toml is the single source of the version
    __version__ = metadata.version("paper-review")
except metadata.PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0+unknown"
