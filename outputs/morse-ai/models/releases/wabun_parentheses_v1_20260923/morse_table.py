"""和文モールス符号。無線局運用規則・別表第一号（数字は略体でない）。

濁音は独立クラスにせず、例: ガ → カ + ゛。国際モールスは含めない。
"""
import unicodedata

KANA = {
    'イ': '.-', 'ロ': '.-.-', 'ハ': '-...', 'ニ': '-.-.', 'ホ': '-..',
    'ヘ': '.', 'ト': '..-..', 'チ': '..-.', 'リ': '--.', 'ヌ': '....',
    'ル': '-.--.', 'ヲ': '.---', 'ワ': '-.-', 'カ': '.-..', 'ヨ': '--',
    'タ': '-.', 'レ': '---', 'ソ': '---.', 'ツ': '.--.', 'ネ': '--.-',
    'ナ': '.-.', 'ラ': '...', 'ム': '-', 'ウ': '..-', 'ヰ': '.-..-',
    'ノ': '..--', 'オ': '.-...', 'ク': '...-', 'ヤ': '.--', 'マ': '-..-',
    'ケ': '-.--', 'フ': '--..', 'コ': '----', 'エ': '-.---', 'テ': '.-.--',
    'ア': '--.--', 'サ': '-.-.-', 'キ': '-.-..', 'ユ': '-..--', 'メ': '-...-',
    'ミ': '..-.-', 'シ': '--.-.', 'ヱ': '.--..', 'ヒ': '--..-', 'モ': '-..-.',
    'セ': '.---.', 'ス': '---.-', 'ン': '.-.-.',
}
MARKS = {'゛': '..', '゜': '..--.'}
DIGITS = {
    '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-',
    '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.',
}
SYMBOLS = {'ー': '.--.-', '、': '.-.-.-', '」': '.-.-..', '（': '-.--.-', '）': '.-..-.'}
MORSE_TABLE = KANA | MARKS | DIGITS | SYMBOLS
REVERSE_TABLE = {code: label for label, code in MORSE_TABLE.items()}


def normalize_text(text: str) -> str:
    """全角カタカナへ統一し、濁点を分離。小書き文字・空白は未対応。"""
    # NFKC changes spacing dakuten into space + combining mark: preserve them first.
    text = text.replace('゛', '\u3099').replace('゜', '\u309a')
    text = unicodedata.normalize('NFD', unicodedata.normalize('NFKC', text))
    result = []
    for char in text:
        if '\u3041' <= char <= '\u3096':
            char = chr(ord(char) + 0x60)
        char = {'\u3099': '゛', '\u309a': '゜', '(': '（', ')': '）'}.get(char, char)
        if char not in MORSE_TABLE:
            raise ValueError(f'未対応文字: {char!r}。全角の通常サイズのカナ・数字・対応記号を指定してください。')
        result.append(char)
    if not result:
        raise ValueError('文字が空です。')
    return ''.join(result)


def get_morse_code(label: str) -> str:
    normalized = normalize_text(label)
    if len(normalized) != 1:
        raise ValueError('1ファイルには1符号のみ指定できます。濁音はカナと濁点に分けてください。')
    return MORSE_TABLE[normalized]
