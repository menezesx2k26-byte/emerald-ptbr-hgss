from __future__ import annotations

import argparse
from pathlib import Path


MARKER = "/* MAP_QA_HEADLESS_VIDEO_BUFFER */"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected exactly one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def patch_source(text: str) -> str:
    if MARKER in text:
        raise ValueError("mGBA headless source is already patched with a video buffer")
    text = replace_once(
        text,
        "static struct mCore* core;",
        f'''{MARKER}
static struct mCore* core;
static void* sHeadlessVideoBuffer = NULL;''',
        "headless core declaration",
    )
    text = replace_once(
        text,
        "\tcore->init(core);",
        '''\tsHeadlessVideoBuffer = calloc(256 * 256, 4);
\tif (!sHeadlessVideoBuffer)
\t\tgoto argsExit;
\tcore->init(core);
\tcore->setVideoBuffer(core, sHeadlessVideoBuffer, 256);''',
        "headless core initialization",
    )
    text = replace_once(
        text,
        "argsExit:\n\tfor (i = 0;",
        '''argsExit:
\tfree(sHeadlessVideoBuffer);
\tsHeadlessVideoBuffer = NULL;
\tfor (i = 0;''',
        "headless cleanup",
    )
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    source.write_text(patch_source(source.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"Installed mGBA headless video buffer in {source}")


if __name__ == "__main__":
    main()
