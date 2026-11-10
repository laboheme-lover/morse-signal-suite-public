package jp.local.wabun;

import android.content.Context;
import android.graphics.*;
import android.hardware.camera2.*;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.media.Image;
import android.media.ImageReader;
import android.os.*;
import android.util.Size;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

public final class OpticalEngine {
    public interface Listener {void update(String status,String text);void preview(Bitmap bitmap);void finished(String status,String text);default void candidates(double[][] values){}}
    public SendProgress.Listener progress;
    public LightRegion region=new LightRegion();public boolean cnnEnabled=false,autoTiming=true;
    private OpticalReceiver receiver;private LightTracker tracker=new LightTracker();
    public final AtomicBoolean cancelled=new AtomicBoolean(false);
    public volatile int threshold=160;
    private final Context context;private String finishMessage="光の受信を停止しました。";private final CameraManager manager;private final Listener listener;
    private HandlerThread thread;private Handler handler;private CameraDevice camera;private CameraCaptureSession session;private ImageReader reader;
    private String torchId;private MorseCodec.Decoder decoder;
    public OpticalEngine(Context context,Listener listener){this.context=context;manager=(CameraManager)context.getSystemService(Context.CAMERA_SERVICE);this.listener=listener;}
    public void stop(){cancelled.set(true);if(handler!=null)handler.post(this::closeCamera);}
    private void closeCamera(){
        if(session!=null){session.close();session=null;}if(camera!=null){camera.close();camera=null;}if(reader!=null){reader.close();reader=null;}
        if(decoder!=null){decoder.finish();if(receiver!=null){receiver.finish();listener.finished(finishMessage+"\n"+receiver.state,receiver.text());}else listener.finished(finishMessage,decoder.text());decoder=null;}
        if(thread!=null){thread.quitSafely();thread=null;}
    }
    public void transmit(List<MorseCodec.Pulse> pulses,double unit)throws Exception{
        for(String id:manager.getCameraIdList())if(Boolean.TRUE.equals(manager.getCameraCharacteristics(id).get(CameraCharacteristics.FLASH_INFO_AVAILABLE))){torchId=id;break;}
        if(torchId==null)throw new IOException("この端末には利用できるライトがありません。");
        long deadline=System.nanoTime(),began=deadline;double maxDelay=0;double total=pulses.stream().mapToInt(p->p.units).sum()*unit;
        try{
            for(MorseCodec.Pulse p:pulses){
                if(cancelled.get())break;
                double delay=(System.nanoTime()-deadline)/1e9;maxDelay=Math.max(maxDelay,delay);
                if(delay>unit*.30)throw new IOException("ライトの切替が遅れました。短点時間を長くして再送してください。");
                manager.setTorchMode(torchId,p.on);deadline+=(long)(unit*p.units*1e9);
                while(!cancelled.get()){if(progress!=null)progress.progress(Math.min(total,(System.nanoTime()-began)/1e9),total);long remain=deadline-System.nanoTime();if(remain<=0)break;Thread.sleep(Math.min(20,Math.max(1,remain/1000000)));}
            }
            if(!cancelled.get()&&progress!=null)progress.progress(total,total);
            listener.update(cancelled.get()?"光の送信を停止しました。":String.format(Locale.JAPAN,"光の送信が完了しました。制御遅延の最大値 %.0f ms（実際の点灯時刻は未測定）",maxDelay*1000),null);
        }finally{manager.setTorchMode(torchId,false);}
    }
    public void receive(double unit)throws Exception{
        if(context.checkSelfPermission(android.Manifest.permission.CAMERA)!=android.content.pm.PackageManager.PERMISSION_GRANTED)throw new SecurityException("カメラの権限を許可してください。");
        String id=null;
        for(String candidate:manager.getCameraIdList())if(Objects.equals(manager.getCameraCharacteristics(candidate).get(CameraCharacteristics.LENS_FACING),CameraCharacteristics.LENS_FACING_BACK)){id=candidate;break;}
        if(id==null)throw new IOException("背面カメラを利用できません。");
        CameraCharacteristics characteristics=manager.getCameraCharacteristics(id);
        StreamConfigurationMap map=characteristics.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
        if(map==null)throw new IOException("カメラの画像形式を取得できません。");
        Size[] sizes=map.getOutputSizes(ImageFormat.YUV_420_888);if(sizes==null||sizes.length==0)throw new IOException("カメラの輝度取得に対応していません。");
        Size size=Arrays.stream(sizes).min(Comparator.comparingLong(x->Math.abs((long)x.getWidth()*x.getHeight()-640*480))).get();
        decoder=new MorseCodec.Decoder(unit);if(cnnEnabled)receiver=new OpticalReceiver(new OpticalCnn(context.getAssets().open("optical_cnn.bin")),unit,autoTiming);thread=new HandlerThread("WabunCamera");thread.start();handler=new Handler(thread.getLooper());
        reader=ImageReader.newInstance(size.getWidth(),size.getHeight(),ImageFormat.YUV_420_888,3);
        final long[] previous={0},start={0},lastPreview={0};final boolean[] on={false},wasConfirmed={false};final double[] worstGap={0};
        reader.setOnImageAvailableListener(r->{
            if(cancelled.get())return;
            try(Image image=r.acquireLatestImage()){
                if(image==null||decoder==null)return;
                long stamp=image.getTimestamp();if(start[0]==0)start[0]=stamp;
                double gap=previous[0]==0?0:(stamp-previous[0])/1e9;previous[0]=stamp;worstGap[0]=Math.max(worstGap[0],gap);
                if(gap>unit*.65)decoder.discontinuity();
                Integer orientation=characteristics.get(CameraCharacteristics.SENSOR_ORIENTATION);
                OpticalFrame frame=new OpticalFrame(image,orientation==null?0:orientation,false);
                tracker.update(frame.grid(),stamp/1e9,region);
                double[] feature=frame.features(region);double brightness=feature[0];
                if(region.confirmed&&!wasConfirmed[0]){decoder=new MorseCodec.Decoder(unit);if(cnnEnabled)receiver=new OpticalReceiver(new OpticalCnn(context.getAssets().open("optical_cnn.bin")),unit,autoTiming);start[0]=stamp;}
                wasConfirmed[0]=region.confirmed;
                if(region.confirmed){
                    if(cnnEnabled)receiver.accept(stamp/1e9,feature);
                    else {on[0]=brightness>(on[0]?threshold-10:threshold+10);decoder.accept(on[0],(stamp-start[0])/1e9);}
                }
                if(stamp-lastPreview[0]>200000000L){
                    lastPreview[0]=stamp;
                    listener.update(region.confirmed?(cnnEnabled?receiver.state:"ルール受信中 明るさ "+(int)brightness):"光源を確認し、受信開始を押してください。\n"+tracker.status,region.confirmed?(cnnEnabled?receiver.text():decoder.text()):null);
                    listener.preview(frame.preview(region,tracker));listener.candidates(tracker.candidates);
                }
            }catch(Exception e){finishMessage="カメラ解析エラー："+e.getMessage();cancelled.set(true);closeCamera();}
        },handler);
        try{
            manager.openCamera(id,new CameraDevice.StateCallback(){
                @Override public void onOpened(CameraDevice device){
                    if(cancelled.get()){device.close();closeCamera();return;}camera=device;
                    try{device.createCaptureSession(Collections.singletonList(reader.getSurface()),new CameraCaptureSession.StateCallback(){
                        @Override public void onConfigured(CameraCaptureSession configured){
                            if(cancelled.get()){configured.close();closeCamera();return;}session=configured;
                            try{CaptureRequest.Builder request=camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);request.addTarget(reader.getSurface());request.set(CaptureRequest.CONTROL_MODE,CaptureRequest.CONTROL_MODE_AUTO);configured.setRepeatingRequest(request.build(),null,handler);}catch(Exception e){fail(e.getMessage());}
                        }
                        @Override public void onConfigureFailed(CameraCaptureSession failed){fail("カメラの撮影設定に失敗しました。");}
                    },handler);}catch(Exception e){fail(e.getMessage());}
                }
                @Override public void onDisconnected(CameraDevice device){device.close();fail("カメラが切断されました。");}
                @Override public void onError(CameraDevice device,int error){device.close();fail("カメラを使用できません："+error);}
                private void fail(String message){finishMessage=message;cancelled.set(true);closeCamera();}
            },handler);
        }catch(Exception e){finishMessage="カメラを開始できません："+e.getMessage();closeCamera();throw e;}
    }
}
