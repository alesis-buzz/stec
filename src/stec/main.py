"""Small playground to try the parser, evaluator, and singleton by hand."""

from pathlib import Path
import tempfile

from stec import Stec
from stec.evaluator import evaluate
from stec.parser import parse

SOURCE = """
# runtime switches
var dev = true  # flip for prod

export env STEC_MODE = $dev ? "development" : "production"
import env string STEC_HOST = "127.0.0.1"

expose int port = 8080
expose string secret = "secreteetoiertoiertoeritoeritoeriotio"
expose string url = "http://${STEC_HOST}:${port}"
expose string api = "${url}/api?mode=${STEC_MODE}"
"""


def main() -> None:
    for declaration in parse(SOURCE):
        print(declaration)

    print(evaluate(parse(SOURCE)))

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "app.stec"
        path.write_text(SOURCE, encoding="utf-8")
        Stec.load(path)
        print(Stec.as_dict())
        print(Stec.api, Stec["port"], Stec.get("secret"))


if __name__ == "__main__":
    main()
