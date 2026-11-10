package jp.local.wabun;
import java.util.*;
import java.util.concurrent.*;

/** Capture never waits for CNN inference. Only one bounded snapshot is in flight. */
public final class AudioM3Live implements AutoCloseable {
 public interface Listener{void update(String state,String text);}
 private final AudioM3Recognition recognizer;private final Listener listener;
 private final ExecutorService worker=Executors.newSingleThreadExecutor();private Future<?> pending;
 private final float[] ring=new float[16000*12];private long samples,lastSnapshot,committed,inspected;private volatile boolean closed;
 private final StringBuilder labels=new StringBuilder();
 public AudioM3Live(AudioM3Recognition r,Listener l){recognizer=r;listener=l;}
 public void push(short[] x,int n){
  for(int i=0;i<n;i++)ring[(int)(samples++%ring.length)]=x[i]/32768f;
  if(samples<32000||samples-lastSnapshot<8000||(pending!=null&&!pending.isDone()))return;
  lastSnapshot=samples;int length=(int)Math.min(samples,ring.length);long offset=samples-length;double[] audio=new double[length];for(int i=0;i<length;i++)audio[i]=ring[(int)((offset+i)%ring.length)];
  pending=worker.submit(()->{
   try{
    if(inspected>0&&offset>inspected){labels.append('□');committed=offset;}
    inspected=offset+audio.length;
    AudioDsp.Segments s=recognizer.dsp.segment(audio);
    if(s.toneRatio<.35)throw new IllegalArgumentException("安定した単一音を確認するまで待機します");
    for(int i=0;i<s.ranges.size()&&!closed;i++){
     int[] range=s.ranges.get(i);long end=offset+range[1];
     if(end<=committed||offset+range[0]<committed||(offset>0&&range[0]<800)||audio.length-range[1]<Math.max(2*s.dot*16000,1920))continue;
     labels.append(recognizer.character(audio,range,s.patterns.get(i)));committed=end;
    }
    if(!closed)listener.update(String.format(Locale.JAPAN,"M3マイク受信／推定音程 %.0f Hz・短点 %.0f ms\n要確認 %d／候補 %s\n候補スコアは正解率ではありません",s.frequency,s.dot*1000,recognizer.review,recognizer.candidates),MorseCodec.hiragana(labels.toString()));
   }catch(IllegalArgumentException e){if(!closed)listener.update("M3受信待機："+e.getMessage(),MorseCodec.hiragana(labels.toString()));}
  });
 }
 public void close(){closed=true;worker.shutdownNow();}
}
