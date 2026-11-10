package jp.local.wabun;
import java.util.*;
import java.io.*;

/** Float64 SOS forward/backward filtering, RMS and Welch carrier estimation. */
public final class AudioDsp {
 private final Map<Integer,double[][][]> filters=new HashMap<>();private final Map<Integer,Integer> first=new HashMap<>();
 public AudioDsp(InputStream source)throws IOException{try(DataInputStream in=new DataInputStream(new BufferedInputStream(source))){int count=in.readInt();for(int k=0;k<count;k++){int n=in.readInt(),start=in.readInt(),size=in.readInt();double[][][] bank=new double[size][4][6];for(double[][] sos:bank)for(double[] s:sos)for(int j=0;j<6;j++)s[j]=in.readDouble();filters.put(n,bank);first.put(n,start);}}}
 public static double[] filtfilt(double[][] sos,double[] x){
  int pad=27;if(x.length<=pad)throw new IllegalArgumentException("音声が短すぎます");double[] a=new double[x.length+2*pad];
  for(int i=0;i<pad;i++){a[i]=2*x[0]-x[pad-i];a[a.length-1-i]=2*x[x.length-1]-x[x.length-pad-1+i];}
  System.arraycopy(x,0,a,pad,x.length);filter(sos,a);reverse(a);filter(sos,a);reverse(a);return Arrays.copyOfRange(a,pad,pad+x.length);
 }
 private static void reverse(double[] x){for(int i=0,j=x.length-1;i<j;i++,j--){double v=x[i];x[i]=x[j];x[j]=v;}}
 private static void filter(double[][] sos,double[] x){
  double initial=x[0],scale=1;for(double[] s:sos){double gain=(s[0]+s[1]+s[2])/(1+s[4]+s[5]);double z1=(gain-s[0])*scale*initial,z2=(s[2]-s[5]*gain)*scale*initial;
   for(int i=0;i<x.length;i++){double v=x[i],y=s[0]*v+z1;z1=s[1]*v-s[4]*y+z2;z2=s[2]*v-s[5]*y;x[i]=y;}scale*=gain;
  }
 }
 public static float[] envelope(double[] x,double[][] filter){
  x=filtfilt(filter,x);double[] energy=new double[x.length+321];for(int i=0;i<energy.length-1;i++){double v=i>=160&&i<160+x.length?x[i-160]:0;energy[i+1]=energy[i]+v*v;}
  int count=x.length/160+1;double[] rms=new double[count];for(int i=0;i<count;i++)rms[i]=Math.sqrt(Math.max(0,(energy[i*160+320]-energy[i*160])/320));
  double lo=OpticalMath.percentile(rms,.1),hi=OpticalMath.percentile(rms,.95);float[] f=new float[count];for(int i=0;i<count;i++)f[i]=(float)Math.max(0,Math.min(2,(rms[i]-lo)/Math.max(hi-lo,1e-6)));return f;
 }
 private static void fft(double[] re,double[] im){int n=re.length;for(int i=1,j=0;i<n;i++){int b=n>>1;for(;(j&b)!=0;b>>=1)j^=b;j^=b;if(i<j){double v=re[i];re[i]=re[j];re[j]=v;}}for(int len=2;len<=n;len<<=1){double angle=-2*Math.PI/len;for(int a=0;a<n;a+=len)for(int j=0;j<len/2;j++){double c=Math.cos(angle*j),s=Math.sin(angle*j);int p=a+j,q=p+len/2;double u=re[q]*c-im[q]*s,v=re[q]*s+im[q]*c;re[q]=re[p]-u;im[q]=im[p]-v;re[p]+=u;im[p]+=v;}}}
 public static final class Segments {public final List<int[]> ranges=new ArrayList<>();public final List<String> patterns=new ArrayList<>();public double frequency,dot,threshold,toneRatio;}
 public Segments segment(double[] audio){
  if(audio.length<8000)throw new IllegalArgumentException("0.5秒以上の音声が必要です");int n=16384;while(n>audio.length)n/=2;double[] power=new double[n/2+1];
  for(int offset=0;offset+n<=audio.length;offset+=n/2){double mean=0;for(int i=0;i<n;i++)mean+=audio[offset+i];mean/=n;double[] re=new double[n],im=new double[n];for(int i=0;i<n;i++)re[i]=(audio[offset+i]-mean)*(.5-.5*Math.cos(2*Math.PI*i/n));fft(re,im);for(int i=0;i<power.length;i++)power[i]+=re[i]*re[i]+im[i]*im[i];}
  int start=first.get(n),best=start;double[][][] bank=filters.get(n);for(int i=start;i<start+bank.length;i++)if(power[i]>power[best])best=i;
  Segments result=new Segments();double totalPower=0,nearPower=0;for(int i=start;i<start+bank.length;i++){totalPower+=power[i];if(Math.abs(i-best)<=2)nearPower+=power[i];}result.toneRatio=nearPower/Math.max(totalPower,1e-30);result.frequency=best*16000./n;double[] y=filtfilt(bank[best-start],audio),energy=new double[y.length+161];
  for(int i=0;i<energy.length-1;i++){int p=i-80;if(p<0)p=-p-1;if(p>=y.length)p=2*y.length-p-1;energy[i+1]=energy[i]+y[p]*y[p];}
  double[] env=new double[y.length];for(int i=0;i<env.length;i++)env[i]=Math.sqrt(Math.max(0,(energy[i+160]-energy[i])/160));double threshold=OpticalMath.percentile(env,.95)*.25;result.threshold=threshold;
  if(threshold<1e-6)throw new IllegalArgumentException("十分なモールス音を検出できません");
  List<int[]> tones=new ArrayList<>();int on=-1;for(int i=0;i<=env.length;i++){boolean v=i<env.length&&env[i]>threshold;if(v&&on<0)on=i;if(!v&&on>=0){if(i-on>=320)tones.add(new int[]{on,i});on=-1;}}
  if(tones.size()<2)throw new IllegalArgumentException("周期を推定する点・線が不足しています");double[] lengths=new double[tones.size()];for(int i=0;i<lengths.length;i++)lengths[i]=(tones.get(i)[1]-tones.get(i)[0])/16000.;double cut=OpticalMath.percentile(lengths,.4);double[] shortOn=Arrays.stream(lengths).filter(v->v<=cut).toArray();result.dot=OpticalMath.percentile(shortOn,.5);
  int from=0;for(int i=1;i<=tones.size();i++)if(i==tones.size()||(tones.get(i)[0]-tones.get(i-1)[1])/16000.>2*result.dot){result.ranges.add(new int[]{tones.get(from)[0],tones.get(i-1)[1]});StringBuilder p=new StringBuilder();for(int j=from;j<i;j++)p.append(lengths[j]<2*result.dot?'.':'-');result.patterns.add(p.toString());from=i;}return result;
 }
 public static double[] clip(double[] x,int[] range){int a=Math.max(0,range[0]-80),b=Math.min(x.length,range[1]+80);double[] out=new double[b-a+3040];System.arraycopy(x,a,out,1520,b-a);return out;}
}
