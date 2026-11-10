package jp.local.wabun;

import java.util.*;

/** PC feature normalization and timing estimator, independent of Android. */
public final class OpticalMath {
    public static double percentile(double[] x,double q){double[] a=x.clone();Arrays.sort(a);double p=(a.length-1)*q;int i=(int)p;return a[i]+(a[Math.min(i+1,a.length-1)]-a[i])*(p-i);}
    public static double[] levels(double[][] f){
        double[] signal=new double[f.length];for(int i=0;i<f.length;i++)signal[i]=f[i][0]-f[i][2];
        double low=percentile(signal,.05),high=percentile(signal,.95);
        if(high-low<5){low=percentile(signal,.01);high=percentile(signal,.99);}
        if(high-low<5)throw new IllegalArgumentException("光の変化が小さいため保留");
        for(int k=0;k<15;k++){
            double[] a=new double[signal.length],b=new double[signal.length];int na=0,nb=0;
            for(double v:signal)if(v<=(low+high)/2)a[na++]=v;else b[nb++]=v;
            if(na<2||nb<2)throw new IllegalArgumentException("点灯と消灯を分離できません");
            low=percentile(Arrays.copyOf(a,na),.5);high=percentile(Arrays.copyOf(b,nb),.5);
        }return new double[]{low,high};
    }
    public static double medianDelta(double[] t){double[] d=new double[t.length-1];for(int i=0;i<d.length;i++){d[i]=t[i+1]-t[i];if(d[i]<=0||!Double.isFinite(d[i]))throw new IllegalArgumentException("フレーム時刻が不正です");}return percentile(d,.5);}
    public static double estimate(double[] t,double[][] f){
        if(t.length<10)throw new IllegalArgumentException("点滅を観測中（周期未確定）");
        double dt=medianDelta(t);double[] lv=levels(f);boolean[] on=new boolean[t.length],filtered=new boolean[t.length];
        for(int i=0;i<t.length;i++)on[i]=f[i][0]-f[i][2]>(lv[0]+lv[1])/2;
        for(int i=0;i<t.length;i++)filtered[i]=(on[Math.max(0,i-1)]?1:0)+(on[i]?1:0)+(on[Math.min(t.length-1,i+1)]?1:0)>=2;
        List<Double> a=new ArrayList<>(),b=new ArrayList<>();int first=0;
        for(int i=1;i<=t.length;i++)if(i==t.length||filtered[i]!=filtered[first]){
            double duration=(i==t.length?t[i-1]+dt:t[i])-t[first];
            if(filtered[first])a.add(duration);else if(first>0&&i<t.length)b.add(duration);first=i;
        }
        if(a.size()<6||b.size()<5)throw new IllegalArgumentException("点滅を観測中（6回以上の点灯が必要）");
        double best=Double.POSITIVE_INFINITY,unit=0,start=Math.max(.1,2.5*dt);
        List<Double> units=new ArrayList<>(),losses=new ArrayList<>();
        for(int k=0;start+k*.001<=1.0001;k++){
            double u=start+k*.001,loss=(loss(a,u,new int[]{1,3})+loss(b,u,new int[]{1,3,7}))/2;
            units.add(u);losses.add(loss);if(loss<best){best=loss;unit=u;}
        }
        double alt=Double.POSITIVE_INFINITY;for(int i=0;i<units.size();i++)if(Math.abs(units.get(i)-unit)>.2*unit)alt=Math.min(alt,losses.get(i));
        double tol=Math.max(.3,2*dt/unit);int fit=0,dots=0,shorts=0;
        for(double d:a){if(residual(d/unit,new int[]{1,3})<=tol)fit++;if(Math.abs(d/unit-1)<=tol)dots++;}
        for(double d:b){if(residual(d/unit,new int[]{1,3,7})<=tol)fit++;if(Math.abs(d/unit-1)<=tol)shorts++;}
        if(best>.35||fit/(double)(a.size()+b.size())<.8||(dots==0&&shorts==0)||alt-best<.08)throw new IllegalArgumentException("周期の整合性不足：手動設定または光源を確認");
        for(int i=1;i<t.length;i++)if(t[i]-t[i-1]>unit*.4)throw new IllegalArgumentException("フレーム欠落が大きいため保留");
        return unit;
    }
    private static double residual(double x,int[] choices){double r=Double.POSITIVE_INFINITY;for(int v:choices)r=Math.min(r,Math.abs(x-v));return r;}
    private static double loss(List<Double> a,double u,int[] choices){double s=0;for(double v:a)s+=Math.min(2,residual(v/u,choices));return s/a.size();}
    public static float[][] tensor(double[][] f,double duration){
        int n=f.length;double[][] channels=new double[5][n];
        for(int c=0;c<2;c++){
            double[] v=new double[n];for(int i=0;i<n;i++)v[i]=f[i][c]-f[i][2];
            double low=percentile(v,.05),span=Math.max(5,percentile(v,.95)-low);
            for(int i=0;i<n;i++)channels[c][i]=Math.max(-1,Math.min(2,(v[i]-low)/span));
        }
        for(int i=0;i<n;i++){channels[2][i]=f[i][2]/255;channels[3][i]=f[i][0]/255;channels[4][i]=duration/12;}
        float[][] x=new float[5][256];for(int j=0;j<256;j++){double p=j*(n-1)/255.;int a=(int)p,b=Math.min(n-1,a+1);for(int c=0;c<5;c++)x[c][j]=(float)(channels[c][a]+(channels[c][b]-channels[c][a])*(p-a));}return x;
    }
    public static float[][] input(double[] times,double[][] f,double start,double end,double unit){
        double scale=.3/unit,left=Math.max(times[0],start-.5/scale),right=Math.min(times[times.length-1],end+.5/scale);
        int n=(int)Math.ceil((right-left)*scale*30-1e-9);if(n<2||n>3600)throw new IllegalArgumentException("一文字の長さが範囲外です");
        double[][] arr=new double[n][4];int at=0;
        for(int i=0;i<n;i++){double t=left+i/(30*scale);while(at+1<times.length&&times[at+1]<=t)at++;int b=Math.min(times.length-1,at+1);double r=b==at?0:(t-times[at])/(times[b]-times[at]);for(int c=0;c<4;c++)arr[i][c]=f[at][c]+(f[b][c]-f[at][c])*r;}
        return tensor(arr,n/30.);
    }
}
