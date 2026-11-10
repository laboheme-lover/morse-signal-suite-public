package jp.local.wabun;

import android.app.Instrumentation;
import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.widget.RadioButton;
import android.graphics.Bitmap;
import java.io.*;
import java.nio.charset.StandardCharsets;
import org.json.*;

/** File decoding integration tests. Never opens microphone, camera or phone calls. */
public final class DeviceSmokeTest extends Instrumentation {
    @Override public void onCreate(Bundle arguments) {super.onCreate(arguments);start();}
    @Override public void onStart() {
        StringBuilder report=new StringBuilder();Activity activity=null;int passed=0;
        try {
            Intent intent=new Intent(getTargetContext(), MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            activity=startActivitySync(intent);waitForIdleSync();
            if(activity==null)throw new AssertionError("Activity did not start");
            report.append("PASS Activity startup\n");passed++;
            Activity screen=activity;
            runOnMainSync(()->{
                View root=screen.getWindow().getDecorView();
                if(root.findViewWithTag("send-page").getVisibility()!=View.VISIBLE)throw new AssertionError("send tab");
                clickTab(root,"受信");
                if(root.findViewWithTag("receive-page").getVisibility()!=View.VISIBLE||root.findViewWithTag("send-page").getVisibility()!=View.GONE)throw new AssertionError("receive tab");
                clickTab(root,"送信");
                if(root.findViewWithTag("send-page").getVisibility()!=View.VISIBLE)throw new AssertionError("return tab");
            });report.append("PASS tab switching\n");passed++;
            String symbols=MorseCodec.normalize("（コーヒー、パン）。");
            MorseCodec.Decoder symbolDecoder=new MorseCodec.Decoder(.12);double t=0;
            for(MorseCodec.Pulse pulse:MorseCodec.encode(symbols)){symbolDecoder.accept(pulse.on,t);t+=pulse.units*.12;}
            symbolDecoder.accept(false,t);symbolDecoder.finish();
            if(!"（こーひー、ぱん）」".equals(symbolDecoder.text()))throw new AssertionError("Wabun symbols roundtrip: "+symbolDecoder.text());
            report.append("PASS Wabun symbols pulse roundtrip\n");passed++;
            String symbolText=TextInput.read(new ByteArrayInputStream("（コーヒー、パン）」".getBytes(StandardCharsets.UTF_8)));
            if(!"(こーひー、ぱん)」".equals(symbolText))throw new AssertionError("symbol text import");
            report.append("PASS Wabun symbols text import\n");passed++;
            String displayName=InputFileName.read(getTargetContext().getContentResolver(),Uri.fromFile(new File(getTargetContext().getCacheDir(),"和文 練習.mp4")));
            if(!"和文 練習.mp4".equals(displayName))throw new AssertionError("filename fallback");
            if(!"（ファイル名を取得できません）".equals(InputFileName.read(getTargetContext().getContentResolver(),Uri.parse("content://jp.local.wabun.missing/opaque/123"))))throw new AssertionError("filename unavailable");
            report.append("PASS filename fallback and unavailable name\n");passed++;
            runOnMainSync(()->{
                View root=screen.getWindow().getDecorView();
                for(String tag:new String[]{"text-file-name","audio-file-name","video-file-name"}){
                    android.widget.TextView label=root.findViewWithTag(tag);
                    if(label==null)throw new AssertionError("missing filename label "+tag);
                    String before=label.getText().toString();
                    ((MainActivity)screen).onActivityResult(13,Activity.RESULT_CANCELED,new Intent().setData(Uri.parse("file:///unused.txt")));
                    if(!before.equals(label.getText().toString()))throw new AssertionError("cancel changed filename");
                }
            });report.append("PASS filename labels and picker cancel\n");passed++;
            passed+=checkTextImport((MainActivity)screen,report);
            byte[] manifest;
            try(InputStream in=getContext().getAssets().open("expected.json");ByteArrayOutputStream out=new ByteArrayOutputStream()) {
                byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))>=0)out.write(buffer,0,n);manifest=out.toByteArray();
            }
            JSONArray cases=new JSONArray(new String(manifest,StandardCharsets.UTF_8));
            for(int i=0;i<cases.length();i++) {
                JSONObject item=cases.getJSONObject(i);String name=item.getString("file");
                File fixture=new File(getTargetContext().getCacheDir(),name);
                try(InputStream in=getContext().getAssets().open(name);OutputStream out=new FileOutputStream(fixture)) {
                    byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))>=0)out.write(buffer,0,n);
                }
                try {
                    final String[] actual={null};
                    AudioEngine engine=new AudioEngine(getTargetContext(),(status,text)->{if(text!=null)actual[0]=text;});
                    engine.decodeFile(Uri.fromFile(fixture),item.getDouble("dot_ms")/1000,item.getDouble("frequency_hz"),.003,0,0);
                    String expected=item.getString("expected");
                    if(!expected.equals(actual[0]))throw new AssertionError(name+" expected="+expected+" actual="+actual[0]);
                    report.append("PASS ").append(name).append(" -> ").append(actual[0]).append('\n');passed++;
                } finally {fixture.delete();}
            }
            for(String name:new String[]{"light_30fps.mp4","light_15fps.mp4"}){
                File fixture=new File(getTargetContext().getCacheDir(),name);
                try(InputStream in=getContext().getAssets().open(name);OutputStream out=new FileOutputStream(fixture)){byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);}
                try{
                    final String[] text={null};
                    OpticalEngine.Listener listener=new OpticalEngine.Listener(){public void update(String s,String t){text[0]=t;}public void finished(String s,String t){}public void preview(Bitmap b){b.recycle();}};
                    VideoEngine video=new VideoEngine(getTargetContext(),listener);video.decodeFile(Uri.fromFile(fixture),.6,0,0);
                    if(!"がら".equals(text[0]))throw new AssertionError(name+" actual="+text[0]);
                    report.append("PASS video ").append(name).append(" -> ").append(text[0]).append('\n');passed++;
                    video=new VideoEngine(getTargetContext(),listener);video.decodeFile(Uri.fromFile(fixture),.6,1,0);
                    if(!"がら".equals(text[0]))throw new AssertionError("seek actual="+text[0]);
                    report.append("PASS video seek ").append(name).append('\n');passed++;
                    video=new VideoEngine(getTargetContext(),listener);video.stop();video.decodeFile(Uri.fromFile(fixture),.6,0,0);
                    if(!"".equals(text[0]))throw new AssertionError("cancel");passed++;
                    boolean rejected=false;try{new VideoEngine(getTargetContext(),listener).decodeFile(Uri.fromFile(fixture),.6,1000,1001);}catch(IOException expected){rejected=true;}
                    if(!rejected)throw new AssertionError("empty interval");passed++;
                }finally{fixture.delete();}
            }
            File cnnVideo=new File(getTargetContext().getCacheDir(),"cnn_offcenter.mp4");
            try(InputStream in=getContext().getAssets().open("cnn_offcenter.mp4");OutputStream out=new FileOutputStream(cnnVideo)){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);}
            final String[] cnnText={null};final int[] previews={0};
            OpticalEngine.Listener cnnListener=new OpticalEngine.Listener(){public void update(String s,String t){if(t!=null)cnnText[0]=t;}public void finished(String s,String t){}public void preview(Bitmap b){previews[0]++;b.recycle();}};
            VideoEngine cnnVideoEngine=new VideoEngine(getTargetContext(),cnnListener);cnnVideoEngine.cnnEnabled=true;cnnVideoEngine.region.x=.7;cnnVideoEngine.region.y=.5;cnnVideoEngine.region.width=.0625;cnnVideoEngine.decodeFile(Uri.fromFile(cnnVideo),.3,0,0);
            if(!"いろはにほへ".equals(cnnText[0]))throw new AssertionError("Off-center CNN video: "+cnnText[0]);
            report.append("PASS off-center decoded video -> CNN six characters with automatic timing\n");passed++;
            VideoEngine previewEngine=new VideoEngine(getTargetContext(),cnnListener);previewEngine.previewOnly=true;previewEngine.decodeFile(Uri.fromFile(cnnVideo),.3,0,0);
            if(previews[0]==0||previewEngine.region.confirmed)throw new AssertionError("Preview confirmation gating");
            report.append("PASS video preview waits for confirmation\n");passed++;cnnVideo.delete();
            OpticalCnn cnn=new OpticalCnn(getTargetContext().getAssets().open("optical_cnn.bin"));
            long began=System.nanoTime();double maxDiff=0;
            try(DataInputStream in=new DataInputStream(new BufferedInputStream(getContext().getAssets().open("optical_cnn_fixture.bin")))){
                int n=in.readInt();for(int k=0;k<n;k++){
                    float[][] x=new float[5][256];for(float[] c:x)for(int j=0;j<256;j++)c[j]=in.readFloat();float[] actual=cnn.logits(x);int a=0,b=0;float best=-Float.MAX_VALUE;
                    for(int j=0;j<65;j++){float expected=in.readFloat();maxDiff=Math.max(maxDiff,Math.abs(expected-actual[j]));if(actual[j]>actual[a])a=j;if(expected>best){best=expected;b=j;}}
                    if(a!=b)throw new AssertionError("Device CNN argmax "+k);
                }
                if(maxDiff>.001)throw new AssertionError("Device CNN logits "+maxDiff);
                report.append("PASS device CNN 130 vectors maxDiff=").append(maxDiff).append(" meanMillis=").append((System.nanoTime()-began)/1e6/n).append('\n');passed++;
            }
            runOnMainSync(()->{
                try{
                    View root=screen.getWindow().getDecorView();if(root.findViewWithTag("light-preview")==null||root.findViewWithTag("send-progress")==null)throw new AssertionError("new UI missing");
                    java.lang.reflect.Method prepare=MainActivity.class.getDeclaredMethod("prepareSend",String.class,double.class);prepare.setAccessible(true);prepare.invoke(screen,"イロハ",.3);
                    java.lang.reflect.Field generation=MainActivity.class.getDeclaredField("generation");generation.setAccessible(true);
                    java.lang.reflect.Method update=MainActivity.class.getDeclaredMethod("updateSend",int.class,double.class,double.class);update.setAccessible(true);update.invoke(screen,generation.getInt(screen),3.,new SendProgress("イロハ",.3).total);
                }catch(ReflectiveOperationException e){throw new AssertionError(e);}
            });waitForIdleSync();
            report.append("PASS new optical controls and send progress UI (no physical transmission)\n");passed++;
            AudioM3 audioModel=new AudioM3(getTargetContext().getAssets().open("audio_m3.bin"));
            try(DataInputStream in=new DataInputStream(new BufferedInputStream(getContext().getAssets().open("audio_m3_fixture.bin")))){
                int audioVectorCount=in.readInt();double worst=0;
                for(int k=0;k<audioVectorCount;k++){float[] x=new float[in.readInt()];for(int i=0;i<x.length;i++)x[i]=in.readFloat();float[] y=audioModel.logits(x);int a=0,b=0;float best=-Float.MAX_VALUE;for(int i=0;i<65;i++){float v=in.readFloat();worst=Math.max(worst,Math.abs(v-y[i]));if(y[i]>y[a])a=i;if(v>best){best=v;b=i;}}if(a!=b)throw new AssertionError("Audio M3 device argmax");}
                if(worst>.001)throw new AssertionError("Audio M3 device logit delta");report.append("PASS device M3 65 variable-length vectors\n");passed++;
            }
            JSONArray audioCases;
            try(InputStream in=getContext().getAssets().open("audio_m3_expected.json")){ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] block=new byte[8192];int n;while((n=in.read(block))!=-1)bytes.write(block,0,n);audioCases=new JSONArray(bytes.toString("UTF-8"));}
            for(int i=0;i<audioCases.length();i++){
                JSONObject item=audioCases.getJSONObject(i);File file=new File(getTargetContext().getCacheDir(),"m3_"+item.getString("file"));
                try(InputStream in=getContext().getAssets().open(item.getString("file"));OutputStream out=new FileOutputStream(file)){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);}
                final String[] actual={""};AudioEngine engine=new AudioEngine(getTargetContext(),(state,text)->{if(text!=null)actual[0]=text;});engine.m3Enabled=true;engine.decodeFile(Uri.fromFile(file),.12,700,.003,0,0);
                if(!MorseCodec.hiragana(item.getString("expected")).equals(actual[0]))throw new AssertionError("M3 decoded file "+i+" "+actual[0]);file.delete();report.append("PASS decoded file through M3 ").append(i).append('\n');passed++;
            }
            report.append("WABUN_SMOKE_PASS ").append(passed).append(" checks\n");
            Bundle results=new Bundle();results.putString("stream",report.toString());finish(Activity.RESULT_OK,results);
        } catch(Throwable error) {
            report.append("WABUN_SMOKE_FAIL ").append(error.toString()).append('\n');
            Bundle results=new Bundle();results.putString("stream",report.toString());finish(Activity.RESULT_CANCELED,results);
        }
    }
    private static boolean clickTab(View v,String text){
        if(v instanceof RadioButton&&text.contentEquals(((RadioButton)v).getText())){v.performClick();return true;}
        if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int i=0;i<g.getChildCount();i++)if(clickTab(g.getChildAt(i),text))return true;}
        return false;
    }
    private int checkTextImport(MainActivity screen,StringBuilder report)throws Exception{
        final android.widget.EditText[] editor={null};final String[] original={null};
        runOnMainSync(()->{editor[0]=screen.getWindow().getDecorView().findViewWithTag("send-input");original[0]=editor[0].getText().toString();});
        int checks=0;
        try{
            String[] texts={"コーヒー、パン。\n（123）","ガッコウ","漢字ABCをなおす","あ".repeat(301)};
            String[] expected={"こーひー、ぱん。\n(123)","がっこう","□□□□□をなおす","あ".repeat(301)};
            for(int i=0;i<texts.length;i++){
                byte[] bytes=texts[i].getBytes(i==1?java.nio.charset.Charset.forName("windows-31j"):StandardCharsets.UTF_8);
                importFixture(screen,bytes);
                final String[] actual={null};runOnMainSync(()->actual[0]=editor[0].getText().toString());
                if(!expected[i].equals(actual[0]))throw new AssertionError("text not displayed case "+i+": "+actual[0]);
                report.append("PASS file picker result displays editor case ").append(i).append('\n');checks++;
            }
            importFixture(screen,new byte[0]);
            runOnMainSync(()->{
                if(!expected[3].equals(editor[0].getText().toString()))throw new AssertionError("failed import erased editor");
                screen.onActivityResult(13,Activity.RESULT_CANCELED,null);
                if(!expected[3].equals(editor[0].getText().toString()))throw new AssertionError("cancel erased editor");
            });report.append("PASS failed/cancelled import retains editor\n");checks++;
            importFixture(screen,"コーヒー、十二漢パン。".getBytes(StandardCharsets.UTF_8));
            runOnMainSync(()->{
                if(!clickButton(screen.getWindow().getDecorView(),"送信音をWAVファイルに保存"))throw new AssertionError("send button missing");
                android.widget.TextView label=screen.getWindow().getDecorView().findViewWithTag("send-validation");
                if(!label.getText().toString().contains("実際に送る表記：こーひー、12ぱん」")||!label.getText().toString().contains("□ 1文字"))throw new AssertionError("send confirmation did not convert/skip imported text");
            });sendKeyDownUpSync(android.view.KeyEvent.KEYCODE_BACK);waitForIdleSync();
            report.append("PASS imported text reaches send confirmation (no transmission)\n");checks++;
        }finally{
            runOnMainSync(()->{editor[0].setText(original[0]);screen.getPreferences(Activity.MODE_PRIVATE).edit().putString("input",original[0]).apply();});
        }
        return checks;
    }
    private void importFixture(MainActivity screen,byte[] bytes)throws Exception{
        File fixture=new File(getTargetContext().getCacheDir(),"読込テスト.txt");
        try{
            try(OutputStream out=new FileOutputStream(fixture)){out.write(bytes);}
            runOnMainSync(()->screen.onActivityResult(13,Activity.RESULT_OK,new Intent().setData(Uri.fromFile(fixture))));
            for(int i=0;i<100;i++){
                final boolean[] done={false};
                runOnMainSync(()->{android.widget.EditText editor=screen.getWindow().getDecorView().findViewWithTag("send-input");done[0]=editor.isEnabled();});
                if(done[0])return;Thread.sleep(50);
            }
            throw new AssertionError("text import timed out");
        }finally{fixture.delete();}
    }
    private static boolean clickButton(View v,String text){
        if(v instanceof android.widget.Button&&text.contentEquals(((android.widget.Button)v).getText())){v.performClick();return true;}
        if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int i=0;i<g.getChildCount();i++)if(clickButton(g.getChildAt(i),text))return true;}
        return false;
    }
}
