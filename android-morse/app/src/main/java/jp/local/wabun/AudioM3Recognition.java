package jp.local.wabun;
import java.util.*;
import java.util.function.BooleanSupplier;

/** Wabun-only policy; never switches the interpretation of parentheses. */
public final class AudioM3Recognition {
 public final AudioM3 model;public final AudioDsp dsp;public String candidates="";public int review;
 public AudioM3Recognition(AudioM3 m,AudioDsp d){model=m;dsp=d;}
 public String character(double[] audio,int[] range,String pattern){
  if(pattern.equals("-..---")||pattern.equals("...-."))return "";
  float[] p=model.probabilities(AudioDsp.envelope(AudioDsp.clip(audio,range),model.envelopeFilter));Integer[] order=new Integer[65];for(int i=0;i<65;i++)order[i]=i;Arrays.sort(order,(a,b)->Float.compare(p[b],p[a]));
  StringBuilder s=new StringBuilder();for(int i=0;i<3;i++)s.append(MorseCodec.hiragana(model.labels[order[i]])).append(String.format(Locale.JAPAN," %.1f%%  ",p[order[i]]*100));candidates=s.toString();
  String label=model.labels[order[0]];boolean supported=MorseCodec.TABLE.containsValue(pattern);
  if(!supported||p[order[0]]<.8||!pattern.equals(MorseCodec.TABLE.get(label.charAt(0))))review++;
  return supported?label:"□";
 }
 public String recognize(double[] audio,BooleanSupplier cancelled){
  AudioDsp.Segments s=dsp.segment(audio);StringBuilder text=new StringBuilder();
  boolean framing=s.patterns.size()>6&&s.patterns.subList(0,5).equals(Arrays.asList("....",".-.","....",".-.","-...-"))&&s.patterns.get(s.patterns.size()-1).equals(".-.-.");
  for(int i=0;i<s.ranges.size();i++){if(cancelled.getAsBoolean())break;if(framing&&(i==4||i==s.ranges.size()-1))continue;text.append(character(audio,s.ranges.get(i),s.patterns.get(i)));}return MorseCodec.hiragana(text.toString());
 }
 /** Windowed-sinc resampling. 16 kHz input is unchanged; other rates require
  * independent comparison because PC uses librosa/soxr instead. */
 public static double[] resample(float[] x,int rate){
  if(rate<8000||rate>192000)throw new IllegalArgumentException("音声サンプルレートが範囲外です");
  int n=(int)Math.ceil(x.length*16000./rate);double[] y=new double[n];if(rate==16000){for(int i=0;i<n;i++)y[i]=x[i];return y;}
  double cutoff=Math.min(1,16000./rate)*.95;int radius=(int)Math.ceil(24/cutoff);
  for(int i=0;i<n;i++){double pos=i*(rate/16000.),sum=0,norm=0;int center=(int)pos;
   for(int k=center-radius;k<=center+radius;k++){double d=k-pos;if(Math.abs(d)>=radius)continue;double u=Math.PI*d*cutoff;double w=(Math.abs(u)<1e-12?cutoff:Math.sin(u)/(Math.PI*d))*(.5+.5*Math.cos(Math.PI*d/radius));if(k>=0&&k<x.length)sum+=w*x[k];norm+=w;}
   y[i]=sum/norm;
  }return y;
 }
}
