from __future__ import annotations

import sys
from typing import Callable

import translate_ptbr as base

MODEL = "Helsinki-NLP/opus-mt-en-ROMANCE"


def make_translator(_: str) -> Callable[[list[str]], list[str]]:
    from transformers import MarianMTModel, MarianTokenizer

    tokenizer = MarianTokenizer.from_pretrained(MODEL)
    model = MarianMTModel.from_pretrained(MODEL)
    model.eval()

    def run(texts: list[str]) -> list[str]:
        prefixed = [f">>pt<< {text}" for text in texts]
        encoded = tokenizer(
            prefixed,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=384,
        )
        generated = model.generate(
            **encoded,
            max_new_tokens=384,
            num_beams=1,
        )
        return tokenizer.batch_decode(generated, skip_special_tokens=True)

    return run


base.make_translator = make_translator

if "--model" not in sys.argv:
    sys.argv.extend(["--model", MODEL])

if __name__ == "__main__":
    base.main()
