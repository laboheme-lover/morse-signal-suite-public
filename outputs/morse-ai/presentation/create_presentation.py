"""Build seven editable slides from frozen evidence; no app/model writes.
Usage: python create_presentation.py [--output NEW_DIRECTORY]
The default uses assets/presentation_data.json beside this script.
"""
import argparse,hashlib,json,math
from datetime import datetime
from pathlib import Path
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE,XL_LABEL_POSITION,XL_LEGEND_POSITION,XL_TICK_MARK
from pptx.enum.shapes import MSO_SHAPE,MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN,MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches,Pt

NAVY='142D4E';BLUE='0072B2';ORANGE='D55E00';GRAY='5D6876';LIGHT='F1F5F9';WHITE='FFFFFF';LINE='D9E2EB'
FONT='Yu Gothic'
def color(s):return RGBColor.from_string(s)
def text(slide,x,y,w,h,value,size=22,bold=False,fill=NAVY,align=PP_ALIGN.LEFT):
    shape=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
    tf=shape.text_frame;tf.clear();tf.word_wrap=True
    tf.margin_left=tf.margin_right=Inches(.03);tf.margin_top=tf.margin_bottom=Inches(.02)
    for i,line in enumerate(value.split('\n')):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line;p.alignment=align;p.space_after=Pt(6)
        p.font.name=FONT;p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=color(fill)
        for run in p.runs:
            props=run._r.get_or_add_rPr();ea=OxmlElement('a:ea');ea.set('typeface',FONT);props.append(ea)
    return shape
def rect(slide,x,y,w,h,fill=LIGHT,line=LINE):
    s=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h))
    s.fill.solid();s.fill.fore_color.rgb=color(fill);s.line.color.rgb=color(line);return s
def box(slide,x,y,w,h,label,fill=LIGHT,edge=LINE,size=22):
    s=rect(slide,x,y,w,h,fill,edge)
    t=text(slide,x+.09,y+.12,w-.18,h-.2,label,size,fill=NAVY,align=PP_ALIGN.CENTER);t.text_frame.vertical_anchor=MSO_ANCHOR.MIDDLE
    return s
def arrow(slide,x1,y1,x2,y2,c=GRAY):
    s=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(x1),Inches(y1),Inches(x2),Inches(y2))
    s.line.color.rgb=color(c);s.line.width=Pt(1.8)
    tail=OxmlElement('a:tailEnd');tail.set('type','triangle');s.line._get_or_add_ln().append(tail)
def base(prs,title,number,source):
    s=prs.slides.add_slide(prs.slide_layouts[6]);s.background.fill.solid();s.background.fill.fore_color.rgb=color(WHITE)
    rect(s,.5,.4,.09,.52,BLUE,BLUE);text(s,.75,.39,12,.65,title,32,True)
    text(s,.6,7.10,11.8,.27,source,14,fill=GRAY);text(s,12.25,7.09,.5,.28,str(number),14,fill=GRAY,align=PP_ALIGN.RIGHT)
    return s
def native_chart(slide,x,y,w,h,cats,series,ytitle,maximum,fmt='0.00',percent=True):
    data=CategoryChartData();data.categories=cats
    for name,vals in series:data.add_series(name,vals)
    chart=slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,Inches(x),Inches(y),Inches(w),Inches(h),data).chart
    chart.has_legend=len(series)>1
    if chart.has_legend:
        chart.legend.position=XL_LEGEND_POSITION.BOTTOM;chart.legend.include_in_layout=False;chart.legend.font.name=FONT;chart.legend.font.size=Pt(18)
    chart.chart_style=10
    va=chart.value_axis;va.minimum_scale=0;va.maximum_scale=maximum;va.has_title=True;va.axis_title.text_frame.text=ytitle
    va.axis_title.text_frame.paragraphs[0].font.name=FONT;va.axis_title.text_frame.paragraphs[0].font.size=Pt(18)
    va.tick_labels.font.name=FONT;va.tick_labels.font.size=Pt(18);va.tick_labels.number_format='0'
    va.major_tick_mark=XL_TICK_MARK.NONE;va.has_major_gridlines=True;va.major_gridlines.format.line.color.rgb=color(LINE)
    ca=chart.category_axis;ca.tick_labels.font.name=FONT;ca.tick_labels.font.size=Pt(20);ca.major_tick_mark=XL_TICK_MARK.NONE
    plot=chart.plots[0];plot.gap_width=90;plot.has_data_labels=True
    labels=plot.data_labels;labels.position=XL_LABEL_POSITION.OUTSIDE_END;labels.font.name=FONT;labels.font.size=Pt(20);labels.font.color.rgb=color(NAVY)
    labels.number_format=fmt+('"%"' if percent else '')
    for i,serie in enumerate(chart.series):
        serie.format.fill.solid();serie.format.fill.fore_color.rgb=color([BLUE,ORANGE][i%2]);serie.format.line.fill.background()
    if len(series)==1:
        for i,p in enumerate(chart.series[0].points):p.format.fill.solid();p.format.fill.fore_color.rgb=color([BLUE,ORANGE][i%2])
    return chart

NOTES=[
'''和文モールス信号AI翻訳アプリを開発しました。音声ファイルを読み込み、認識した文章だけでなく、文字ごとの候補や予測確率、メルスペクトログラムを確認できるアプリです。自作のPyTorch CNNをStreamlitの画面へ組み込み、ローカルPCで動かします。このスライド下部は表示項目を説明する画面イメージで、実際のスクリーンショットではありません。本発表では、アプリの仕組み、合成データによる学習、そして実録音評価を紹介します。特に、認識方式の違いだけでなく、評価する文字の範囲や表記をどう揃えるかが数値に大きく影響した点をお伝えします。''',
'''CNNとルール方式は、処理を分けて実装しています。最初に共通の処理で音の区間と短点・長点などの符号を取得します。CNN側では切り出した音声をメルスペクトログラムへ変換し、65クラスの文字候補を分類します。ルール側では取得した符号を対応表で文字にします。括弧や手続符号の管理には検出した符号を使い、CNN側もそのモードに応じて元ラベルを読み替えます。正解文を見てCNN出力を修正する処理ではありません。ただし、CNN側にも区間やモード処理の補助があるため、CNN単独の完全自動評価とは区別する必要があります。ルール出力は別の比較欄で確認できます。''',
'''学習には正解が分かる合成モールス音声を使いました。現在のモデルにつながる追加学習では、16キロヘルツの音声に対し、短点を50から170ミリ秒、周波数を550から850ヘルツ、振幅を0.2から0.9の範囲で変化させています。タイミングの揺らぎも最大10パーセントまで与えました。追加分はクリーン音声と白色雑音で、従来データのESC-50雑音も保持しています。追加分の白色雑音はSNR 0、5、10、20デシベルです。メル入力から3段の畳み込みなどを経て65クラスへ分類します。学習は20,150件、検証は4,225件で、検証成績でモデルを選択しています。耐ノイズ性を調べる設定を作ったことと、CNNの耐ノイズ優位性を証明したことは別です。''',
'''既存の本文中心の評価は40件、16,317文字です。保存レポートを再確認すると、CNN方式の編集距離は1,149、CERは約7.04パーセント、ルール方式は編集距離16、CER約0.10パーセントでした。CERは置換、削除、挿入の合計を正解文字数で割った文字誤り率で、低いほどよい指標です。この評価対象と条件では、ルール方式のCERが低かったといえます。ただし、本文の開始と終了、句読点の除外、表記正規化、混在文のモード処理を含む評価です。CNN単体の分類Accuracyではありません。また過去に開発で接触した録音も含み、40件全体を未見の独立testとは呼んでいません。この集計はDRAFTとして保持しています。''',
'''追加の57、62、64、67は、アプリから保存した最終テキストを原稿と全文比較しました。空白、句読点、小書きカナ、濁点の表し方などを残したため、先ほどの40件とは評価条件が異なります。4件合計は2,250文字で、CNNの統合CERは48.04パーセント、ルールは43.56パーセントです。これは各録音CERの単純平均ではなく、総編集距離を総正解文字数で割った値です。特に64の値が高く見えますが、同じ条件でモデル性能が悪化したという意味ではありません。保存テキスト比較だけで音声入力からの完全自動End-to-End性能を検証できたともいえません。40件と合算した44件のCERは算出していません。''',
'''64を詳しく調べると、正解1,141文字のうち362文字が行内空白でした。そこで保存出力を変えず、正解文だけに従来確認済みの正規化を適用する補助分析を行いました。編集距離はCNNで686から68、ルールで652から6へ変化しました。これは空白だけの効果ではなく、小書きカナや濁点などの表記、さらに最短編集対応の変化を含む結果です。モデルを再学習したわけではなく、精度が改善したとは表現しません。また本文の開始終了を確定していないため、Legacy互換CERでもありません。高い全文CERには表記差が大きく関係していましたが、残った編集をすべて純粋な認識誤りとみなすこともできません。''',
'''成果は、操作可能なアプリを実装したこと、連続音声と括弧内欧文に対応したこと、そして実録音の評価を条件別に整理したことです。次は区間情報、正規化、実行条件を共通形式で保存し、同じ条件で比較できるようにします。62では保存出力に括弧付きのIPCC、CM、KMが存在した一方、従来の正解文正規化は括弧なし英字を拒否しました。これはアプリに欧文認識能力が全くないという話とは異なります。評価側の扱いを整理する必要があります。そのうえで同一条件の耐ノイズ比較を行い、動画入力へ拡張します。今回の対象ではルール方式が低いCERを示しました。今後は共通の評価条件で、AIを組み込む効果がどの条件にあるかを検証します。'''
]

def build(out,data_path):
    d=json.loads(data_path.read_text(encoding='utf-8'));old=d['legacy40'];strict=d['strict4'];diag=d['aux64']
    assert old['recordings']==40 and old['reference_units']==16317 and old['cnn_edit_distance']==1149 and old['rule_edit_distance']==16
    assert strict['combined']['reference_chars']==2250
    records=strict['records'];assert [r['file_no'] for r in records]==[57,62,64,67]
    assert [diag[m]['edit_distance'] for m in ('cnn','rule')]==[68,6]
    out.mkdir(parents=True,exist_ok=True)
    prs=Presentation();prs.slide_width=Inches(13.333333);prs.slide_height=Inches(7.5)
    s=base(prs,'和文モールス信号AI翻訳アプリ',1,'実装：app.py / predict_sequence.py')
    text(s,.75,1.18,11.9,.45,'自作PyTorch CNN × Streamlit × 実録音評価',24)
    for x,label in [(.7,'モールス音声'),(4.55,'文字認識'),(8.4,'文章・候補\nスペクトログラム')]:box(s,x,2.15,3.35,1.05,label,size=23)
    arrow(s,4.07,2.67,4.5,2.67);arrow(s,7.92,2.67,8.35,2.67)
    text(s,.8,3.57,11.8,.55,'音声ファイルから文字列と認識の詳細を確認',26,True)
    rect(s,.8,4.3,11.7,1.75)
    text(s,1.05,4.4,11,.3,'画面イメージ（表示項目の模式図）',14,fill=GRAY)
    text(s,1.05,4.93,3.1,.8,'認識した文章\n文字列を表示',22)
    text(s,4.8,4.93,3.3,.8,'文字ごとの候補\n予測確率を表示',22)
    text(s,8.55,4.93,3.7,.8,'区間の詳細\n音声・メル画像',22)
    text(s,.8,6.45,11.6,.4,'発表者：＿＿＿＿＿＿＿＿　　発表日：＿＿＿＿＿＿＿＿',20)

    s=base(prs,'AIとルールを分けて実装・比較',2,'実装：morse_segmentation.py / predict_sequence.py / mixed_morse.py')
    text(s,.7,1.18,12,.5,'区間の取得とモード管理を共有し、文字化の方法を比較',22)
    box(s,.6,2.35,2.25,2.2,'音声から\n区間と符号\nを抽出\n【共通】',size=21)
    text(s,3.25,1.8,4.7,.4,'CNN方式',22,True,BLUE)
    box(s,3.25,2.3,2.15,1.1,'切り出し\nメル変換',edge=BLUE,size=21)
    box(s,5.85,2.3,1.9,1.1,'CNN分類\n65クラス',edge=BLUE,size=21)
    text(s,3.25,4.0,4.7,.4,'ルール方式',22,True,ORANGE)
    box(s,3.25,4.5,4.5,1.0,'符号の対応表で復号',edge=ORANGE,size=22)
    box(s,8.25,2.35,2.1,3.15,'括弧と\n手続符号で\nモード管理\n【共通】\n\n和文／欧文\nの読み替え',size=20)
    box(s,10.9,2.3,1.8,1.1,'CNN出力',edge=BLUE,size=21)
    box(s,10.9,4.5,1.8,1.0,'ルール出力',edge=ORANGE,size=20)
    for coords,c in [((2.85,2.85,3.2,2.85),BLUE),((2.85,4.45,3.2,4.98),ORANGE),((5.4,2.85,5.8,2.85),BLUE),((7.75,2.85,8.2,2.85),BLUE),((7.75,5,8.2,5),ORANGE),((10.35,2.85,10.85,2.85),BLUE),((10.35,5,10.85,5),ORANGE)]:arrow(s,*coords,c)
    text(s,.7,6.15,12,.6,'CNN側にも区間・モード処理の補助があるため、\nCNN単独の完全自動評価ではない',18,fill=GRAY)

    s=base(prs,'合成データでばらつきを与えて学習',3,'学習記録：RETRAINING_REPORT / continuous_v1 run_config / 保存モデルmanifest')
    labels=['文字・符号','音声生成','送信条件\nの変化','ノイズ付加','メル変換','小型CNN']
    for i,label in enumerate(labels):
        x=.65+i*2.1;box(s,x,1.65,1.78,1.05,label,size=20)
        if i<5:arrow(s,x+1.8,2.17,x+2.07,2.17)
    text(s,.7,3.07,6,.4,'追加学習で確認した条件',24,True)
    text(s,.7,3.67,6.35,2.6,'16 kHz ／ 短点 50〜170 ms\n周波数 550〜850 Hz\n振幅 0.2〜0.9 ／ 揺らぎ 0〜10%\n白色雑音 SNR 0 / 5 / 10 / 20 dB',22)
    text(s,7.3,3.07,5.3,.4,'実際のモデルとデータ',24,True)
    text(s,7.3,3.67,5.3,2.6,'メル 64 × 512 → 畳み込み3段\n集約・全結合 → 65クラス\n学習 20,150件 ／ 検証 4,225件\n従来のESC-50雑音データも保持',21)
    text(s,.7,6.42,12,.35,'耐ノイズ性を検証するための設定。CNNの優位性を示す結果とは区別する。',16,fill=GRAY)

    s=base(prs,'本文中心の評価：40件・16,317文字',4,'出典：final_report / provisional_summary.json（DRAFT）')
    text(s,.7,1.18,12,.5,'この評価対象・条件では、ルール方式のCERが低かった',24,True)
    native_chart(s,.55,1.85,7.65,4.5,['CNN','ルール'],[('CER',[100*old['cnn_cer'],100*old['rule_cer']])],'CER（%）',9)
    text(s,8.65,2.25,4.0,1.5,'総編集距離\nCNN：1,149\nルール：16',24)
    text(s,8.65,4.37,4.0,1.35,'CER＝文字誤り率\n置換・削除・挿入で算出\n低いほどよい',20)
    text(s,.7,6.45,12,.5,'本文抽出・正規化・モード処理を含むLegacy評価。CNN単体の分類Accuracyではない。',16,fill=GRAY)

    s=base(prs,'全文比較では表記差も誤りに含まれる',5,'出典：個別テスト結果 / analysis / summary.json・combined_4files.json')
    text(s,.7,1.17,12,.45,'追加4件は、保存出力を原稿と全文で比較',24,True)
    native_chart(s,.65,1.77,12.1,3.8,['57','62','64','67'],[(name,[r[f'{key}_cer_percent'] for r in records]) for name,key in [('CNN','cnn'),('ルール','rule')]],'CER（%）',75)
    text(s,.8,5.62,11.8,.43,'4件合計 2,250文字　　CNN：48.04%　　ルール：43.56%',23,True)
    text(s,.8,6.16,11.8,.32,'空白・句読点・大小カナ・濁点表記等を保持した、保存出力の全文比較',16,fill=GRAY)
    text(s,.8,6.6,11.8,.35,'40件と評価条件が異なるため、44件統合CERは算出していない',18,True,ORANGE)

    s=base(prs,'64番：評価表記によって編集距離が変わる',6,'出典：analysis_legacy_comparison / 64 result.json・reference_normalization_only.csv')
    text(s,.7,1.17,12,.45,'高い全文CERには、認識誤りと表記差が混在',24,True)
    native_chart(s,.6,1.83,8.25,4.22,['Strict全文比較','正解文のみ\n既存正規化'],[('CNN',[686,68]),('ルール',[652,6])],'編集距離',820,'0',False)
    text(s,9.2,2.42,3.45,1.9,'正解 1,141文字中\n空白 362文字',25,True)
    text(s,9.2,4.48,3.45,1.1,'正規化全体と\n文字対応の変化を含む',20)
    text(s,.7,6.25,12,.64,'本文未抽出の補助分析。正解側のみの正規化であり、\nモデル改善やLegacy互換CERを示す値ではない。',18,True,ORANGE)

    s=base(prs,'成果と次の検証',7,'出典：実装・評価レポート / analysis_legacy_comparison（PARTIAL）')
    rect(s,.65,1.65,5.8,3.85,LIGHT,LINE);rect(s,6.9,1.65,5.8,3.85,LIGHT,LINE)
    text(s,.95,1.92,5.1,.5,'実現したこと',26,True,BLUE)
    text(s,.95,2.65,5.1,2.8,'自作CNNを組み込んだ\n操作可能なアプリ\n\n連続音声と括弧内欧文への対応\n\n実録音の評価と表記差の分析',21)
    text(s,7.2,1.92,5.1,.5,'次の検証',26,True,ORANGE)
    text(s,7.2,2.65,5.1,2.8,'区間情報・正規化・実行条件を\n共通形式で保存\n\n非括弧欧文の評価上の扱いを整理\n\n同一条件の耐ノイズ比較から動画へ',20)
    text(s,.75,5.87,11.95,.95,'今回の対象ではルール方式が低いCERを示した。\n共通の評価条件で、AIを組み込む効果がどの条件にあるかを検証する。',22,True)
    for i,(slide,note) in enumerate(zip(prs.slides,NOTES),1):slide.notes_slide.notes_text_frame.text=note+f'\n\n出典の詳細：sources.md の Slide {i}。'
    dest=out/'morse_ai_presentation.pptx';prs.save(dest)
    md='\n\n'.join(f'## Slide {i}（目安 {seconds}秒）\n\n{note}' for i,(note,seconds) in enumerate(zip(NOTES,[45,55,60,55,55,55,60]),1))
    (out/'speaker_notes.md').write_text('# 発表原稿（合計目安6分25秒）\n\n'+md,encoding='utf-8')
    (out/'requirements-presentation.txt').write_text('python-pptx==1.0.2\n',encoding='utf-8')
    reopened=Presentation(dest)
    assert len(reopened.slides)==7
    chart_count=sum(shape.has_chart for slide in reopened.slides for shape in slide.shapes)
    assert chart_count==3
    assert all(slide.notes_slide.notes_text_frame.text.strip() for slide in reopened.slides)
    for slide in reopened.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:assert 'C:\\Users' not in shape.text
            assert shape.left>=0 and shape.top>=0 and shape.left+shape.width<=prs.slide_width+10 and shape.top+shape.height<=prs.slide_height+10
    return dict(slides=7,native_charts=chart_count,notes_chars=sum(map(len,NOTES)),file=str(dest))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);parser.add_argument('--data',type=Path)
    args=parser.parse_args();home=Path(__file__).resolve().parent;out=args.output or home
    if (out/'morse_ai_presentation.pptx').exists():out=out/datetime.now().strftime('%Y%m%d_%H%M%S')
    print(json.dumps(build(out,args.data or home/'assets/presentation_data.json'),ensure_ascii=False))
