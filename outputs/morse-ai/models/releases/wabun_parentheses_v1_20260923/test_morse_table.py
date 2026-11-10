import unittest
from morse_table import KANA, MORSE_TABLE, REVERSE_TABLE, get_morse_code, normalize_text


class MorseTableTests(unittest.TestCase):
    def test_inventory(self):
        expected = set('アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヰヱヲン')
        self.assertEqual(set(KANA), expected)
        self.assertEqual(len(MORSE_TABLE), 65)
        self.assertEqual(len(REVERSE_TABLE), len(MORSE_TABLE))
        for label, code in MORSE_TABLE.items():
            with self.subTest(label=label):
                self.assertTrue(code)
                self.assertLessEqual(set(code), set('.-'))
                self.assertEqual(REVERSE_TABLE[code], label)

    def test_reference_codes(self):
        # Particularly easy to confuse with international Morse or old transcriptions.
        reference = {'イ': '.-', 'ヘ': '.', 'ム': '-', 'モ': '-..-.', 'ユ': '-..--',
                     'ヰ': '.-..-', 'ヱ': '.--..', '゛': '..', '゜': '..--.',
                     'ー': '.--.-', '、': '.-.-.-', '」': '.-.-..',
                     '（': '-.--.-', '）': '.-..-.', '0': '-----', '9': '----.'}
        for label, code in reference.items():
            with self.subTest(label=label):
                self.assertEqual(get_morse_code(label), code)

    def test_normalization(self):
        self.assertEqual(normalize_text('がぱヴｶﾞ１２(い)'), 'カ゛ハ゜ウ゛カ゛12（イ）')
        self.assertEqual(normalize_text('゛゜'), '゛゜')
        self.assertEqual(get_morse_code('い'), '.-')

    def test_reject_unknown_or_multiple(self):
        for text in ('', 'A', '漢', ' ', 'ッ', '。', 'ガ', 'イロ'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                get_morse_code(text)


if __name__ == '__main__':
    unittest.main()
