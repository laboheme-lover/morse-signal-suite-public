"""Reporting only; no model, preprocessing or recognition changes."""
import csv,html,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'outputs/optical_remaining_20261013'

def main():
 d=json.loads((P/'results.json').read_text(encoding='utf-8'));assert d['complete']
 plan=json.loads((P/'plan.json').read_text(encoding='utf-8'));records={r['no']:r for r in plan['records']}
 previous=json.loads((ROOT/'outputs/optical_adaptive_timing_development_v2_20261013/results.json').read_text(encoding='utf-8'))
 summaries=[]
 for t in d['totals']:
  rs=[r for r in d['records'] if r['condition']==t['condition']]
  old=next(r for r in previous['totals'] if r['method']=='auto_segmentation_and_input' and r['condition']==t['condition'])
  assert len(rs)==34 and t['N']==3510
  summaries.append(dict(condition=t['condition'],new34_CER=t['CER'],new34_macro_CER=sum(r['CER'] for r in rs)/34,new34_exact=t['exact'],new34_holds=t['failures'],development10_CER=old['CER'],development10_exact=old['exact']))
 with (P/'前回10件と追加34件の比較.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
 grouped=[]
 for source in sorted(set(r['original_recording'] for r in records.values())):
  ns={n for n,r in records.items() if r['original_recording']==source}
  for t in d['totals']:
   rs=[r for r in d['records'] if r['no'] in ns and r['condition']==t['condition']]
   grouped.append(dict(source=source,condition=t['condition'],cases=len(rs),N=sum(r['N'] for r in rs),errors=sum(r['errors'] for r in rs),holds=sum(r['failure'] for r in rs)))
 with (P/'撮影動画別の内訳.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(grouped[0]));w.writeheader();w.writerows(grouped)
 failures=[dict(no=r['no'],condition=r['condition'],reason=r['error']) for r in d['records'] if r['failure']]
 with (P/'周期推定の記録.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['No','条件','推定短点ms','周期適合率','平均単位残差','保留理由'])
  for r in d['records']:
   timing=r.get('timing') or {}
   w.writerow([r['no'],r['condition'],1000*timing['unit_seconds'] if timing else '',timing.get('fit_fraction',''),timing.get('mean_unit_residual',''),r['error']])
 (P/'保留一覧.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding='utf-8')
 N=sum(r['N'] for r in d['records']);errors=sum(r['errors'] for r in d['records']);exact=sum(r['exact'] for r in d['records'])
 notes=f'''評価完了：34電文×12条件＝408ケース。正解は1条件あたり3510文字単位。
全条件参考合算：{N}文字単位、{errors}修正、CER {errors/N:.2%}、全文一致{exact}/408、保留・失敗{len(failures)}/408。
この合算は同じ34原稿を繰り返したもので、独立した文字数・録画数ではない。No.63・64は長いため、文字数加重の合計に大きく寄与する。前回比較CSVに各電文を等しく扱った平均CERも併記。
No.41～50は試作v2の開発に使用した10件。No.53～86は今回、固定済みの試作v2を適用した追加34件であり、この結果を見たモデル調整・再学習は行っていない。両群の値は記録条件や原稿が異なるため、直接の優劣を意味しない。
34電文は6本の録画から切り出したもの。電文境界は原稿の点滅列と事前照合済みで、元動画全体から自動で光源を見つける工程を含む完全独立評価ではない。
元動画・加工とも、固定CNN＋周期自動推定＋300ms基準への入力時間補正を使用。広い緑枠は中心40×40へ統一。可変ROI入力は使っていない。雨・霧は人工効果で、実天候での保証ではない。
各条件1乱数／電文。推定保留は空出力として正解文字数分の削除に計上。推論エラーを除いて成功例だけの正解率にはしていない。
保存物は光源周辺画像の全フレーム、時刻、加工後特徴、加工パラメータ、固定コードとモデル、原稿と認識の文字対応。全サイズの加工MP4は作らず、同じ乱数で再生成可能な形で保管した。元動画は変更していない。
'''
 (P/'評価の読み方.txt').write_text(notes,encoding='utf-8')
 p=P/'評価結果.html';s=p.read_text(encoding='utf-8');s=s.replace('<h2>電文別の正解と認識結果</h2>','<h2>集計と評価上の位置づけ</h2><pre style="white-space:pre-wrap;font-family:inherit;line-height:1.8">'+html.escape(notes)+'</pre><h2>電文別の正解と認識結果</h2>');p.write_text(s,encoding='utf-8')
 print(notes);print(json.dumps(summaries,ensure_ascii=False))

if __name__=='__main__':main()
