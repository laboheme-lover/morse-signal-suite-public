import jp.local.wabun.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
public final class AudioM3Test {
 public static void main(String[] args)throws Exception{
  AudioM3 m=new AudioM3(new FileInputStream(args[0]));AudioDsp dsp=new AudioDsp(new FileInputStream(args[1]));double worst=0;
  try(DataInputStream in=new DataInputStream(new BufferedInputStream(new FileInputStream(args[2])))){
   int n=in.readInt();for(int k=0;k<n;k++){float[] f=new float[in.readInt()];for(int i=0;i<f.length;i++)f[i]=in.readFloat();float[] logits=m.logits(f);int a=0,b=0;float best=-Float.MAX_VALUE;for(int i=0;i<65;i++){float v=in.readFloat();worst=Math.max(worst,Math.abs(v-logits[i]));if(logits[i]>logits[a])a=i;if(v>best){best=v;b=i;}}if(a!=b)throw new AssertionError("M3 class mismatch "+k);}
   if(worst>.0002)throw new AssertionError("M3 logit delta "+worst);System.out.println("PASS 65 variable-length M3 CNN/BiGRU parity; max delta="+worst);
   int cases=in.readInt();for(int k=0;k<cases;k++){
    double[] x=new double[in.readInt()];for(int i=0;i<x.length;i++)x[i]=in.readDouble();float[] f=AudioDsp.envelope(Arrays.copyOf(x,16000),m.envelopeFilter);if(in.readInt()!=f.length)throw new AssertionError("RMS length");for(float v:f)if(Math.abs(v-in.readFloat())>2e-5)throw new AssertionError("RMS mismatch");
    AudioDsp.Segments s=dsp.segment(x);double frequency=in.readDouble(),dot=in.readDouble();if(Math.abs(s.frequency-frequency)>.001||Math.abs(s.dot-dot)>.0001)throw new AssertionError("Timing/frequency "+s.frequency+" / "+frequency+" dot "+s.dot+" / "+dot);
    if(in.readInt()!=s.ranges.size())throw new AssertionError("Segment count");for(int[] range:s.ranges)for(int v:range)if(Math.abs(v-in.readInt())>1)throw new AssertionError("Segment boundary");
    String expected=MorseCodec.hiragana(in.readUTF());String actual=new AudioM3Recognition(m,dsp).recognize(x,()->false);if(!actual.equals(expected))throw new AssertionError("File "+k+" "+actual+" / "+expected);System.out.println("PASS file "+k+" waveform -> segments -> RMS -> M3 -> "+actual);
    if(k<3){final String[] liveText={""};try(AudioM3Live live=new AudioM3Live(new AudioM3Recognition(m,dsp),(state,text)->liveText[0]=text)){
     java.lang.reflect.Field pending=AudioM3Live.class.getDeclaredField("pending");pending.setAccessible(true);
     for(int pos=0;pos<x.length;pos+=640){short[] chunk=new short[Math.min(640,x.length-pos)];for(int i=0;i<chunk.length;i++)chunk[i]=(short)Math.round(x[pos+i]*32768);live.push(chunk,chunk.length);Future<?> job=(Future<?>)pending.get(live);if(job!=null)job.get(30,TimeUnit.SECONDS);}
     if(!liveText[0].equals(expected))throw new AssertionError("Live "+liveText[0]+" / "+expected);System.out.println("PASS microphone-like 40ms chunk replay: "+liveText[0]);
    }}
   }
   int rates=in.readInt();for(int k=0;k<rates;k++){
    int rate=in.readInt();float[] pcm=new float[in.readInt()];for(int i=0;i<pcm.length;i++)pcm[i]=in.readFloat();String expected=MorseCodec.hiragana(in.readUTF());
    String actual=new AudioM3Recognition(m,dsp).recognize(AudioM3Recognition.resample(pcm,rate),()->false);if(!actual.equals(expected))throw new AssertionError("Resampled "+rate+" "+actual+" / "+expected);System.out.println("PASS "+rate+"Hz file resampling text vs PC: "+actual);
   }
  }
 }
}
