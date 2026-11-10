package jp.local.wabun;

import java.io.*;

/** Exact float32 weight export of the adopted PyTorch CNN. No training on phone.
 * Small fixed network uses CPU loops so no native runtime/ABI dependency is needed.
 * Verified against PyTorch logits by tools/test_optical_cnn.py. */
public final class OpticalCnn {
    public final String[] labels;
    private final float[][] weights=new float[8][];
    public OpticalCnn(InputStream source)throws IOException {
        try(DataInputStream in=new DataInputStream(new BufferedInputStream(source))){
            if(in.readInt()!=0x4f434e31)throw new IOException("光モデルの形式が違います");
            int n=in.readInt();if(n!=65)throw new IOException("光モデルのクラス数が違います");
            labels=new String[n];for(int i=0;i<n;i++)labels[i]=in.readUTF();
            int[] sizes={32*5*5,32,48*32*5,48,128*768,128,65*128,65};
            for(int i=0;i<8;i++){if(in.readInt()!=sizes[i])throw new IOException("モデルの配列サイズが不正です");weights[i]=new float[sizes[i]];for(int j=0;j<sizes[i];j++)weights[i][j]=in.readFloat();}
            if(in.read()!=-1)throw new IOException("モデルの末尾が不正です");
        }
    }
    private static float[][] conv(float[][] x,float[] w,float[] b,int stride){
        int length=(x[0].length-1)/stride+1;float[][] y=new float[b.length][length];
        for(int o=0;o<b.length;o++)for(int t=0;t<length;t++){
            float s=b[o];for(int c=0;c<x.length;c++)for(int k=0;k<5;k++){
                int p=t*stride+k-2;if(p>=0&&p<x[c].length)s+=x[c][p]*w[(o*x.length+c)*5+k];
            }y[o][t]=Math.max(0,s);
        }return y;
    }
    public float[] logits(float[][] x){
        if(x.length!=5)throw new IllegalArgumentException("5 channels required");
        for(float[] c:x){if(c.length!=256)throw new IllegalArgumentException("256 steps required");for(float v:c)if(!Float.isFinite(v))throw new IllegalArgumentException("Nonfinite feature");}
        float[][] y=conv(conv(x,weights[0],weights[1],1),weights[2],weights[3],2);
        float[] flat=new float[768];
        for(int c=0;c<48;c++)for(int p=0;p<16;p++){
            int a=p*y[c].length/16,b=((p+1)*y[c].length+15)/16;float s=0;
            for(int j=a;j<b;j++)s+=y[c][j];flat[c*16+p]=s/(b-a);
        }
        float[] hidden=new float[128],out=new float[65];
        for(int o=0;o<128;o++){float s=weights[5][o];for(int i=0;i<768;i++)s+=flat[i]*weights[4][o*768+i];hidden[o]=Math.max(0,s);}
        for(int o=0;o<65;o++){float s=weights[7][o];for(int i=0;i<128;i++)s+=hidden[i]*weights[6][o*128+i];out[o]=s;}
        return out;
    }
    public float[] probabilities(float[][] x){float[] a=logits(x);float max=-Float.MAX_VALUE;for(float v:a)max=Math.max(max,v);double total=0;for(int i=0;i<a.length;i++){a[i]=(float)Math.exp(a[i]-max);total+=a[i];}for(int i=0;i<a.length;i++)a[i]/=total;return a;}
}
