from pathlib import Path
import os,json
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.plot_cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'Yu Gothic','font.size':11,'axes.unicode_minus':False})
colors=['#2166ac','#e08214','#1b9e77','#984ea3'];models=['M1','M2','M3','M4']
data=json.loads((ROOT/'noise_expanded/summary.json').read_text(encoding='utf-8'))
fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
for ax,(noise,label) in zip(axes.flat,[('OOFFICE','オフィス'),('DKITCHEN','キッチン'),('STRAFFIC','交通音'),('gaussian_control','ガウス雑音（対照）')]):
    for model,color in zip(models,colors):
        values=[r for r in data if r['model']==model and r['noise']==noise]
        ax.plot(range(5),[v['cer']*100 for v in values],label=model,color=color,marker='o',alpha=.85)
    ax.set_xticks(range(5),['20','10','5','0','−5']);ax.set_ylim(-.5,23);ax.set_title(label)
    ax.set_xlabel('SNR（dB）：右ほど雑音が強い');ax.set_ylabel('文字誤り率 CER（%）');ax.grid(alpha=.2);ax.legend(ncol=4,fontsize=9)
fig.suptitle('ノイズ予備診断：合成3文・2速度・各録音3区間\n独立した実録音テストではありません',fontsize=15)
fig.savefig(ROOT/'noise_expanded/cer_by_noise.png',dpi=160);plt.close(fig)
data=json.loads((ROOT/'model_operations/summary.json').read_text(encoding='utf-8'))
fig,axes=plt.subplots(1,2,figsize=(11,4.8),layout='constrained')
times=[next(c for c in r['conditions'] if c['id']=='long') for r in data]
for i,(r,t,color) in enumerate(zip(data,times,colors)):
    axes[0].bar(i,t['median_seconds'],color=color,width=.55)
    axes[0].errorbar(i,t['median_seconds'],yerr=[[t['median_seconds']-t['min_seconds']],[t['max_seconds']-t['median_seconds']]],color='black',capsize=4)
    axes[0].text(i,.025,f"{t['median_seconds']:.3f}",ha='center',color='white',weight='bold')
    axes[1].bar(i,r['peak_mib_max'],color=color,width=.55);axes[1].text(i,30,f"{r['peak_mib_max']:.1f}",ha='center',color='white',weight='bold')
for ax in axes:ax.set_xticks(range(4),models);ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.2)
axes[0].set_title('272秒音声の処理時間\n15観測の中央値、線は最小〜最大');axes[0].set_ylabel('秒（読込・分割・推論等を含む）')
axes[1].set_title('プロセスの最大メモリ\nモデルごとの3プロセス中の最大値');axes[1].set_ylabel('MiB（Python・Torch等を含む）')
fig.suptitle('同一PC・CPU 4スレッドの運用負荷比較\n合成音声による測定。別PCの性能保証ではありません',fontsize=14)
fig.savefig(ROOT/'model_operations/operations.png',dpi=160);plt.close(fig)
print('Saved 2 figures')
