package jp.local.wabun;
import java.io.*;
import java.util.*;

/** Fixed adopted M3: three Conv1d branches -> Conv1d -> bidirectional GRU -> 65 logits. */
public final class AudioM3 {
 public final String[] labels=new String[65];private final float[][] w=new float[18][];
 public final double[][] envelopeFilter=new double[4][6];
 public AudioM3(InputStream source)throws IOException{
  try(DataInputStream in=new DataInputStream(new BufferedInputStream(source))){
   if(in.readInt()!=0x4d330001)throw new IOException("M3モデル形式が違います");
   for(int i=0;i<65;i++)labels[i]=in.readUTF();
   int[] sizes={24,8,40,8,72,8,5760,48,9216,12288,192,192,9216,12288,192,192,8320,65};
   for(int j=0;j<w.length;j++){if(in.readInt()!=sizes[j])throw new IOException("M3モデル配列が不正です");w[j]=new float[sizes[j]];for(int i=0;i<w[j].length;i++)w[j][i]=in.readFloat();}
   for(double[] s:envelopeFilter)for(int i=0;i<6;i++)s[i]=in.readDouble();
  }
 }
 private static float sigmoid(float x){return (float)(1/(1+Math.exp(-x)));}
 public float[] logits(float[] input){
  int n=input.length;if(n<1||n>2000)throw new IllegalArgumentException("一文字の長さがM3上限を超えました");
  for(float v:input)if(!Float.isFinite(v))throw new IllegalArgumentException("不正な包絡");
  float[][] a=new float[24][n];int[] kernels={3,5,9};
  for(int b=0;b<3;b++)for(int c=0;c<8;c++)for(int t=0;t<n;t++){
   int k=kernels[b];float sum=w[b*2+1][c];for(int j=0;j<k;j++){int p=t+j-k/2;if(p>=0&&p<n)sum+=input[p]*w[b*2][c*k+j];}a[b*8+c][t]=Math.max(0,sum);
  }
  int steps=(n+1)/2;float[][] sequence=new float[steps][48];
  for(int t=0;t<steps;t++)for(int c=0;c<48;c++){float sum=w[7][c];for(int j=0;j<24;j++)for(int k=0;k<5;k++){int p=2*t+k-2;if(p>=0&&p<n)sum+=a[j][p]*w[6][(c*24+j)*5+k];}sequence[t][c]=Math.max(0,sum);}
  float[] state=new float[128];
  for(int direction=0;direction<2;direction++){
   float[] h=new float[64];int base=8+direction*4;
   for(int step=0;step<steps;step++){
    float[] x=sequence[direction==0?step:steps-1-step],ih=new float[192],hh=new float[192];
    for(int g=0;g<192;g++){float v=w[base+2][g],u=w[base+3][g];for(int i=0;i<48;i++)v+=w[base][g*48+i]*x[i];for(int i=0;i<64;i++)u+=w[base+1][g*64+i]*h[i];ih[g]=v;hh[g]=u;}
    for(int i=0;i<64;i++){float r=sigmoid(ih[i]+hh[i]),z=sigmoid(ih[64+i]+hh[64+i]);float candidate=(float)Math.tanh(ih[128+i]+r*hh[128+i]);h[i]=(1-z)*candidate+z*h[i];}
   }System.arraycopy(h,0,state,64*direction,64);
  }
  float[] logits=new float[65];for(int c=0;c<65;c++){float s=w[17][c];for(int j=0;j<128;j++)s+=w[16][c*128+j]*state[j];logits[c]=s;}return logits;
 }
 public float[] probabilities(float[] x){float[] p=logits(x);float max=-Float.MAX_VALUE;for(float v:p)max=Math.max(max,v);double sum=0;for(int i=0;i<65;i++){p[i]=(float)Math.exp(p[i]-max);sum+=p[i];}for(int i=0;i<65;i++)p[i]/=sum;return p;}
}
