"""Local saved-result viewer, independent from the inference applications."""
from pathlib import Path
import csv
import io
import json
import streamlit as st
from evaluation_compare import load_bundle, aggregate, paired

ROOT=Path(__file__).resolve().parent

def main():
    st.title('保存した評価結果の比較')
    st.caption('合成音声と既知の実録音の開発評価です。新しい録音の独立評価や採用モデルの確定とは区別してください。')
    st.info('CERは編集距離の合計÷正解文字数の合計です。括弧はモード制御として処理済みです。予測確率は正解率ではありません。')
    defaults=list((ROOT/'phase8_quality/saved_error_analysis').glob('*_comparison.json'))
    experiments=list((ROOT/'phase8_quality/frontend_experiment_v1').glob('*/*_comparison.json'))
    experiments+=list((ROOT/'phase8_quality/frontend_stress_v1/comparisons').glob('*_comparison.json'))
    experiments+=list((ROOT/'phase8_quality/timing_experiment_v1').glob('*/comparisons/*_comparison.json'))
    experiments+=list((ROOT/'phase8_quality/adaptive_experiment_v1').glob('*/comparisons/*_comparison.json'))
    experiments+=list((ROOT/'phase8_quality/real_adaptive_v1/comparisons').glob('*_comparison.json'))
    experiments+=list((ROOT/'phase8_quality/real_low_memory_v1/viewer_comparisons').glob('*_comparison.json'))
    selected=st.multiselect('保存済み評価',defaults+experiments,default=[p for p in defaults if not p.name.startswith('pilot_')],format_func=lambda p:('low_memory_' if 'real_low_memory_v1' in p.parts else '')+p.stem)
    st.caption('development＝改善案の開発条件、held＝事前固定した未使用条件、baseline＝従来処理、segment_mode_v1＝区間検出＋切替補正の実験版。実験版は通常の認識アプリには適用していません。')
    st.caption('timing_v1＝短点推定だけを変更した実験版。音の長さと無音の長さを合わせて推定します。')
    st.caption('adaptiveのtracking＝短点推定＋音程追従、tempo＝短点推定＋速度補正、combined＝両方、combined_mode＝さらに切替補正を加えた方式です。')
    st.caption('known_real＝既知44録音の本文範囲を固定した再評価。guarded＝自動切り戻しの検証用で、採用は保留しています。')
    st.caption('low_memory_known_real＝省メモリ版で同じ44録音を再処理した結果です。')
    uploads=st.file_uploader('別の比較用JSONを追加（morse-saved-evaluation-v1、1ファイル20 MB以下）',type=['json'],accept_multiple_files=True,max_upload_size=20)
    bundles=[]
    for name,raw in [(p.name,p.read_bytes()) for p in selected]+[(u.name,u.getvalue()) for u in uploads]:
        try:
            b=load_bundle(raw); b['name']=f"{b['name']} [{len(bundles)+1}]"; bundles.append(b)
        except ValueError as exc: st.error(f'{name}: {exc}')
    if not bundles:
        st.info('評価ファイルを選択してください。');return
    policies={(b['scoring_policy'],b['scope']) for b in bundles}
    if len(policies)>1:
        st.error('採点基準または評価対象が異なります。同じ基準のファイルを選択してください。');return
    st.caption('採点基準：'+bundles[0]['scoring_policy'])
    rows=[dict(r,evaluation=b['name']) for b in bundles for r in b['rows']]
    noises=sorted({str(r.get('noise','不明')) for r in rows})
    filters=st.multiselect('環境音',noises,default=noises)
    snrs=sorted({str(r.get('snr_db')) for r in rows})
    snr_filter=st.multiselect('SNR（None＝無雑音）',snrs,default=snrs)
    speeds=sorted({str(r.get('dot_seconds')) for r in rows})
    speed_filter=st.multiselect('短点の長さ（秒）',speeds,default=speeds)
    rows=[r for r in rows if str(r.get('noise','不明')) in filters and str(r.get('snr_db')) in snr_filter and str(r.get('dot_seconds')) in speed_filter]
    frequencies=sorted({str(r.get('frequency_hz','記録なし')) for r in rows})
    frequency_filter=st.multiselect('音程（Hz）',frequencies,default=frequencies)
    rows=[r for r in rows if str(r.get('frequency_hz','記録なし')) in frequency_filter]
    profiles=sorted({str(r.get('profile','通常条件')) for r in rows})
    profile_filter=st.multiselect('変動・故障条件',profiles,default=profiles)
    rows=[r for r in rows if str(r.get('profile','通常条件')) in profile_filter]
    if any('profile' in r for r in rows):
        st.caption('stress＝合成の耐性診断。driftは音程の移動、wobbleは音程の揺れ、jitterは打鍵時間のばらつき、control_notch/spikeは切替符号への人工的な欠落/余分な音です。音程欄は中心周波数です。')
    if not rows: st.warning('該当する結果はありません。');return
    st.subheader('選択した条件の集計')
    summary=aggregate(rows)
    st.dataframe(summary,hide_index=True,column_config={'CER':st.column_config.NumberColumn(format='%.4f')})
    st.caption('異なる入力集合の集計値だけで改善・悪化を判断しないでください。下で共通音声に限定できます。')
    choices=list(dict.fromkeys((r['evaluation'],r['model']) for r in rows))
    if len(choices)>1:
        left=st.selectbox('比較元',choices,format_func=lambda x:' / '.join(x))
        right=st.selectbox('比較先',choices,index=1,format_func=lambda x:' / '.join(x))
        if left!=right:
            try:
                result=paired([r for r in rows if (r['evaluation'],r['model'])==left], [r for r in rows if (r['evaluation'],r['model'])==right])
                st.subheader('同じ音声・同じ正解文での比較')
                st.dataframe([result],hide_index=True)
                if not result['共通件数']: st.warning('共通音声がないため、同一条件での差分は評価できません。')
                else: st.caption('音声ファイルのSHA-256と正規化済み正解文が一致した件だけを比較しています。同じ音声が複数条件で使われる場合は、条件IDも一致するものを対応させます。')
            except ValueError as exc: st.warning(str(exc))
    st.subheader('個別結果')
    only_errors=st.checkbox('誤り・処理失敗がある結果だけ',value=True)
    shown=[r for r in rows if not only_errors or r['edits'] or r['status']=='FAILED']
    display=[{'評価':r['evaluation'],'モデル':r['model'],'条件':r['id'],'正解':r['reference'],'認識':r['hypothesis'],
              '編集距離':r['edits'],'要確認（模擬）':r.get('ui_alert'),'状態':r['status']} for r in shown]
    st.dataframe(display,hide_index=True)
    if shown:
        index=st.selectbox('本文を確認',range(len(shown)),format_func=lambda i:f"{shown[i]['evaluation']} / {shown[i]['id']}")
        r=shown[index]
        st.text('正解：'+r['reference']+'\n認識：'+r['hypothesis'])
        with st.expander('区間・切替の診断と詳細データ'):
            st.json(r)
        st.caption('baseline_alert＝保存時の警告、ui_alert＝既存アプリの既定条件を模擬適用。mode_error等は重複を含む観測数です。')
    stream=io.StringIO(newline='')
    keys=list(dict.fromkeys(k for r in rows for k in r))
    writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(rows)
    st.download_button('絞り込んだ全結果をCSV保存',stream.getvalue().encode('utf-8-sig'),'comparison.csv','text/csv')
    st.download_button('集計をJSON保存',json.dumps(summary,ensure_ascii=False,indent=2),'summary.json','application/json')
