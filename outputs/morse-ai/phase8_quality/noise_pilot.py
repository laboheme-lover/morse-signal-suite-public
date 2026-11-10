"""Paired synthetic-signal diagnostic with existing and external noise corpora."""
from pathlib import Path
import csv,hashlib,json,math,sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
sys.path.insert(0,str(PROJECT));sys.path.insert(0,str(ROOT))
from noise_preparation import mix_at_snr
from generate_morse_audio import generate_morse_audio
import evaluate_new

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    out=ROOT/'noise_pilot';out.mkdir(exist_ok=False)
    noise_path=ROOT/'external_noise/DEMAND/OOFFICE_ch01.wav'
    provenance=json.loads((noise_path.parent/'provenance.json').read_text(encoding='utf-8'))
    assert sha(noise_path)==provenance['selected_sha256']
    with (PROJECT/'data/ESC-50-master/meta/esc50.csv').open(encoding='utf-8') as f:
        known=next(r for r in csv.DictReader(f) if r['category']=='keyboard_typing')
    known_path=PROJECT/'data/ESC-50-master/audio'/known['filename']
    # Check exact bytes against all locally available ESC-50 sources. Not a perceptual duplicate proof.
    external_hash=sha(noise_path)
    exact_duplicates=[p.name for p in (PROJECT/'data/ESC-50-master/audio').glob('*.wav') if sha(p)==external_hash]
    assert not exact_duplicates
    clean=np.concatenate([generate_morse_audio(c,.1,700,.7,padding=.15) for c in 'イロハ'])
    noises={}
    for label,path,offset_seconds in [('existing_category',known_path,0),('external_office',noise_path,10)]:
        audio,sr=sf.read(path,dtype='float64')
        if audio.ndim!=1:raise ValueError('Explicit mono channel required')
        if sr!=16000:
            divisor=math.gcd(sr,16000);audio=resample_poly(audio,16000//divisor,sr//divisor)
        noises[label]=(audio,round(offset_seconds*16000),path,sr)
    plan=dict(scope='PILOT_DIAGNOSTIC_SYNTHETIC_MORSE_NOT_INDEPENDENT_TEST',text='イロハ',seed=None,
        frequency_hz=700,dot_seconds=.1,padding_seconds=.15,snrs=[20,10,5,0,-5],noise_provenance=provenance,
        known_noise=dict(path=str(known_path),sha256=sha(known_path),category='keyboard_typing',scope='previously used category, specific file training use not asserted'),
        external_exact_byte_duplicates_in_local_esc50=exact_duplicates,
        limitations='One synthetic phrase and one excerpt per noise, no unseen-category claim, no model selection. No final acceptance threshold.',
        scripts={str(p.relative_to(PROJECT)):sha(p) for p in [Path(__file__),ROOT/'noise_preparation.py']})
    (out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    cases=[('clean',None,None)]+[(f'{label}_{snr}',label,snr) for label in noises for snr in plan['snrs']]
    rows=[]
    for ident,label,snr in cases:
        folder=out/ident;folder.mkdir()
        if label:
            noise,offset,path,sr=noises[label];audio,meta=mix_at_snr(clean,noise,snr,offset=offset)
            meta.update(noise_source=str(path),noise_sha256=sha(path),source_sample_rate=sr,output_sample_rate=16000)
        else:audio=clean;meta={'condition':'unmixed clean control','output_sample_rate':16000}
        sf.write(folder/'input.wav',audio,16000,subtype='FLOAT');(folder/'reference.txt').write_text('イロハ',encoding='utf-8')
        meta['wav_sha256']=sha(folder/'input.wav');(folder/'mixture.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
        manifest=dict(source_review_completed=False,purpose=plan['scope'],recordings=[dict(id=ident,audio='input.wav',reference='reference.txt',group_id='synthetic_phrase_001',declared_unseen=False,body={'mode':'full'})])
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        code=evaluate_new.run(folder/'manifest.json',folder/'results',rehearsal=True)
        assert code in (0,2)
        result=json.loads((folder/'results/recording_results.json').read_text(encoding='utf-8'))
        for r in result:rows.append(dict(condition=label or 'clean',snr_db=snr,**r))
    evaluate_new.verify_frozen()
    for path,expected in plan['scripts'].items():assert sha(PROJECT/path)==expected
    assert sha(noise_path)==provenance['selected_sha256'] and sha(known_path)==plan['known_noise']['sha256']
    (out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 環境音混合の予備診断','', '合成「イロハ」1文・各ノイズ1区間。独立実録音評価、未知カテゴリ評価、モデル採用判定ではありません。',
        '全条件で同じ信号を使用。既知カテゴリ対照はESC-50 keyboard_typing、別コーパスはDEMAND OOFFICE ch01の10秒位置から。',
        'SNRは無音を含む全文区間のRMS比。処理失敗も全削除として計上。モデル・既存固定計画は変更なし。','',
        '|条件|SNR dB|M1 CER|M2 CER|M3 CER|M4 CER|','|---|---:|---:|---:|---:|---:|']
    for ident,label,snr in cases:
        items=[r for r in rows if r['id']==ident]
        values=['FAILED' if r['status']=='FAILED' else f"{r['cer']:.1%}" for r in items]
        lines.append('|'+str(label or 'clean')+'|'+str(snr if snr is not None else '—')+'|'+'|'.join(values)+'|')
    lines += ['', '出典：[DEMAND公式配布記録](https://zenodo.org/records/1227121)。録音作者・ライセンス・チェックサムはplan.jsonとexternal_noise/DEMAND/provenance.jsonを参照。',
        'この結果を使った再学習・しきい値調整は行っていません。複数文章・複数収録環境・複数区間での評価が必要です。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (out/'verification.json').write_text(json.dumps(dict(completed=True,conditions=len(cases),model_recordings=len(rows),models_and_sources_unchanged=True,scope=plan['scope']),indent=2),encoding='utf-8')
    print('Pilot complete: 11 conditions x 4 frozen models')

if __name__=='__main__':main()
