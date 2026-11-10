package jp.local.wabun;

import java.util.*;

/** Progress uses the same pulse schedule as transmission, including all silence. */
public final class SendProgress {
    public interface Listener {void progress(double elapsed,double total);}
    public final String labels;public final double[] starts,ends;public final int[] positions;public final double total;
    public SendProgress(String labels,double unit){
        this.labels=labels;int n=labels.replace(" ","").length();starts=new double[n];ends=new double[n];positions=new int[n];double at=7*unit;int j=0;
        for(int i=0;i<labels.length();i++){
            char c=labels.charAt(i);if(c==' ')continue;String code=MorseCodec.TABLE.get(c);if(code==null)throw new IllegalArgumentException("未対応文字");
            positions[j]=i;starts[j]=at;for(int k=0;k<code.length();k++){at+=unit*(code.charAt(k)=='.'?1:3);if(k+1<code.length())at+=unit;}
            ends[j++]=at;at+=unit*(i+1==labels.length()||labels.charAt(i+1)==' '?7:3);
        }total=at;
    }
    public int completed(double elapsed){int n=0;while(n<ends.length&&elapsed>=ends[n])n++;return n;}
    public int active(double elapsed){for(int i=0;i<starts.length;i++)if(elapsed>=starts[i]&&elapsed<ends[i])return i;return -1;}
}
