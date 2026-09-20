"""Small playground to try the parser, evaluator, and singleton by hand."""

from pathlib import Path
import tempfile

from konfig import Konfig
from konfig.evaluator import evaluate
from konfig.parser import parse

SOURCE = """
# runtime switches
var dev = true  # flip for prod

expose int port = 8080
expose string secret = "secreteetoiertoiertoeritoeritoeriotio"
expose string url = $dev ? "127.0.0.1" : "0.0.0.0"
expose string api = "${url}:${port}/api"
"""


def main() -> None:
    for declaration in parse(SOURCE):
        print(declaration)

    print(evaluate(parse(SOURCE)))

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "app.konfig"
        path.write_text(SOURCE, encoding="utf-8")
        Konfig.load(path)
        print(Konfig.as_dict())
        print(Konfig.api, Konfig["port"], Konfig.get("secret"))


if __name__ == "__main__":
    main()
