# encoding: utf-8

import pytest

if __name__ == "__main__":
    pytest.main([ 
        "-v",
        "--asyncio-mode",
        "auto",
        "--alluredir",
        "aiotest/test/reports",
        "aiotest/test",
        "--clean-alluredir",
        "--disable-warnings",
        "--color",
        "yes"
    ])
