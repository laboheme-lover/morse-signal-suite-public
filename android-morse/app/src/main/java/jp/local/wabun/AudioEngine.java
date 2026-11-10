package jp.local.wabun;

import android.content.Context;
import android.media.*;
import android.net.Uri;
import android.os.Build;
import java.io.*;
import java.nio.*;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

public final class AudioEngine {
    public interface Listener {void update(String status,String text);}
    public boolean m3Enabled=false;
    public SendProgress.Listener progress;
    private AudioM3Recognition m3()throws IOException{return new AudioM3Recognition(new AudioM3(context.getAssets().open("audio_m3.bin")),new AudioDsp(context.getAssets().open("audio_filters.bin")));}
    public final AtomicBoolean cancelled=new AtomicBoolean(false);
    private final Context context;private final Listener listener;
    public AudioEngine(Context context,Listener listener){this.context=context;this.listener=listener;}
    public void stop(){cancelled.set(true);}
    private void report(String status,MorseCodec.Decoder d){listener.update(status+"\n要確認符号："+d.uncertain,d.text());}
    public void microphone(double unit,double hz,double minimum) throws Exception {
        if(context.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)!=android.content.pm.PackageManager.PERMISSION_GRANTED)throw new SecurityException("マイクの権限を許可してください。");
        if(m3Enabled){microphoneM3();return;}
        final int rate=16000;
        int minimumBuffer=AudioRecord.getMinBufferSize(rate,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT);
        if(minimumBuffer<=0)throw new IOException("マイクの録音形式に対応していません。");
        AudioRecord record=new AudioRecord(MediaRecorder.AudioSource.MIC,rate,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,Math.max(6400,minimumBuffer*2));
        MorseCodec.Decoder d=new MorseCodec.Decoder(unit);MorseCodec.ToneDetector detector=new MorseCodec.ToneDetector(rate,hz,minimum);
        short[] buffer=new short[640];long update=0;long silentSamples=0;
        try{
            if(record.getState()!=AudioRecord.STATE_INITIALIZED)throw new IOException("マイクを初期化できません。");
            record.startRecording();
            if(record.getRecordingState()!=AudioRecord.RECORDSTATE_RECORDING)throw new IOException("録音を開始できません。");
            while(!cancelled.get()){
                int n=record.read(buffer,0,buffer.length,AudioRecord.READ_NON_BLOCKING);
                if(n<0)throw new IOException("マイク入力エラー："+n);
                for(int i=0;i<n;i++){double v=buffer[i]/32768.0;silentSamples=Math.abs(v)<.0001?silentSamples+1:0;detector.push(v,d);}
                long now=android.os.SystemClock.elapsedRealtime();
                if(now-update>250){
                    String state=String.format(java.util.Locale.JAPAN,"マイク受信中  入力 %.3f / 音程一致 %.0f%%",detector.rms,100*detector.ratio);
                    if(Build.VERSION.SDK_INT>=29){AudioRecordingConfiguration cfg=record.getActiveRecordingConfiguration();if(cfg!=null&&cfg.isClientSilenced())state="通話等によりマイク入力が無音化されています。録音ファイル読込をご利用ください。";}
                    if(silentSamples>rate*3)state+="\n入力音を確認できません。権限・通話・マイクを確認してください。";
                    report(state,d);update=now;
                }
                if(n==0)Thread.sleep(10);
            }
        } finally {try{record.stop();}catch(IllegalStateException ignored){}record.release();d.finish();report("マイク受信を停止しました。",d);}
    }
    public void decodeFile(Uri uri,double unit,double hz,double minimum,double start,double end)throws Exception{
        if(m3Enabled){decodeM3(uri,start,end);return;}
        MediaExtractor extractor=new MediaExtractor();MediaCodec codec=null;
        MorseCodec.Decoder d=new MorseCodec.Decoder(unit);MorseCodec.ToneDetector detector=null;
        try{
            extractor.setDataSource(context,uri,null);int track=-1;
            for(int i=0;i<extractor.getTrackCount();i++)if(extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME).startsWith("audio/")){track=i;break;}
            if(track<0)throw new IOException("音声トラックがありません。");
            extractor.selectTrack(track);MediaFormat format=extractor.getTrackFormat(track);
            codec=MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME));codec.configure(format,null,null,0);codec.start();
            int rate=format.getInteger(MediaFormat.KEY_SAMPLE_RATE),channels=format.getInteger(MediaFormat.KEY_CHANNEL_COUNT),encoding=AudioFormat.ENCODING_PCM_16BIT;
            detector=new MorseCodec.ToneDetector(rate,hz,minimum);boolean inputDone=false,outputDone=false;
            MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();long lastUpdate=0,samples=0,lastOutput=android.os.SystemClock.elapsedRealtime();
            if(start>0)extractor.seekTo((long)(start*1e6),MediaExtractor.SEEK_TO_PREVIOUS_SYNC);
            while(!outputDone&&!cancelled.get()){
                if(!inputDone){int index=codec.dequeueInputBuffer(10000);if(index>=0){ByteBuffer b=codec.getInputBuffer(index);int size=extractor.readSampleData(b,0);if(size<0){codec.queueInputBuffer(index,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inputDone=true;}else{codec.queueInputBuffer(index,0,size,extractor.getSampleTime(),0);extractor.advance();}}}
                int index=codec.dequeueOutputBuffer(info,10000);
                if(index==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED){
                    MediaFormat actual=codec.getOutputFormat();rate=actual.getInteger(MediaFormat.KEY_SAMPLE_RATE);channels=actual.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
                    encoding=actual.containsKey(MediaFormat.KEY_PCM_ENCODING)?actual.getInteger(MediaFormat.KEY_PCM_ENCODING):AudioFormat.ENCODING_PCM_16BIT;
                    if(encoding!=AudioFormat.ENCODING_PCM_16BIT&&encoding!=AudioFormat.ENCODING_PCM_FLOAT)throw new IOException("この音声の復号形式には未対応です。PCM16 WAVをご利用ください。");
                    if(samples>0)throw new IOException("途中で音声形式が変わるファイルには未対応です。");
                    detector=new MorseCodec.ToneDetector(rate,hz,minimum);
                }else if(index>=0){
                    ByteBuffer b=codec.getOutputBuffer(index).order(ByteOrder.LITTLE_ENDIAN);b.position(info.offset);b.limit(info.offset+info.size);
                    int bytes=encoding==AudioFormat.ENCODING_PCM_FLOAT?4:2,frame=0;
                    while(b.remaining()>=bytes*channels){
                        double value=0;for(int c=0;c<channels;c++)value+=encoding==AudioFormat.ENCODING_PCM_FLOAT?b.getFloat():b.getShort()/32768.0;
                        double t=info.presentationTimeUs/1e6+(double)frame++/rate;
                        if(t<start)continue;if(end>0&&t>=end){outputDone=true;break;}
                        detector.push(value/channels,d);samples++;
                        if(samples>(long)rate*1800)throw new IOException("解析上限は30分です。終了位置を指定してください。");
                    }
                    codec.releaseOutputBuffer(index,false);lastOutput=android.os.SystemClock.elapsedRealtime();
                    outputDone|=(info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0;
                    if(lastOutput-lastUpdate>250){report("録音ファイルを解析中："+(samples/rate)+"秒",d);lastUpdate=lastOutput;}
                }
                if(android.os.SystemClock.elapsedRealtime()-lastOutput>15000)throw new IOException("音声の復号が進みません。別の形式で保存してください。");
            }
            if(samples==0&&!cancelled.get())throw new IOException("指定した区間に解析できる音声がありません。");
            d.finish();report(cancelled.get()?"解析を停止しました（途中結果）。":"録音ファイルの解析が完了しました。",d);
        } finally {if(codec!=null){try{codec.stop();}catch(Exception ignored){}codec.release();}extractor.release();}
    }
    private void microphoneM3()throws Exception {
        if(context.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)!=android.content.pm.PackageManager.PERMISSION_GRANTED)throw new SecurityException("マイクの権限を許可してください。");
        AudioM3Recognition recognizer=m3();int min=AudioRecord.getMinBufferSize(16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT);
        if(min<=0)throw new IOException("マイク形式に対応していません。");
        AudioRecord record=new AudioRecord(MediaRecorder.AudioSource.MIC,16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,Math.max(min*4,32000));
        try(AudioM3Live live=new AudioM3Live(recognizer,(state,text)->listener.update(state,text))){
            if(record.getState()!=AudioRecord.STATE_INITIALIZED)throw new IOException("マイクを初期化できません。");record.startRecording();
            if(record.getRecordingState()!=AudioRecord.RECORDSTATE_RECORDING)throw new IOException("マイク録音を開始できません。");
            short[] buffer=new short[640];long silence=0,last=0;
            while(!cancelled.get()){
                int n=record.read(buffer,0,buffer.length,AudioRecord.READ_NON_BLOCKING);if(n<0)throw new IOException("マイク読込エラー "+n);
                if(n==0){Thread.sleep(10);continue;}for(int i=0;i<n;i++)silence=Math.abs(buffer[i])<3?silence+1:0;live.push(buffer,n);
                long now=android.os.SystemClock.elapsedRealtime();if(now-last>1000){last=now;
                    AudioRecordingConfiguration config=Build.VERSION.SDK_INT>=29?record.getActiveRecordingConfiguration():null;
                    if(Build.VERSION.SDK_INT>=29&&config!=null&&config.isClientSilenced())listener.update("通話などによりマイク入力が無音化されています。録音ファイルを利用してください。",null);
                    else if(silence>48000)listener.update("M3：マイクの入力音を確認できません。",null);
                }
            }
        }finally{try{record.stop();}catch(Exception ignored){}record.release();}
    }
    private void decodeM3(Uri uri,double from,double to)throws Exception {
        MediaExtractor extractor=new MediaExtractor();MediaCodec codec=null;java.util.ArrayList<float[]> chunks=new java.util.ArrayList<>();int total=0;
        try{
            extractor.setDataSource(context,uri,null);int track=-1;for(int i=0;i<extractor.getTrackCount();i++)if(extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME).startsWith("audio/")){track=i;break;}
            if(track<0)throw new IOException("音声トラックがありません。");extractor.selectTrack(track);MediaFormat format=extractor.getTrackFormat(track);
            codec=MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME));codec.configure(format,null,null,0);codec.start();
            int rate=format.getInteger(MediaFormat.KEY_SAMPLE_RATE),channels=format.getInteger(MediaFormat.KEY_CHANNEL_COUNT),encoding=AudioFormat.ENCODING_PCM_16BIT;
            if(from>0)extractor.seekTo((long)(from*1e6),MediaExtractor.SEEK_TO_PREVIOUS_SYNC);
            boolean inputDone=false,done=false;MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();long last=android.os.SystemClock.elapsedRealtime(),update=0;
            while(!done&&!cancelled.get()){
                if(!inputDone){int i=codec.dequeueInputBuffer(10000);if(i>=0){ByteBuffer b=codec.getInputBuffer(i);int n=extractor.readSampleData(b,0);if(n<0){codec.queueInputBuffer(i,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inputDone=true;}else{codec.queueInputBuffer(i,0,n,extractor.getSampleTime(),0);extractor.advance();}}}
                int i=codec.dequeueOutputBuffer(info,10000);
                if(i==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED){if(total>0)throw new IOException("途中で音声形式が変化しました。");MediaFormat f=codec.getOutputFormat();rate=f.getInteger(MediaFormat.KEY_SAMPLE_RATE);channels=f.getInteger(MediaFormat.KEY_CHANNEL_COUNT);encoding=f.containsKey(MediaFormat.KEY_PCM_ENCODING)?f.getInteger(MediaFormat.KEY_PCM_ENCODING):AudioFormat.ENCODING_PCM_16BIT;if(encoding!=AudioFormat.ENCODING_PCM_FLOAT&&encoding!=AudioFormat.ENCODING_PCM_16BIT)throw new IOException("PCM16またはFloat音声を利用してください。");}
                else if(i>=0){try{
                    ByteBuffer b=codec.getOutputBuffer(i).order(ByteOrder.LITTLE_ENDIAN);b.position(info.offset);b.limit(info.offset+info.size);int bytes=encoding==AudioFormat.ENCODING_PCM_FLOAT?4:2;float[] chunk=new float[b.remaining()/(bytes*channels)];int n=0,index=0;
                    while(b.remaining()>=bytes*channels){double value=0;for(int c=0;c<channels;c++)value+=encoding==AudioFormat.ENCODING_PCM_FLOAT?b.getFloat():b.getShort()/32768.;double time=info.presentationTimeUs/1e6+(index++)/(double)rate;if(time<from)continue;if(to>0&&time>=to){done=true;break;}if(!Double.isFinite(value))throw new IOException("不正な音声サンプルです。");chunk[n++]=(float)(value/channels);}
                    total+=n;if(total>rate*120L||total>6000000)throw new IOException("M3の録音解析は1回120秒・600万サンプル以内です。開始・終了秒で分けてください。");if(n>0)chunks.add(java.util.Arrays.copyOf(chunk,n));done|=(info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0;last=android.os.SystemClock.elapsedRealtime();
                    if(last-update>500){update=last;listener.update("M3：録音を読込中 "+total/rate+"秒",null);}
                }finally{codec.releaseOutputBuffer(i,false);}}
                if(android.os.SystemClock.elapsedRealtime()-last>15000)throw new IOException("音声の復号が進みません。");
            }
            if(cancelled.get())return;if(total==0)throw new IOException("指定区間に音声がありません。");float[] samples=new float[total];int at=0;for(float[] c:chunks){System.arraycopy(c,0,samples,at,c.length);at+=c.length;}chunks.clear();
            listener.update("M3：文字区切り・RMS包絡・CNN＋双方向GRUを計算中…",null);
            double[] resampled=AudioM3Recognition.resample(samples,rate);AudioM3Recognition r=m3();String text=r.recognize(resampled,cancelled::get);
            if(!cancelled.get())listener.update("M3録音認識が完了しました。要確認 "+r.review+"\n候補："+r.candidates+"\n候補スコアは正解率ではありません。",text);
        }finally{if(codec!=null){try{codec.stop();}catch(Exception ignored){}codec.release();}extractor.release();}
    }
    public void play(List<MorseCodec.Pulse> pulses,double unit,double hz)throws Exception{
        int rate=16000;AudioTrack track=new AudioTrack.Builder().setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build()).setAudioFormat(new AudioFormat.Builder().setSampleRate(rate).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).setEncoding(AudioFormat.ENCODING_PCM_16BIT).build()).setBufferSizeInBytes(Math.max(4096,AudioTrack.getMinBufferSize(rate,AudioFormat.CHANNEL_OUT_MONO,AudioFormat.ENCODING_PCM_16BIT))).setTransferMode(AudioTrack.MODE_STREAM).build();
        try{
            double total=pulses.stream().mapToInt(p->p.units).sum()*unit;
            track.play();short[] buffer=new short[512];long totalWritten=0;
            for(MorseCodec.Pulse p:pulses){int length=(int)Math.round(p.units*unit*rate);
                for(int offset=0;offset<length&&!cancelled.get();){int n=Math.min(buffer.length,length-offset);for(int j=0;j<n;j++)buffer[j]=sample(p.on,offset+j,length,rate,hz);
                    int used=0;while(used<n&&!cancelled.get()){int wrote=track.write(buffer,used,n-used,AudioTrack.WRITE_BLOCKING);if(wrote<=0)throw new IOException("音声出力に失敗しました。");used+=wrote;totalWritten+=wrote;}offset+=n;if(progress!=null)progress.progress(Integer.toUnsignedLong(track.getPlaybackHeadPosition())/(double)rate,total);}
                if(cancelled.get())break;
            }
            while(!cancelled.get()&&Integer.toUnsignedLong(track.getPlaybackHeadPosition())<totalWritten){if(progress!=null)progress.progress(Integer.toUnsignedLong(track.getPlaybackHeadPosition())/(double)rate,total);Thread.sleep(20);}
            if(!cancelled.get()&&progress!=null)progress.progress(total,total);
        }finally{try{track.stop();}catch(Exception ignored){}track.release();}
    }
    private static short sample(boolean on,int i,int n,int rate,double hz){if(!on)return 0;double ramp=Math.min(1,Math.min(i,n-1-i)/(rate*.005));return (short)(8192*ramp*Math.sin(2*Math.PI*hz*i/rate));}
    public void saveWav(Uri uri,List<MorseCodec.Pulse> pulses,double unit,double hz)throws Exception{
        int rate=16000,count=0;for(MorseCodec.Pulse p:pulses)count+=(int)Math.round(p.units*unit*rate);
        try(OutputStream out=context.getContentResolver().openOutputStream(uri,"wt")){
            if(out==null)throw new IOException("保存先を開けません。");
            ByteBuffer h=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);h.put("RIFF".getBytes()).putInt(36+count*2).put("WAVEfmt ".getBytes()).putInt(16).putShort((short)1).putShort((short)1).putInt(rate).putInt(rate*2).putShort((short)2).putShort((short)16).put("data".getBytes()).putInt(count*2);out.write(h.array());
            byte[] buffer=new byte[2048];
            for(MorseCodec.Pulse p:pulses){int n=(int)Math.round(p.units*unit*rate);for(int offset=0;offset<n;){if(cancelled.get())throw new IOException("保存を中断しました。途中のファイルは使用しないでください。");int take=Math.min(n-offset,buffer.length/2);for(int j=0;j<take;j++){short v=sample(p.on,offset+j,n,rate,hz);buffer[j*2]=(byte)v;buffer[j*2+1]=(byte)(v>>8);}out.write(buffer,0,take*2);offset+=take;}}
        }
    }
}
