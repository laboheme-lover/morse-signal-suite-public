"""Review UI: user corrections are stored separately from model predictions."""
import json
import uuid
import streamlit as st


def render_result(bundle):
    result = bundle['result']
    characters = result.get('characters', [])
    edits = bundle.setdefault('corrections', {})
    widget_id = bundle.setdefault('editor_id', uuid.uuid4().hex)
    if 'timing' in result:
        st.caption(f"推定短点時間：{result['timing']['unit_seconds']*1000:.1f} ms ／ モデル入力は300 ms基準へ補正")
    corrected = ''.join(edits.get(i, char.get('text', '')) for i, char in enumerate(characters)) if characters else result['text']
    st.subheader('認識結果（候補による修正を反映）')
    st.write(corrected)
    st.caption(f'修正した文字：{len(edits)}文字 ／ 元の認識結果は保持しています。')
    st.caption(result['warning'])
    with st.expander('元の認識結果を見る'):
        st.write(result['text'])
    st.subheader('文字ごとの変換候補')
    st.caption('文字を指定し、候補を選んで「選んだ候補を反映」を押してください。候補スコアは正解率ではありません。')
    rows = []
    for i, char in enumerate(characters):
        row = {'文字番号': i+1, '現在の文字': edits.get(i, char.get('text', '')),
               '元の認識文字': char.get('text', ''), '修正': 'あり' if i in edits else '',
               '開始（秒）': round(char['start'], 3), '終了（秒）': round(char['end'], 3)}
        candidates = char.get('candidates', [])
        for rank in range(3):
            candidate = candidates[rank] if rank < len(candidates) else {}
            row[f'第{rank+1}候補'] = candidate.get('label', '—')
            score = candidate.get('score')
            row[f'第{rank+1}候補スコア'] = f'{score:.1%}' if score is not None else '—'
        rows.append(row)
    if rows:
        st.dataframe(rows, hide_index=True, width='stretch')
        selected = st.selectbox('修正する文字', range(len(characters)), key=f'{widget_id}_position',
            format_func=lambda i: f"{i+1}文字目：{characters[i].get('text','')}（{characters[i]['start']:.2f}～{characters[i]['end']:.2f}秒）")
        char = characters[selected]
        candidates = char.get('candidates', [])
        if candidates:
            st.table([{'順位': rank+1, '候補文字': c['label'], '候補スコア': f"{c['score']:.1%}"} for rank,c in enumerate(candidates)])
            current = edits.get(selected, char.get('text', ''))
            default = next((i for i,c in enumerate(candidates) if c['label'] == current), 0)
            choice = st.selectbox('反映する候補', range(len(candidates)), index=default,
                key=f'{widget_id}_candidate_{selected}',
                format_func=lambda i: f"第{i+1}候補：{candidates[i]['label']}（スコア {candidates[i]['score']:.1%}）")
            if st.button('選んだ候補を反映', key=f'{widget_id}_apply'):
                label = candidates[choice]['label']
                if label == char.get('text', ''):
                    edits.pop(selected, None)
                else:
                    edits[selected] = label
                st.rerun()
        else:
            st.info('この文字の候補データがありません。認識を再実行してください。')
        if st.button('この文字を元に戻す', key=f'{widget_id}_undo', disabled=selected not in edits):
            edits.pop(selected, None)
            st.rerun()
        if st.button('すべての修正を取り消す', key=f'{widget_id}_reset', disabled=not edits):
            edits.clear()
            st.rerun()
    else:
        st.info('認識した文字がありません。光源範囲と動画を確認してください。')
    # Keep original text, scores and candidates untouched for later review.
    export = dict(result, corrected_text=corrected, corrections=[
        {'character_number': i+1, 'original': characters[i]['text'], 'replacement': label,
         'start': characters[i]['start'], 'end': characters[i]['end']}
        for i,label in sorted(edits.items())])
    st.download_button('修正後の文章をTXT保存', corrected, 'optical_ml_corrected.txt', 'text/plain; charset=utf-8')
    st.download_button('結果JSONを保存（元の結果・修正内容）', json.dumps(export, ensure_ascii=False, indent=2), 'optical_ml_result.json', 'application/json')
