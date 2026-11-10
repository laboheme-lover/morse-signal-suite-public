package jp.local.wabun;

import java.util.*;

/** Streaming frontend: calibration buffers early characters, then commits only
 * completed characters after 2 dot silence and the CNN's trailing margin.
 * Live timing is a port, not a claim of PC whole-file evaluation equivalence. */
public final class OpticalReceiver {
    private final OpticalCnn model;private final boolean automatic;private final double configured;
    private final List<Double> times=new ArrayList<>();private final List<double[]> values=new ArrayList<>();
    private final StringBuilder labels=new StringBuilder();private double committed=-1,lastAttempt=-10,unit=0;
    public String state="光の点滅を観測中",candidates="";public int count;
    public OpticalReceiver(OpticalCnn model,double configured,boolean automatic){this.model=model;this.configured=configured;this.automatic=automatic;if(!automatic)unit=configured;}
    public void accept(double t,double[] f){
        if(!Double.isFinite(t)||f.length!=4)throw new IllegalArgumentException("時刻・特徴量が不正です");
        for(double value:f)if(!Double.isFinite(value))throw new IllegalArgumentException("明るさが不正です");
        if(!times.isEmpty()&&t<=times.get(times.size()-1))throw new IllegalArgumentException("フレーム時刻が重複・逆行しています");
        if(times.size()>10800)throw new IllegalArgumentException("周期または文字区切りを確定できません。光源を再選択してください");
        times.add(t);values.add(f);
        if(t-lastAttempt>=.25){lastAttempt=t;process(false);}
    }
    private void process(boolean finish){
        if(times.size()<10)return;double[] t=times.stream().mapToDouble(Double::doubleValue).toArray();double[][] f=values.toArray(new double[0][]);
        try{
            if(unit==0)unit=OpticalMath.estimate(t,f);
            double dt=OpticalMath.medianDelta(t);for(int i=1;i<t.length;i++)if(t[i]-t[i-1]>unit*.4)throw new IllegalArgumentException("フレーム欠落：この区間の文字を確定できません");
            double[] lv=OpticalMath.levels(f);double threshold=(lv[0]+lv[1])/2,start=-1,end=-1;
            for(int i=0;i<t.length;i++){
                boolean on=f[i][0]-f[i][2]>threshold;
                if(on){if(start<0)start=t[i];end=i+1<t.length?t[i+1]:t[i]+dt;}
                else if(start>=0&&t[i]-end>=2*unit){
                    if(end>committed&&t[t.length-1]-end>=Math.max(2*unit,.5*unit/.3))classify(t,f,start,end);
                    start=end=-1;
                }
            }
            if(finish&&start>=0&&end>committed){labels.append('□');committed=end;state="末尾の文字区切り不足：□で保留";}
            else state=String.format(Locale.JAPAN,"CNN受信 %d文字単位／短点 %.0f ms（%s）\n候補：%s\n候補スコアは正解率ではありません",count,unit*1000,automatic?"自動推定・固定":"手動",candidates);
            // Keep sufficient local context; confirmed text never reclassified.
            if(committed>0){double cutoff=committed-Math.max(2,unit*4);int remove=0;while(remove<times.size()&&times.get(remove)<cutoff)remove++;if(remove>0){times.subList(0,remove).clear();values.subList(0,remove).clear();}}
        }catch(IllegalArgumentException e){state=e.getMessage();if(unit>0&&state.startsWith("フレーム欠落")){labels.append('□');times.clear();values.clear();committed=-1;if(automatic)unit=0;}if(finish&&unit==0)state+="。周期未確定のため認識結果を出しません";}
    }
    private void classify(double[] t,double[][] f,double start,double end){
        float[] p=model.probabilities(OpticalMath.input(t,f,start,end,unit));Integer[] order=new Integer[65];for(int i=0;i<65;i++)order[i]=i;Arrays.sort(order,(a,b)->Float.compare(p[b],p[a]));
        labels.append(model.labels[order[0]]);count++;committed=end;StringBuilder s=new StringBuilder();for(int i=0;i<3;i++)s.append(MorseCodec.hiragana(model.labels[order[i]])).append(String.format(Locale.JAPAN," %.1f%%  ",p[order[i]]*100));candidates=s.toString();
    }
    public String text(){return MorseCodec.hiragana(labels.toString());}
    public void finish(){process(true);}
}
