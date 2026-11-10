package jp.local.wabun;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.net.Uri;
import android.os.*;
import android.text.InputType;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

public final class MainActivity extends Activity {
    private static final int FILE=10,SAVE_TEXT=11,SAVE_WAV=12,OPEN_TEXT=13,OPEN_VIDEO=14,PERMISSION=20;
    private EditText input,hz,start,end,videoStart,videoEnd;private TextView result,status,normalized,thresholdLabel,settingsLabel;
    private Spinner audioSpeed,lightSpeed;private SeekBar brightness;private LightPreview preview;
    private final List<View> controls=new ArrayList<>();private final ExecutorService executor=Executors.newSingleThreadExecutor();
    private VideoEngine video;private LinearLayout sendPage,receivePage;private RadioGroup tabs;
    private AudioEngine audio;private OpticalEngine optical;private Runnable pendingPermission;
    private int generation=0;private boolean busy=false;private String wavText="";
    private TextView textFileName,audioFileName,videoFileName;
    private boolean importingText=false;
    private final LightRegion lightRegion=new LightRegion();
    private CheckBox useAudioM3,useCnn,autoTiming,followSend,trackLight;
    private ProgressBar sendBar;private TextView sendText,sendStats;private ScrollView sendScroll;
    private boolean sending;private SendProgress sendTimeline;private long lastSendUpdate;
    private Uri selectedVideo;private double selectedFrom,selectedTo;private boolean videoSource;

    private double wavUnit=.12,wavHz=700;private Bitmap currentPreview;
    @Override public void onCreate(Bundle saved){super.onCreate(saved);buildUi();loadSettings();}
    private int dp(int value){return (int)(value*getResources().getDisplayMetrics().density+.5f);}
    private TextView text(LinearLayout parent,String value,int size){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(Color.rgb(22,51,76));t.setPadding(0,dp(7),0,dp(7));parent.addView(t);return t;}
    private EditText edit(LinearLayout parent,String hint,boolean numeric){EditText t=new EditText(this);t.setHint(hint);t.setTextSize(18);if(numeric)t.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_FLAG_DECIMAL);parent.addView(t,new LinearLayout.LayoutParams(-1,-2));controls.add(t);return t;}
    private Button button(LinearLayout parent,String caption,Runnable action,boolean operation){Button b=new Button(this);b.setText(caption);b.setTextSize(16);parent.addView(b,new LinearLayout.LayoutParams(-1,-2));b.setOnClickListener(v->{try{action.run();}catch(Exception e){error(e);}});if(operation)controls.add(b);return b;}
    private Spinner spinner(LinearLayout parent,String[] items){Spinner s=new Spinner(this);s.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,items));parent.addView(s);controls.add(s);return s;}
    private void buildUi(){
        LinearLayout shell=new LinearLayout(this);shell.setOrientation(LinearLayout.VERTICAL);setContentView(shell);
        shell.setOnApplyWindowInsetsListener((v,insets)->{v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        tabs=new RadioGroup(this);tabs.setOrientation(LinearLayout.HORIZONTAL);shell.addView(tabs);
        RadioButton sendTab=new RadioButton(this);sendTab.setText("送信");sendTab.setId(View.generateViewId());tabs.addView(sendTab,new RadioGroup.LayoutParams(0,-2,1));
        RadioButton receiveTab=new RadioButton(this);receiveTab.setText("受信");receiveTab.setId(View.generateViewId());tabs.addView(receiveTab,new RadioGroup.LayoutParams(0,-2,1));
        ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(16),dp(12),dp(16),dp(24));scroll.addView(root);shell.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        text(root,"和文モールス送受信",25).setTypeface(null,Typeface.BOLD);
        text(root,"試作版 0.5.0｜音M3・光CNN／ルール方式・端末内で処理",14);
        text(root,"通話中のマイク受信は端末により制限されます。AQUOSの通話録音をエクスポートして読み込めます。音声送信はスピーカー出力です。通話相手に届くかは未確認です。",15);
        status=text(root,"待機中",17);status.setTag("operation-status");status.setBackgroundColor(Color.rgb(231,243,246));
        text(root,"音の短点時間（送信側と受信側を合わせる）",16);audioSpeed=spinner(root,new String[]{"120 ms（初期値・実機未検証）","180 ms（ゆっくり）","240 ms（さらにゆっくり）","80 ms（試験用）"});
        text(root,"音程 Hz（送信側と受信側を合わせる）",16);hz=edit(root,"700",true);hz.setText("700");
        text(root,"光の短点時間（音とは別に保存）",16);lightSpeed=spinner(root,new String[]{"300 ms（初期値・実機未検証）","450 ms（ゆっくり）","600 ms（さらにゆっくり）"});
        sendPage=new LinearLayout(this);sendPage.setOrientation(LinearLayout.VERTICAL);root.addView(sendPage);sendPage.setTag("send-page");
        receivePage=new LinearLayout(this);receivePage.setOrientation(LinearLayout.VERTICAL);root.addView(receivePage);receivePage.setTag("receive-page");
        text(sendPage,"送る文章",20);input=edit(sendPage,"ひらがな・カタカナで入力（半角カナも可）",false);input.setMinLines(2);input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);input.setText("こんにちは");
        input.setTag("send-input");
        button(sendPage,"和文記号を入力",()->{
            String[] symbols={"ー","、","」","（","）","゛","゜"};
            String[] labels={"ー　長音　.--.-","、　区切点　.-.-.-","」　段落　.-.-..","（　括弧を開く　-.--.-","）　括弧を閉じる　.-..-.","゛　濁点　..","゜　半濁点　..--."};
            new AlertDialog.Builder(this).setTitle("和文記号を選択（送信はしません）").setItems(labels,(dialog,which)->{
                int a=input.getSelectionStart(),b=input.getSelectionEnd();if(a<0||b<0)a=b=input.length();
                int left=Math.min(a,b),right=Math.max(a,b);input.getText().replace(left,right,symbols[which]);input.setSelection(left+1);input.requestFocus();
            }).setNegativeButton("取消",null).show();
        },true);
        text(sendPage,"対応記号：ー 、 」 （ ） ゛ ゜。音・光とも同じ和文符号です。段落は 」 を使い、句点 。 も 」 に変換します。開きかぎ括弧「や欧文の ! ? 等は未対応です。",14);
        button(sendPage,"テキストファイルを開く",()->{
            Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);
            i.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"text/*","application/octet-stream"});startActivityForResult(i,OPEN_TEXT);
        },true);
        textFileName=text(sendPage,"選択したTXT：未選択",15);textFileName.setTag("text-file-name");textFileName.setTextIsSelectable(true);
        text(sendPage,"TXTを送る文章へ表示します（UTF-8／Shift_JIS／BOM付きUTF-16、64 KB以内）。漢数字は数字へ変換（十二→12、二百三→203）。送れない文字は□で表示し、音・光・WAV送信から除外します。送信は300符号以内です。",14);
        normalized=text(sendPage,"小書きは通常サイズへ、。は段落符号」へ変換します。送信前に確認画面を表示します。丸括弧内も和文です。",14);
        normalized.setTag("send-validation");
        input.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence s,int start,int count,int after){}public void onTextChanged(CharSequence s,int start,int before,int count){showSendPreview();}public void afterTextChanged(android.text.Editable e){}});
        button(sendPage,"音で送る",()->confirmSend(false,false),true);
        button(sendPage,"送信音をWAVファイルに保存",()->confirmSend(false,true),true);
        button(sendPage,"ライトで送る",()->permission(Manifest.permission.CAMERA,()->confirmSend(true,false)),true);
        text(sendPage,"送出の進捗（相手の受信確認ではありません）",18);
        sendBar=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);sendBar.setMax(1000);sendBar.setTag("send-progress");sendPage.addView(sendBar);
        sendStats=text(sendPage,"待機中",16);sendStats.setTag("send-stats");
        followSend=new CheckBox(this);followSend.setText("送信中の文字へ自動スクロール");followSend.setChecked(true);sendPage.addView(followSend);
        sendScroll=new ScrollView(this);sendText=new TextView(this);sendText.setTextSize(23);sendText.setPadding(dp(8),dp(8),dp(8),dp(8));sendText.setTag("send-position");sendScroll.addView(sendText);sendPage.addView(sendScroll,new LinearLayout.LayoutParams(-1,dp(150)));
        sendScroll.setOnTouchListener((v,e)->{if(e.getActionMasked()==MotionEvent.ACTION_DOWN)followSend.setChecked(false);return false;});
        text(receivePage,"音を受ける",20);
        useAudioM3=new CheckBox(this);useAudioM3.setText("音をM3で認識（オフなら従来ルール方式）");useAudioM3.setChecked(true);useAudioM3.setTag("audio-m3");receivePage.addView(useAudioM3);controls.add(useAudioM3);
        text(receivePage,"M3録音解析は1回120秒以内。M3は音程・短点を自動推定します。マイクは一文字分の区切りを待って順次表示します。実機の精度・遅延は未検証です。",14);
        button(receivePage,"マイクで受信する",()->permission(Manifest.permission.RECORD_AUDIO,this::microphone),true);
        text(receivePage,"録音の解析範囲（秒）：空欄なら全体。通話案内や会話を除外できます。",14);start=edit(receivePage,"開始 0",true);end=edit(receivePage,"終了（空欄＝最後まで）",true);
        button(receivePage,"録音ファイルを開く",()->{settings();Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);i.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"audio/*","application/octet-stream"});startActivityForResult(i,FILE);},true);
        audioFileName=text(receivePage,"選択した録音：未選択",15);audioFileName.setTag("audio-file-name");audioFileName.setTextIsSelectable(true);
        text(receivePage,"光を受ける",20);text(receivePage,"光源をプレビューで選び、確認後に受信を開始します。CNNはPC採用モデルの重みを使用しますが、スマホでの実撮影精度は未検証です。",14);
        useCnn=new CheckBox(this);useCnn.setText("CNNで光を認識（オフなら従来ルール方式）");useCnn.setChecked(true);receivePage.addView(useCnn);controls.add(useCnn);
        autoTiming=new CheckBox(this);autoTiming.setText("CNNの短点時間を自動推定（初めの点滅を蓄積）");autoTiming.setChecked(true);receivePage.addView(autoTiming);controls.add(autoTiming);
        text(receivePage,"自動推定できない場合は停止し、自動推定をオフにして送信側と同じ短点時間を選択してください。明るさの境界はルール方式だけに使用します。",14);
        thresholdLabel=text(receivePage,"明るさの境界：160",16);brightness=new SeekBar(this);brightness.setMax(225);brightness.setProgress(140);receivePage.addView(brightness);
        brightness.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onProgressChanged(SeekBar s,int p,boolean user){int value=p+20;thresholdLabel.setText("明るさの境界："+value);if(optical!=null)optical.threshold=value;if(video!=null)video.threshold=value;}public void onStartTrackingTouch(SeekBar s){}public void onStopTrackingTouch(SeekBar s){}});
        button(receivePage,"カメラで光源を確認",()->permission(Manifest.permission.CAMERA,this::camera),true);
        text(receivePage,"動画は先頭の解析範囲から最大30秒のプレビューを読みます。枠を選択した後、指定範囲の先頭から解析し直します。音声は解析しません。",14);
        text(receivePage,"動画の解析範囲（秒）：空欄なら全体、最大30分",14);videoStart=edit(receivePage,"動画の開始 0",true);videoEnd=edit(receivePage,"動画の終了（空欄＝最後まで）",true);
        button(receivePage,"動画ファイルを開く",()->{settings();Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);i.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"video/*","application/octet-stream"});startActivityForResult(i,OPEN_VIDEO);},true);
        videoFileName=text(receivePage,"選択した動画：未選択",15);videoFileName.setTag("video-file-name");videoFileName.setTextIsSelectable(true);
        text(receivePage,"ファイル名は最後に選択したものです。読込・解析の成功／失敗は上部の状態欄で確認できます。",14);
        preview=new LightPreview(this);preview.region=lightRegion;preview.setTag("light-preview");receivePage.addView(preview,new LinearLayout.LayoutParams(-1,dp(280)));preview.setVisibility(View.GONE);
        preview.changed=()->{status.setText("光源枠を変更しました。確認して受信・解析を開始してください。");};
        text(receivePage,"水色＝確認前／緑＝受信対象／黄丸＝点滅候補。タップ・ドラッグで移動、2本指または下のバーで大きさを変更できます。",14);
        SeekBar size=new SeekBar(this);size.setMax(285);size.setProgress(65);receivePage.addView(size);size.setTag("roi-size");
        size.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onProgressChanged(SeekBar b,int p,boolean user){if(user&&preview.isEnabled()){lightRegion.manual(lightRegion.x,lightRegion.y,(p+15)/1000.);preview.invalidate();status.setText("枠の大きさを変更しました。再確認してください。");}}public void onStartTrackingTouch(SeekBar b){}public void onStopTrackingTouch(SeekBar b){}});
        trackLight=new CheckBox(this);trackLight.setText("カメラ受信時に光源の小さな移動へ追従");trackLight.setChecked(true);receivePage.addView(trackLight);trackLight.setOnCheckedChangeListener((b,c)->lightRegion.tracking=c);
        button(receivePage,"光源を自動で探し直す",()->{if(videoSource){if(busy)throw new IllegalArgumentException("プレビューまたは解析を停止してから操作してください。");lightRegion.reset();startVideo(true);}else {lightRegion.reset();preview.invalidate();}},false);
        button(receivePage,"この光源で受信・解析開始",()->{if(currentPreview==null)throw new IllegalArgumentException("先にカメラまたは動画プレビューを開いてください。");if(videoSource){if(busy)throw new IllegalArgumentException("プレビュー完了まで待ってください。");lightRegion.confirmed=true;startVideo(false);}else {if(optical==null||!busy)throw new IllegalArgumentException("カメラを開始してください。");lightRegion.confirmed=true;status.setText("選択した光源で受信開始。途中で枠を変更すると文字蓄積はリセットされます。");}preview.invalidate();},false);
        text(receivePage,"受信した文章",20);result=text(receivePage,"",22);result.setTextIsSelectable(true);result.setMinHeight(dp(90));result.setBackgroundColor(Color.WHITE);
        settingsLabel=text(receivePage,"仮名はひらがな、和文記号・数字はそのまま表示します。丸括弧で欧文へ切り替えません。□は符号を確定できなかった箇所です。信頼性の高い速度は実機試験で決定します。",14);
        button(receivePage,"文章をコピー",()->{android.content.ClipboardManager c=(android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE);c.setPrimaryClip(ClipData.newPlainText("和文モールス",result.getText()));Toast.makeText(this,"コピーしました",Toast.LENGTH_SHORT).show();},false);
        button(receivePage,"結果をTXTに保存",()->{Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("text/plain").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"morse_result.txt");startActivityForResult(i,SAVE_TEXT);},false);
        Button stop=button(shell,"■ すべて停止",this::stop,false);stop.setTextColor(Color.rgb(160,25,25));
        tabs.setOnCheckedChangeListener((group,id)->{if(busy)stop();sendPage.setVisibility(id==sendTab.getId()?View.VISIBLE:View.GONE);receivePage.setVisibility(id==receiveTab.getId()?View.VISIBLE:View.GONE);scroll.scrollTo(0,0);});
        tabs.check(sendTab.getId());
    }
    private double[] settings(){
        double freq=Double.parseDouble(hz.getText().toString());if(!Double.isFinite(freq)||freq<200||freq>2000)throw new IllegalArgumentException("音程は200〜2000 Hzで指定してください。");
        double a=new double[]{.12,.18,.24,.08}[audioSpeed.getSelectedItemPosition()],l=new double[]{.30,.45,.60}[lightSpeed.getSelectedItemPosition()];
        saveSettings();return new double[]{a,l,freq};
    }
    private void confirmSend(boolean light,boolean save){
        double[] cfg=settings();String prepared=MorseCodec.editableText(input.getText().toString());input.setText(prepared);
        String labels=MorseCodec.normalize(prepared);String visible=MorseCodec.hiragana(labels);showSendPreview();
        int excluded=(int)prepared.chars().filter(c->c=='□').count();
        new AlertDialog.Builder(this).setTitle("送信する表記を確認").setMessage("実際に送る文章：\n"+visible+String.format(Locale.JAPAN,"\n\n送出見込み：約 %.1f 秒（前後の休止を含む）",new SendProgress(labels,light?cfg[1]:cfg[0]).total)+"\n\n□ "+excluded+"文字を除外します（□自体の符号・間隔は送りません）。\n\n小書き・句点の元の表記は受信側で完全には復元できません。"+(light?"":"\n通話回線への直接送信機能ではありません。")).setNegativeButton("戻る",null).setPositiveButton(save?"保存先を選ぶ":"送信する",(d,w)->{
            if(save){wavText=labels;wavUnit=cfg[0];wavHz=cfg[2];startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("audio/wav").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"morse_send.wav"),SAVE_WAV);}
            else if(light){int id=begin("ライトで送信中",false);prepareSend(labels,cfg[1]);optical=newOptical(id);optical.progress=(elapsed,total)->updateSend(id,elapsed,total);OpticalEngine job=optical;run(id,()->job.transmit(MorseCodec.encode(labels),cfg[1]),true);}
            else{int id=begin("音で送信中：通話相手に届くかは別途確認してください。",false);prepareSend(labels,cfg[0]);audio=newAudio(id);audio.progress=(elapsed,total)->updateSend(id,elapsed,total);AudioEngine job=audio;run(id,()->{job.play(MorseCodec.encode(labels),cfg[0],cfg[2]);post(id,"音の出力を終了しました。",null);},true);}
        }).show();
    }
    private void showSendPreview(){
        String original=input.getText().toString(),display=MorseCodec.editableText(original);
        int skipped=(int)display.chars().filter(c->c=='□').count();
        String message="確認用の表記："+display+"\n□ "+skipped+"文字は送信しません。";
        try{message+="\n実際に送る表記："+MorseCodec.hiragana(MorseCodec.normalize(original));}
        catch(IllegalArgumentException e){message+="\n"+e.getMessage();}
        normalized.setText(message);
    }
    private AudioEngine newAudio(int id){AudioEngine a=new AudioEngine(this,(s,t)->post(id,s,t));a.m3Enabled=useAudioM3.isChecked();return a;}
    private OpticalEngine newOptical(int id){OpticalEngine o=new OpticalEngine(this,opticalListener(id));o.region=lightRegion;o.cnnEnabled=useCnn.isChecked();o.autoTiming=autoTiming.isChecked();return o;}
    private OpticalEngine.Listener opticalListener(int id){return new OpticalEngine.Listener(){public void update(String s,String t){post(id,s,t);}public void finished(String s,String t){post(id,s,t);runOnUiThread(()->{if(id==generation)idle();});}public void preview(Bitmap b){runOnUiThread(()->{if(id!=generation){b.recycle();return;}Bitmap old=currentPreview;currentPreview=b;preview.setImageBitmap(b);if(old!=null&&old!=b)old.recycle();});}public void candidates(double[][] values){runOnUiThread(()->{if(id==generation){preview.candidates=values;preview.invalidate();}});}};}
    private void microphone(){double[] cfg=settings();int id=begin("マイクを開始しています…",true);audio=newAudio(id);AudioEngine job=audio;run(id,()->job.microphone(cfg[0],cfg[2],.005),true);}
    private void camera(){videoSource=false;selectedVideo=null;lightRegion.confirmed=false;currentPreview=null;preview.setImageDrawable(null);double[] cfg=settings();int id=begin("カメラを開始しています…",true);preview.setVisibility(View.VISIBLE);optical=newOptical(id);optical.threshold=brightness.getProgress()+20;OpticalEngine job=optical;run(id,()->job.receive(cfg[1]),false);}
    private int begin(String message,boolean clear){stop();int id=++generation;busy=true;for(View v:controls)v.setEnabled(false);getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);status.setText(message);if(clear)result.setText("");return id;}
    private interface Work {void run()throws Exception;}
    private void run(int id,Work work,boolean finish){executor.execute(()->{try{work.run();}catch(Exception e){post(id,"処理できませんでした："+e.getMessage(),null);runOnUiThread(()->{if(id==generation&&sending)sendStats.setText("送出エラー（未完了）\n"+sendStats.getText());});runOnUiThread(()->{if(id==generation)idle();});}finally{if(finish)runOnUiThread(()->{if(id==generation)idle();});}});}
    private void post(int id,String message,String value){runOnUiThread(()->{if(id!=generation)return;status.setText(message);if(value!=null)result.setText(value);});}
    private void idle(){sending=false;if(preview!=null)preview.setEnabled(true);busy=false;importingText=false;for(View v:controls)v.setEnabled(true);getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);}
    private void stop(){if(busy&&sending&&sendTimeline!=null&&sendBar.getProgress()<1000)sendStats.setText("中止／中断（送信完了ではありません）\n"+sendStats.getText());generation++;if(video!=null){video.stop();video=null;}if(audio!=null){audio.stop();audio=null;}if(optical!=null){optical.stop();optical=null;}idle();if(status!=null)status.setText("停止しました。受信結果は残しています。");}
    private void error(Exception e){status.setText("確認してください："+e.getMessage());}
    private void permission(String name,Runnable action){if(checkSelfPermission(name)==PackageManager.PERMISSION_GRANTED){action.run();return;}pendingPermission=action;requestPermissions(new String[]{name},PERMISSION);}
    @Override public void onRequestPermissionsResult(int request,String[] names,int[] grants){super.onRequestPermissionsResult(request,names,grants);Runnable action=pendingPermission;pendingPermission=null;if(request==PERMISSION&&grants.length>0&&grants[0]==PackageManager.PERMISSION_GRANTED){if(action!=null)try{action.run();}catch(Exception e){error(e);}}else status.setText("権限が許可されませんでした。録音ファイル読込はマイク権限なしで使用できます。");}
    @Override protected void onActivityResult(int request,int code,Intent data){super.onActivityResult(request,code,data);if(code!=RESULT_OK||data==null||data.getData()==null)return;Uri uri=data.getData();try{
        if(request==OPEN_TEXT)textFileName.setText("選択したTXT："+InputFileName.read(getContentResolver(),uri));
        if(request==FILE)audioFileName.setText("選択した録音："+InputFileName.read(getContentResolver(),uri));
        if(request==OPEN_VIDEO)videoFileName.setText("選択した動画："+InputFileName.read(getContentResolver(),uri));
        if(request==OPEN_TEXT){int id=begin("テキストを読み込んでいます…",false);importingText=true;run(id,()->{
            String text;try(InputStream in=getContentResolver().openInputStream(uri)){text=TextInput.read(in);}
            runOnUiThread(()->{
                if(id!=generation||isDestroyed())return;
                input.setText(text);input.setSelection(0);input.requestFocus();
                showSendPreview();
                saveSettings();status.setText("テキストを「送る文章」に表示しました。内容を確認してください。");
            });
        },true);}
        if(request==FILE){double[] cfg=settings();double from=start.getText().toString().trim().isEmpty()?0:Double.parseDouble(start.getText().toString()),to=end.getText().toString().trim().isEmpty()?0:Double.parseDouble(end.getText().toString());if(!Double.isFinite(from)||!Double.isFinite(to)||from<0||to<0||(to>0&&to<=from))throw new IllegalArgumentException("解析区間を確認してください。");int id=begin("録音を読み込んでいます…",true);audio=newAudio(id);AudioEngine job=audio;run(id,()->job.decodeFile(uri,cfg[0],cfg[2],.003,from,to),true);}
        if(request==OPEN_VIDEO){settings();selectedFrom=videoStart.getText().toString().trim().isEmpty()?0:Double.parseDouble(videoStart.getText().toString());selectedTo=videoEnd.getText().toString().trim().isEmpty()?0:Double.parseDouble(videoEnd.getText().toString());if(!Double.isFinite(selectedFrom)||!Double.isFinite(selectedTo)||selectedFrom<0||selectedTo<0||(selectedTo>0&&selectedTo<=selectedFrom))throw new IllegalArgumentException("動画の解析区間を確認してください。");selectedVideo=uri;videoSource=true;lightRegion.reset();currentPreview=null;preview.setImageDrawable(null);startVideo(true);}
        if(request==SAVE_WAV){int id=begin("WAVを保存中…",false);audio=newAudio(id);AudioEngine job=audio;run(id,()->{job.saveWav(uri,MorseCodec.encode(wavText),wavUnit,wavHz);post(id,"WAVを保存しました。",null);},true);}
        if(request==SAVE_TEXT){String contents=result.getText()+"\n";try(OutputStream out=getContentResolver().openOutputStream(uri,"wt")){if(out==null)throw new IOException("保存先を開けません。");out.write(contents.getBytes(StandardCharsets.UTF_8));}status.setText("受信した文章を保存しました。");}
    }catch(Exception e){error(e);}}
    private void startVideo(boolean previewOnly){
        if(selectedVideo==null)throw new IllegalArgumentException("動画ファイルを選択してください。");
        double[] cfg=settings();int id=begin(previewOnly?"光源のプレビューを取得中…":"CNN／ルールで動画を解析中…",!previewOnly);
        preview.setVisibility(View.VISIBLE);preview.setEnabled(previewOnly);
        video=new VideoEngine(this,opticalListener(id));video.threshold=brightness.getProgress()+20;video.region=lightRegion;video.cnnEnabled=useCnn.isChecked();video.autoTiming=autoTiming.isChecked();video.previewOnly=previewOnly;
        VideoEngine job=video;Uri uri=selectedVideo;run(id,()->job.decodeFile(uri,cfg[1],selectedFrom,selectedTo),true);
    }
    private void prepareSend(String labels,double unit){sending=true;sendTimeline=new SendProgress(labels,unit);lastSendUpdate=0;sendBar.setProgress(0);followSend.setChecked(true);sendScroll.scrollTo(0,0);updateSend(generation,0,sendTimeline.total);sendScroll.post(()->sendScroll.requestRectangleOnScreen(new Rect(0,0,sendScroll.getWidth(),sendScroll.getHeight()),false));}
    private void updateSend(int id,double elapsed,double total){
        long now=SystemClock.elapsedRealtime();if(now-lastSendUpdate<80&&elapsed<total&&elapsed>0)return;lastSendUpdate=now;
        runOnUiThread(()->{if(id!=generation||sendTimeline==null)return;
            SendProgress t=sendTimeline;int done=t.completed(elapsed),active=t.active(elapsed);
            StringBuilder display=new StringBuilder();for(char c:t.labels.toCharArray())display.append(c>='ァ'&&c<='ヶ'?(char)(c-0x60):c);
            android.text.SpannableString styled=new android.text.SpannableString(display);
            for(int j=0;j<done;j++)styled.setSpan(new android.text.style.ForegroundColorSpan(Color.GRAY),t.positions[j],t.positions[j]+1,0);
            if(active>=0){int pos=t.positions[active];styled.setSpan(new android.text.style.BackgroundColorSpan(Color.rgb(255,220,100)),pos,pos+1,0);styled.setSpan(new android.text.style.StyleSpan(Typeface.BOLD),pos,pos+1,0);}
            sendText.setText(styled);sendBar.setProgress((int)Math.min(1000,1000*elapsed/total));
            String state=elapsed>=total?"送出完了":(active>=0?"文字を送出中":(done==0?"開始前の休止":"文字間・終了の休止"));
            sendStats.setText(String.format(Locale.JAPAN,"%s  %d／%d文字単位\n経過 %.1f秒／見込み %.1f秒・残り約 %.1f秒",state,done,t.ends.length,elapsed,total,Math.max(0,total-elapsed)));
            int pos=active>=0?t.positions[active]:(done>0?t.positions[done-1]:0);
            if(followSend.isChecked())sendText.post(()->{if(id==generation&&sendText.getLayout()!=null)sendScroll.smoothScrollTo(0,Math.max(0,sendText.getLayout().getLineTop(sendText.getLayout().getLineForOffset(pos))-dp(40)));});
        });
    }
    private void saveSettings(){getPreferences(MODE_PRIVATE).edit().putString("input",input.getText().toString()).putString("hz",hz.getText().toString()).putInt("audio",audioSpeed.getSelectedItemPosition()).putInt("light",lightSpeed.getSelectedItemPosition()).putInt("brightness",brightness.getProgress()).apply();}
    private void loadSettings(){android.content.SharedPreferences p=getPreferences(MODE_PRIVATE);input.setText(p.getString("input","こんにちは"));hz.setText(p.getString("hz","700"));audioSpeed.setSelection(Math.min(3,p.getInt("audio",0)));lightSpeed.setSelection(Math.min(2,p.getInt("light",0)));brightness.setProgress(p.getInt("brightness",140));}
    @Override protected void onPause(){super.onPause();saveSettings();if(busy&&!importingText)stop();}
    @Override protected void onDestroy(){stop();generation++;executor.shutdown();super.onDestroy();}
}
