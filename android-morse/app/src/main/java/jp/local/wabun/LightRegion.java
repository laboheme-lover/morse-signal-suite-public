package jp.local.wabun;

/** Normalized coordinates in the displayed, rotation-corrected image. */
public final class LightRegion {
    public volatile double x=.5,y=.5,width=.08,aspect=1;
    public volatile boolean automatic=true,confirmed=false,tracking=true;
    public volatile int revision=0;
    public synchronized void set(double cx,double cy,double size){
        width=Math.max(.015,Math.min(.3,size));double margin=width*1.6;
        x=Math.max(margin,Math.min(1-margin,cx));double ym=Math.min(.49,margin*aspect);y=Math.max(ym,Math.min(1-ym,cy));revision++;
    }
    public synchronized void manual(double cx,double cy,double size){automatic=false;confirmed=false;set(cx,cy,size);}
    public synchronized void reset(){confirmed=false;automatic=true;revision++;}
}
