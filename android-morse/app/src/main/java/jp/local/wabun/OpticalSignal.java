package jp.local.wabun;

/** Frame brightness + actual timestamps to Wabun; independent of Android codecs. */
public final class OpticalSignal {
    public final MorseCodec.Decoder decoder;
    private final double unit;
    private double previous=-1,first=-1;
    private boolean on;
    public OpticalSignal(double unit){this.unit=unit;decoder=new MorseCodec.Decoder(unit);}
    public void accept(double brightness,int threshold,double seconds){
        if(!Double.isFinite(seconds)||seconds<0||!Double.isFinite(brightness))throw new IllegalArgumentException("動画の時刻・明るさが不正です。");
        if(previous>=0&&seconds<previous)throw new IllegalArgumentException("動画の時刻が逆行しています。");
        if(first<0)first=seconds;
        if(previous>=0&&seconds-previous>unit*.65)decoder.discontinuity();
        previous=seconds;
        on=brightness>(on?threshold-10:threshold+10);
        decoder.accept(on,seconds-first);
    }
}
