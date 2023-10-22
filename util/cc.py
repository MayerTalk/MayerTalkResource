__all__ = ['s2t']

import opencc


class CC:
    def __init__(self, config: str):
        self.converter: opencc.OpenCC = opencc.OpenCC(config)

    def __call__(self, text: str) -> str:
        return self.converter.convert(text)


s2t = CC('s2t')
