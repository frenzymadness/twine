# Copyright 2018 Dustin Ingram
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

import pretend
import pytest

from twine import commands
from twine import package as package_file
from twine.commands import check


class TestWarningStream:
    def setup(self):
        self.stream = check._WarningStream()
        self.stream.output = pretend.stub(
            write=pretend.call_recorder(lambda a: None),
            getvalue=lambda: "result",
        )

    def test_write_match(self):
        self.stream.write("<string>:2: (WARNING/2) Title underline too short.")

        assert self.stream.output.write.calls == [
            pretend.call("line 2: Warning: Title underline too short.\n")
        ]

    def test_write_nomatch(self):
        self.stream.write("this does not match")

        assert self.stream.output.write.calls == [pretend.call("this does not match")]

    def test_str_representation(self):
        assert str(self.stream) == "result"


def test_check_no_distributions(monkeypatch, caplog):
    monkeypatch.setattr(commands, "_find_dists", lambda a: [])

    assert not check.check(["dist/*"])
    assert caplog.record_tuples == [
        (
            "twine.commands.check",
            logging.ERROR,
            "No files to check.",
        ),
    ]


def test_check_passing_distribution(monkeypatch, capsys):
    renderer = pretend.stub(render=pretend.call_recorder(lambda *a, **kw: "valid"))
    package = pretend.stub(
        metadata_dictionary=lambda: {
            "description": "blah",
            "description_content_type": "text/markdown",
        }
    )
    warning_stream = ""

    monkeypatch.setattr(check, "_RENDERERS", {None: renderer})
    monkeypatch.setattr(commands, "_find_dists", lambda a: ["dist/dist.tar.gz"])
    monkeypatch.setattr(
        package_file,
        "PackageFile",
        pretend.stub(from_filename=lambda *a, **kw: package),
    )
    monkeypatch.setattr(check, "_WarningStream", lambda: warning_stream)

    assert not check.check(["dist/*"])
    assert capsys.readouterr().out == "Checking dist/dist.tar.gz: PASSED\n"
    assert renderer.render.calls == [pretend.call("blah", stream=warning_stream)]


@pytest.mark.parametrize("content_type", ["text/plain", "text/markdown"])
def test_check_passing_distribution_with_none_renderer(
    content_type,
    monkeypatch,
    capsys,
):
    """Pass when rendering a content type can't fail."""
    package = pretend.stub(
        metadata_dictionary=lambda: {
            "description": "blah",
            "description_content_type": content_type,
        }
    )

    monkeypatch.setattr(commands, "_find_dists", lambda a: ["dist/dist.tar.gz"])
    monkeypatch.setattr(
        package_file,
        "PackageFile",
        pretend.stub(from_filename=lambda *a, **kw: package),
    )

    assert not check.check(["dist/*"])
    assert capsys.readouterr().out == "Checking dist/dist.tar.gz: PASSED\n"


def test_check_no_description(monkeypatch, capsys, caplog):
    package = pretend.stub(
        metadata_dictionary=lambda: {
            "description": None,
            "description_content_type": None,
        }
    )

    monkeypatch.setattr(commands, "_find_dists", lambda a: ["dist/dist.tar.gz"])
    monkeypatch.setattr(
        package_file,
        "PackageFile",
        pretend.stub(from_filename=lambda *a, **kw: package),
    )

    assert not check.check(["dist/*"])

    assert capsys.readouterr().out == (
        "Checking dist/dist.tar.gz: PASSED with warnings\n"
    )
    assert caplog.record_tuples == [
        (
            "twine.commands.check",
            logging.WARNING,
            "`long_description_content_type` missing. defaulting to `text/x-rst`.",
        ),
        (
            "twine.commands.check",
            logging.WARNING,
            "`long_description` missing.",
        ),
    ]


def test_strict_fails_on_warnings(monkeypatch, capsys, caplog):
    package = pretend.stub(
        metadata_dictionary=lambda: {
            "description": None,
            "description_content_type": None,
        }
    )

    monkeypatch.setattr(commands, "_find_dists", lambda a: ["dist/dist.tar.gz"])
    monkeypatch.setattr(
        package_file,
        "PackageFile",
        pretend.stub(from_filename=lambda *a, **kw: package),
    )

    assert check.check(["dist/*"], strict=True)

    assert capsys.readouterr().out == (
        "Checking dist/dist.tar.gz: FAILED due to warnings\n"
    )
    assert caplog.record_tuples == [
        (
            "twine.commands.check",
            logging.WARNING,
            "`long_description_content_type` missing. defaulting to `text/x-rst`.",
        ),
        (
            "twine.commands.check",
            logging.WARNING,
            "`long_description` missing.",
        ),
    ]


def test_check_failing_distribution(monkeypatch, capsys, caplog):
    renderer = pretend.stub(render=pretend.call_recorder(lambda *a, **kw: None))
    package = pretend.stub(
        metadata_dictionary=lambda: {
            "description": "blah",
            "description_content_type": "text/markdown",
        }
    )
    warning_stream = "Syntax error"

    monkeypatch.setattr(check, "_RENDERERS", {None: renderer})
    monkeypatch.setattr(commands, "_find_dists", lambda a: ["dist/dist.tar.gz"])
    monkeypatch.setattr(
        package_file,
        "PackageFile",
        pretend.stub(from_filename=lambda *a, **kw: package),
    )
    monkeypatch.setattr(check, "_WarningStream", lambda: warning_stream)

    assert check.check(["dist/*"])

    assert capsys.readouterr().out == "Checking dist/dist.tar.gz: FAILED\n"
    assert caplog.record_tuples == [
        (
            "twine.commands.check",
            logging.ERROR,
            "`long_description` has syntax errors in markup and would not be rendered "
            "on PyPI.\nSyntax error",
        ),
    ]
    assert renderer.render.calls == [pretend.call("blah", stream=warning_stream)]


def test_main(monkeypatch):
    check_result = pretend.stub()
    check_stub = pretend.call_recorder(lambda a, strict=False: check_result)
    monkeypatch.setattr(check, "check", check_stub)

    assert check.main(["dist/*"]) == check_result
    assert check_stub.calls == [pretend.call(["dist/*"], strict=False)]


# TODO: Test print() color output

# TODO: Test log formatting
