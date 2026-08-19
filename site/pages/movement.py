"""Line Movement — see requirements page section.

A3 builds the shell; A4 builds the body. The page appears in nav today and states
honestly what it is waiting on rather than being hidden.
"""
from lib import shell


def render() -> None:
    shell.render_page("movement")
