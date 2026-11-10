import unittest
from evaluate_four import select_extended,reference_allow_latin,decode_drop_controls

def rows(patterns):
    return [{'pattern':p,'prediction':'ハ','rule_prediction':'イ'} for p in patterns]

class FourTests(unittest.TestCase):
    def test_bt_ar_only_with_exact_header(self):
        data=rows(['....','.-.','....','.-.','-...-','.-','.-.-.'])
        body,info=select_extended(data)
        self.assertEqual(body,data[5:6]);self.assertEqual(info['method'],'HR_HR_BT_prefix_and_terminal_AR')
        with self.assertRaises(ValueError):select_extended(rows(['.-','-...-','.-','.-.-.']))
        data[-1]['pattern']='.'
        with self.assertRaises(ValueError):select_extended(data)
    def test_legacy_frame_preserved(self):
        data=rows(['-..---','.-','...-.'])
        body,info=select_extended(data)
        self.assertEqual(len(body),1);self.assertEqual(info['method'],'existing_HORE_RATA')
    def test_latin_reference_no_invented_brackets(self):
        self.assertEqual(reference_allow_latin('ガ60cm、IPCC。'),'カ゛60CMIPCC')
    def test_control_not_text_and_no_rule_correction(self):
        data=[{'pattern':'-.--.-','prediction':'（','rule_prediction':'（'},
              {'pattern':'.-','prediction':'ハ','rule_prediction':'イ'},
              {'pattern':'.-..-.','prediction':'）','rule_prediction':'）'}]
        cnn,rule=decode_drop_controls(data)
        self.assertEqual(cnn,'B');self.assertEqual(rule,'A')
        with self.assertRaises(ValueError):decode_drop_controls(data[:-1])

if __name__=='__main__':unittest.main()
