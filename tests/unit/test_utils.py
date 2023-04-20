# Copyright (c) 2020-2022 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import tempfile
from unittest.mock import MagicMock, Mock

import lifemonitor.exceptions as lm_exceptions
import lifemonitor.utils as utils
import pytest


def test_download_url_404():
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(lm_exceptions.DownloadException) as excinfo:
            _ = utils.download_url('http://httpbin.org/status/404', os.path.join(d, 'get_404'))
        assert excinfo.value.status == 404


class SerializableMock(MagicMock):
    def __reduce__(self):
        return (Mock, ())


def test_datetime_to_isoformat():
    """Test the datetime_to_isoformat function."""
    from datetime import datetime

    # test with a datetime with microseconds
    dt = datetime(2020, 1, 1, 0, 0, 0, 123456)
    assert utils.datetime_to_isoformat(dt) == "2020-01-01T00:00:00.123456Z"

    # test with a datetime without microseconds
    dt = datetime(2020, 1, 1, 0, 0, 0)
    assert utils.datetime_to_isoformat(dt) == "2020-01-01T00:00:00Z"


def test_isoformat_to_datetime():
    """Test the isoformat_to_datetime function."""
    from datetime import datetime

    # test with a datetime with microseconds
    dt = datetime(2020, 1, 1, 0, 0, 0, 123456)
    iso = "2020-01-01T00:00:00.123456Z"
    assert utils.isoformat_to_datetime(iso) == dt

    # test with a datetime without microseconds
    dt = datetime(2020, 1, 1, 0, 0, 0)
    iso = "2020-01-01T00:00:00Z"
    assert utils.isoformat_to_datetime(iso) == dt

    # test with a datetime without microseconds and without Z
    dt = datetime(2020, 1, 1, 0, 0, 0)
    iso = "2020-01-01T00:00:00"
    assert utils.isoformat_to_datetime(iso) == dt

    # test with a datetime without microseconds and without Z and without seconds
    dt = datetime(2020, 1, 1, 0, 0)
    iso = "2020-01-01T00:00"
    assert utils.isoformat_to_datetime(iso) == dt

    # test with a datetime without microseconds and without Z and without seconds and without minutes
    dt = datetime(2020, 1, 1, 0)
    iso = "2020-01-01T00"
    assert utils.isoformat_to_datetime(iso) == dt

    # test with a datetime without microseconds and without Z and without seconds and without minutes and without hours
    dt = datetime(2020, 1, 1)
    iso = "2020-01-01"
    assert utils.isoformat_to_datetime(iso) == dt

    # test with a datetime without microseconds and without Z and without seconds and without minutes and without hours and without day
    dt = datetime(2020, 1, 1)
    iso = "2020-01"
    assert utils.isoformat_to_datetime(iso) == dt

    # test with a datetime without microseconds and without Z and without seconds and without minutes and without hours and without day and without month
    dt = datetime(2020, 1, 1)
    iso = "2020"


def test_parse_date_interval():
    """Test the parse_date_interval function."""
    from datetime import datetime

    # test with a datetime with microseconds and operator <=
    dt = datetime(2020, 1, 1, 0, 0, 0, 123456)
    iso = "2020-01-01T00:00:00.123456Z"
    operator, start_date, end_date = parse_date_interval(f"<={iso}")
    assert operator == "<="
    assert start_date is None
    assert end_date == dt

    # test with a datetime with microseconds and operator >=
    dt = datetime(2020, 1, 1, 0, 0, 0, 123456)
    iso = "2020-01-01T00:00:00.123456Z"
    operator, start_date, end_date = parse_date_interval(f">={iso}")
    assert operator == ">="
    assert start_date == dt
    assert end_date == datetime.now()

    # test with a datetime with microseconds and operator <
    dt = datetime(2020, 1, 1, 0, 0, 0, 123456)
    iso = "2020-01-01T00:00:00.123456Z"
    operator, start_date, end_date = parse_date_interval(f"<{iso}")
    assert operator == "<"
    assert start_date is None
    assert end_date == dt

    # test with a datetime with microseconds and operator >
    dt = datetime(2020, 1, 1, 0, 0, 0, 123456)
    iso = "2020-01-01T00:00:00.123456Z"
    operator, start_date, end_date = parse_date_interval(f">{iso}")
    assert operator == ">"
    assert start_date == dt
    assert end_date == datetime.now()

    # test with a datetime with microseconds and operator ..
    dt = datetime(2020, 1, 1, 0, 0, 0, 123456)
    iso = "2020-01-01T00:00:00.123456Z"
    operator, start_date, end_date = parse_date_interval(f"{iso}..{iso}")
    assert operator == ".."
    assert start_date == dt
    assert end_date ==
