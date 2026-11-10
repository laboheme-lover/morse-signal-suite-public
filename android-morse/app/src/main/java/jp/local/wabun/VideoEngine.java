package jp.local.wabun;

import android.content.Context;
import android.graphics.*;
import android.media.*;
import android.net.Uri;
import android.os.SystemClock;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

/** Sequential decoded frames and presentation timestamps, not keyframe sampling. */
public final class VideoEngine {
    private final Context context;
    private final OpticalEngine.Listener listener;
    private final AtomicBoolean cancelled=new AtomicBoolean();
    public volatile int threshold=160;
    public LightRegion region=new LightRegion();public boolean cnnEnabled=false,autoTiming=true,previewOnly=false;
    private LightTracker tracker=new LightTracker();
    public VideoEngine(Context context,OpticalEngine.Listener listener){this.context=context;this.listener=listener;}
    public void stop(){cancelled.set(true);}
    public void decodeFile(Uri uri,double unit,double from,double to)throws Exception {
        MediaExtractor extractor=new MediaExtractor();MediaCodec codec=null;
        OpticalSignal signal=new OpticalSignal(unit);MorseCodec.Decoder decoder=signal.decoder;
        OpticalReceiver receiver=cnnEnabled&&!previewOnly?new OpticalReceiver(new OpticalCnn(context.getAssets().open("optical_cnn.bin")),unit,autoTiming):null;
        Bitmap bestPreview=null;double bestContrast=-Double.MAX_VALUE;
        int frames=0;long first=-1,previous=-1,lastUpdate=0;double worst=0;
        try {
            extractor.setDataSource(context,uri,null);int track=-1;
            for(int i=0;i<extractor.getTrackCount();i++)if(extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME).startsWith("video/")){track=i;break;}
            if(track<0)throw new IOException("動画トラックがありません。MP4などの動画を選んでください。");
            extractor.selectTrack(track);MediaFormat format=extractor.getTrackFormat(track);
            int rotation=format.containsKey(MediaFormat.KEY_ROTATION)?format.getInteger(MediaFormat.KEY_ROTATION):0;
            // Apply rotation only to the preview; the central square is rotation invariant.
            format.setInteger(MediaFormat.KEY_ROTATION,0);
            format.setInteger(MediaFormat.KEY_COLOR_FORMAT,MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible);
            codec=MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME));codec.configure(format,null,null,0);codec.start();
            if(from>0)extractor.seekTo((long)(from*1e6),MediaExtractor.SEEK_TO_PREVIOUS_SYNC);
            boolean inputDone=false,done=false;MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();long progress=SystemClock.elapsedRealtime();
            while(!done&&!cancelled.get()){
                if(!inputDone){int index=codec.dequeueInputBuffer(10000);if(index>=0){ByteBuffer b=codec.getInputBuffer(index);int n=extractor.readSampleData(b,0);if(n<0){codec.queueInputBuffer(index,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inputDone=true;}else{codec.queueInputBuffer(index,0,n,extractor.getSampleTime(),0);extractor.advance();}}}
                int index=codec.dequeueOutputBuffer(info,10000);
                if(index>=0){
                    try {
                        double seconds=info.presentationTimeUs/1e6;
                        if(to>0&&seconds>=to)done=true;
                        else if(info.size>0&&(info.flags&MediaCodec.BUFFER_FLAG_CODEC_CONFIG)==0&&seconds>=from){
                            if(first>=0&&info.presentationTimeUs<=previous)throw new IOException("動画の時刻が逆行しています。別形式で保存してください。");
                            if(first<0)first=info.presentationTimeUs;
                            if((info.presentationTimeUs-first)/1e6>1800)throw new IOException("解析上限は30分です。終了位置を指定してください。");
                            if(previous>=0){double gap=(info.presentationTimeUs-previous)/1e6;worst=Math.max(worst,gap);}
                            previous=info.presentationTimeUs;
                            try(Image frame=codec.getOutputImage(index)){
                                if(frame==null)throw new IOException("この動画の画素を取得できません。H.264のMP4で保存し直してください。");
                                boolean full=format.containsKey(MediaFormat.KEY_COLOR_RANGE)&&format.getInteger(MediaFormat.KEY_COLOR_RANGE)==MediaFormat.COLOR_RANGE_FULL;
                                OpticalFrame opticalFrame=new OpticalFrame(frame,rotation,full);
                                if(previewOnly)tracker.update(opticalFrame.grid(),seconds,region);
                                double[] feature=opticalFrame.features(region);double level=feature[0];frames++;
                                if(previewOnly&&feature[0]-feature[2]>bestContrast){bestContrast=feature[0]-feature[2];if(bestPreview!=null)bestPreview.recycle();bestPreview=opticalFrame.preview(region,tracker);}
                                if(!previewOnly){if(receiver!=null)receiver.accept(seconds,feature);else signal.accept(level,threshold,seconds);}
                                long now=SystemClock.elapsedRealtime();
                                if(now-lastUpdate>=200){lastUpdate=now;
                                    listener.update(previewOnly?"光源確認用プレビュー："+tracker.status:(receiver!=null?receiver.state:"ルール方式で動画解析中 "+(int)seconds+"秒"),previewOnly?null:(receiver!=null?receiver.text():decoder.text()));
                                    listener.preview(opticalFrame.preview(region,tracker));listener.candidates(tracker.candidates);
                                }
                                if(previewOnly&&(seconds-from>=30||(seconds-from>=8&&tracker.candidates.length>0)))done=true;
                            }
                        }
                    }finally{codec.releaseOutputBuffer(index,false);}
                    progress=SystemClock.elapsedRealtime();done|=(info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0;
                }
                if(SystemClock.elapsedRealtime()-progress>15000)throw new IOException("動画の復号が進みません。別形式の動画を選んでください。");
            }
            if(frames==0&&!cancelled.get())throw new IOException("指定した区間に解析できる動画フレームがありません。");
            if(previewOnly&&bestPreview!=null&&!cancelled.get()){listener.preview(bestPreview);bestPreview=null;}
            if(previewOnly)listener.update("プレビュー取得完了。光源をタップ・拡縮して確認し、「この光源で受信・解析開始」を押してください。自動候補がない場合も手動指定できます。",null);
            else if(receiver!=null){if(!cancelled.get())receiver.finish();listener.update((cancelled.get()?"動画解析を停止しました。":"CNN動画解析が完了しました。")+"\n"+receiver.state,receiver.text());}
            else {decoder.finish();listener.update((cancelled.get()?"動画解析を停止しました。":"動画解析が完了しました。")+"\n"+frames+"フレーム",decoder.text());}
        } finally {if(bestPreview!=null)bestPreview.recycle();if(codec!=null){try{codec.stop();}catch(Exception ignored){}codec.release();}extractor.release();}
    }
}
