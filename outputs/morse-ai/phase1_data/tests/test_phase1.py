import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import copy,io,json,tempfile,unittest
from unittest.mock import patch
import numpy as np
import soundfile as sf
from src.common import ROOT,load_config,write_csv,write_json,read_csv,sha256,digest
from src.morse_table import TABLE,morse_code
from src.legacy import legacy_tables
from src.signal_generator import generate_signal
from src.noise_generator import add_noise
from src.augmentation import synthesize,sample_seed,synthesis_config
from src.dataset_audit import scan_sources,leakage,audit,inspect_record
from src.test_protection import freeze_or_verify,verify_lock
from src.metadata_manager import prepare_existing
from src.generation import generate,safe_output
from src.dataset_manager import WaveformDataset


def fixture(root):
    cfg=load_config();cfg['labels']=['A'];cfg['samples_per_class']=2;cfg['validation_samples_per_class']=2
    cfg['existing_sources']=[{'id':'fixture','path':'data/existing/fixture','label_system':'international','active_splits':['train','validation','test']}]
    records=[];base=root/'data/existing/fixture'
    for i,split in enumerate(('train','validation','test')):
        path=base/split/'A.wav';path.parent.mkdir(parents=True,exist_ok=True)
        x,_=generate_signal('A',frequency=600+i*70,jitter=(0,0));sf.write(path,x,16000,subtype='PCM_16')
        records.append({'filepath':path.relative_to(base).as_posix(),'split':split,'label':'A','morse_code':'.-',
                        'sample_id':'A_'+split,'wav_sha256':sha256(path),'frequency_hz':600+i*70})
    write_csv(base/'metadata.csv',records)
    rows,summary=audit(cfg,root);freeze_or_verify(rows,cfg,root);prepare_existing(rows,cfg,root)
    return cfg


class SignalTests(unittest.TestCase):
    def test_table_A_and_all_36_match_existing(self):
        self.assertEqual(morse_code('A'),'.-');self.assertEqual(len(TABLE),36)
        self.assertEqual(TABLE,legacy_tables()[1])
    def test_itu_ratios_and_no_extra_character_or_word_gap(self):
        x,parts=generate_signal('A A',jitter=(0,0),padding_seconds=0)
        self.assertEqual([p['end_sample']-p['start_sample'] for p in parts],[1600,1600,4800,11200,1600,1600,4800])
        _,p=generate_signal('AA',jitter=(0,0),padding_seconds=0)
        self.assertEqual([v['units'] for v in p if v['kind']=='character_gap'],[3])
    def test_wav_sample_rate_and_pcm(self):
        x,_=generate_signal('Z',sample_rate=22050)
        f=io.BytesIO();sf.write(f,x,22050,subtype='PCM_16',format='WAV');f.seek(0)
        info=sf.info(f);self.assertEqual(info.samplerate,22050);self.assertEqual(info.channels,1);self.assertEqual(info.subtype,'PCM_16')
    def test_reproducibility_and_split_independent_seeds(self):
        cfg=load_config();seed=sample_seed(cfg,'train','A',0)
        a,_,m=synthesize('A',cfg,seed);b,_,n=synthesize('A',cfg,seed)
        np.testing.assert_array_equal(a,b);self.assertEqual(m,n)
        self.assertNotEqual(seed,sample_seed(cfg,'validation','A',0))
    def test_jitter_30_percent_and_config_ranges(self):
        cfg=load_config();cfg['timing_jitter']={'min':-.3,'max':.3}
        for seed in range(10):
            _,_,r=synthesize('B',cfg,seed)
            self.assertTrue(400<=r['frequency']<=1200);self.assertTrue(.06<=r['dot_duration']<=.18)
            self.assertTrue(.2<=r['amplitude']<=1)
            self.assertTrue(all(.7<=p['jitter_factor']<=1.3 for p in r['timing_samples']))
    def test_noise_snr_including_pcm_and_anticlip(self):
        x,_=generate_signal('A',jitter=(0,0))
        for kind in ('gaussian','white'):
            for snr in (20,10,5,0,-5):
                mixed,clean,meta=add_noise(x,kind,snr,np.random.default_rng(42))
                self.assertLessEqual(np.max(np.abs(mixed)),.98000001)
                buf=io.BytesIO();sf.write(buf,mixed,16000,format='WAV',subtype='PCM_16');buf.seek(0);saved,_=sf.read(buf)
                measured=10*np.log10(np.mean(clean**2)/np.mean((saved-clean)**2))
                self.assertLess(abs(measured-snr),.01)
        with self.assertRaises(ValueError):add_noise(x,'white',None,np.random.default_rng(0))
    def test_invalid_text_and_parameters(self):
        for text in ('','a','A  B',' A','漢','A\nB'):
            with self.assertRaises(ValueError):generate_signal(text)
        with self.assertRaises(ValueError):generate_signal('A',frequency=8000)
    def test_invalid_config_ranges(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=load_config();cfg['frequency']['max']=9000;p=Path(d)/'bad.yaml';write_json(p,cfg)
            with self.assertRaises(ValueError):load_config(p)


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.cfg=fixture(self.root)
    def tearDown(self): self.tmp.cleanup()
    def test_test_train_leakage_is_error(self):
        rows=scan_sources(self.cfg,self.root)
        train=next(r for r in rows if r['split']=='train');test=next(r for r in rows if r['split']=='test')
        train['sha256']=test['sha256'];train['pcm_sha256']=test['pcm_sha256']
        self.assertTrue(any(f['severity']=='ERROR' for f in leakage(rows)))
        with self.assertRaises(ValueError):prepare_existing(rows,self.cfg,self.root)
    def test_same_filename_different_content_is_warning(self):
        findings=leakage(scan_sources(self.cfg,self.root))
        self.assertTrue(any(f['kind']=='filename' and f['severity']=='WARNING' for f in findings))
        self.assertFalse(any(f['severity']=='ERROR' for f in findings))
    def test_missing_unreadable_and_silent_audit(self):
        p=self.root/'bad.wav';p.write_bytes(b'bad')
        self.assertIn('unreadable',inspect_record(p,{},16000)['issues'])
        self.assertIn('missing',inspect_record(self.root/'absent.wav',{},16000)['issues'])
        sf.write(p,np.zeros(160),16000,subtype='PCM_16')
        self.assertIn('silent',inspect_record(p,{},16000)['issues'])
    def test_manifest_detects_change_addition_and_deletion(self):
        test=self.root/'data/existing/fixture/test/A.wav';saved=test.read_bytes()
        test.write_bytes(saved+b'changed')
        with self.assertRaises(ValueError):verify_lock(self.root)
        test.write_bytes(saved)
        extra=test.with_name('extra.wav');extra.write_bytes(saved)
        with self.assertRaises(ValueError):verify_lock(self.root)
        extra.unlink();test.unlink()
        with self.assertRaises(ValueError):verify_lock(self.root)
    def test_lock_and_index_tampering_detected(self):
        p=self.root/'reports/test_manifest.csv';p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaises(ValueError):verify_lock(self.root,read_audio=False)
        p=self.root/'metadata/test.csv';p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaises(ValueError):WaveformDataset('test',self.root,purpose='evaluation')
    def test_dry_run_has_no_file_changes(self):
        before={str(p.relative_to(self.root)):sha256(p) for p in self.root.rglob('*') if p.is_file()}
        generate(self.cfg,self.root,dry_run=True)
        after={str(p.relative_to(self.root)):sha256(p) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
    def test_generate_only_deficits_and_never_modify_test(self):
        protected=verify_lock(self.root);before={r['path']:sha256(r['path']) for r in protected}
        generate(self.cfg,self.root)
        self.assertEqual(before,{p:sha256(p) for p in before})
        verify_lock(self.root)
        self.assertFalse((self.root/'data/generated/test').exists())
        self.assertEqual(len(read_csv(self.root/'metadata/train.csv')),2)
        files=list((self.root/'data/generated').rglob('*.wav'));self.assertEqual(len(files),2)
        generate(self.cfg,self.root);self.assertEqual(len(list((self.root/'data/generated').rglob('*.wav'))),2)
    def test_training_loader_never_opens_test_and_eval_opt_in(self):
        with self.assertRaises(ValueError):WaveformDataset('test',self.root)
        original_open=Path.open
        def guarded(path,*args,**kwargs):
            if path.name.startswith('test') or 'test' in path.parts:raise AssertionError('Training accessed Test')
            return original_open(path,*args,**kwargs)
        with patch.object(Path,'open',guarded):
            item=WaveformDataset('train',self.root)[0];self.assertEqual(item['label'],'A');self.assertEqual(item['split'],'train')
        self.assertEqual(WaveformDataset('test',self.root,purpose='evaluation')[0]['label'],'A')
    def test_collision_gets_new_name_and_preserves_old_file(self):
        signature=digest(synthesis_config(self.cfg))
        path=self.root/f'data/generated/train/A/A_000001_{signature[:12]}.wav'
        path.parent.mkdir(parents=True);path.write_bytes(b'preexisting untouched')
        generate(self.cfg,self.root,limit=1)
        self.assertEqual(path.read_bytes(),b'preexisting untouched')
        self.assertTrue(path.with_stem(path.stem+'_extra1').exists())
    def test_output_cannot_target_existing_or_test(self):
        for p in [self.root/'data/existing/a.wav',self.root/'data/generated/test/a.wav',self.root/'../a.wav']:
            with self.assertRaises(ValueError):safe_output(p,self.root)
    def test_generation_is_identical_in_fresh_experiment(self):
        generate(self.cfg,self.root)
        with tempfile.TemporaryDirectory() as d:
            other=Path(d);cfg=fixture(other);generate(cfg,other)
            self.assertEqual([sha256(p) for p in sorted((self.root/'data/generated').rglob('*.wav'))],
                             [sha256(p) for p in sorted((other/'data/generated').rglob('*.wav'))])


if __name__=='__main__':unittest.main()
