package jp.local.wabun;

import android.Manifest;
import android.app.*;
import android.os.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.hardware.camera2.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Dedicated, offline test sender. Original recognition app is a separate package. */
public class BatchActivity extends Activity {
    private JSONArray batches;
    private BluetoothRemote remote;
    private TextView remoteStatus;
    private boolean remoteStarted;
    private final Set<String> remoteStartIds=new HashSet<>();
    private Spinner batch, speed;
    private EditText first,last;
    private TextView details,status,timing;
    private ProgressBar progress;
    private CheckBox autoHeader;
    private long startedNs,plannedNs,lastProgressNs;
    private volatile int completedCases,totalCases;
    private Button start, selectMany, clearSelection;
    private final BatchSelection selection = new BatchSelection();
    private final AtomicBoolean cancel=new AtomicBoolean(false);
    private volatile boolean running=false;
    private JSONArray log=new JSONArray();
    private String corpusHash="",torchId;
    private CameraManager camera;
    private JSONObject session=new JSONObject();
    private void text(String s){runOnUiThread(()->status.setText(s));}
    private TextView label(LinearLayout root,String s){TextView t=new TextView(this);t.setText(s);t.setTextSize(17);root.addView(t);return t;}
    private Button button(LinearLayout root,String title,Runnable action){Button b=new Button(this);b.setText(title);root.addView(b);b.setOnClickListener(v->action.run());return b;}
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        camera=(CameraManager)getSystemService(CAMERA_SERVICE);
        ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(24,30,24,30);scroll.addView(root);setContentView(scroll);
        // Respect status/navigation bar insets on edge-to-edge Android versions.
        root.setOnApplyWindowInsetsListener((v,insets)->{v.setPadding(24,30+insets.getSystemWindowInsetTop(),24,30+insets.getSystemWindowInsetBottom());return insets;});
        label(root,"光モールス試験送信 0.5.0");
        label(root,"単文字65ケースは従来どおり。②は44バッチ、③は20バッチから複数の例文を選んで順次送信できます。各例文は一文を文末まで送信（区切点なしは全文）。和文固定。録画は別端末で開始してください。");
        try {
            byte[] bytes;
            try(java.io.InputStream input=getAssets().open("batches.json");java.io.ByteArrayOutputStream output=new java.io.ByteArrayOutputStream()){
                byte[] buffer=new byte[8192];int count;while((count=input.read(buffer))!=-1)output.write(buffer,0,count);bytes=output.toByteArray();
            }
            StringBuilder h=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))h.append(String.format(Locale.ROOT,"%02x",b&255));corpusHash=h.toString();
            batches=new JSONObject(new String(bytes,StandardCharsets.UTF_8)).getJSONArray("batches");
        }catch(Exception e){label(root,"原稿を読み込めません："+e.getMessage());return;}
        remoteStatus=label(root,"Bluetooth遠隔待受：オフ");
        button(root,"送信側：Bluetooth待受を開始",this::enableRemote);
        button(root,"Bluetooth待受を終了",this::disableRemote);
        batch=new Spinner(this);String[] names=new String[batches.length()];for(int i=0;i<names.length;i++)names[i]=batches.optJSONObject(i).optString("name");batch.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,names));root.addView(batch);
        speed=new Spinner(this);speed.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"短点300 ms（既存の初期値）","短点450 ms","短点600 ms"}));root.addView(speed);
        label(root,"複数選択時はチェックした順に送信。未選択時は上の1単位のみ。①は65文字すべて送信。");
        first=new EditText(this);first.setInputType(2);root.addView(first);last=new EditText(this);last.setInputType(2);root.addView(last);
        autoHeader=new CheckBox(this);autoHeader.setText("開始前に送信範囲を光で連携（試験機能・送信時間が増えます）");root.addView(autoHeader);
        details=label(root,"");status=label(root,"待機中");
        autoHeader.setOnCheckedChangeListener((v,on)->{if(!running)preview();});
        timing=label(root,"開始すると経過時間・残り目安・完了件数を表示します。");
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(1000);root.addView(progress);
        selectMany=button(root,"複数の送信単位を選択",this::chooseMany);
        clearSelection=button(root,"複数選択を解除（上の1単位のみ）",()->{if(running)return;selection.clear();preview();});
        button(root,"順序・予定時間・原稿を確認",this::preview);
        button(root,"受信側：この選択を別端末へ指示",this::openController);
        start=button(root,"送信開始（15秒後から点滅）",this::confirmStart);
        button(root,"停止・消灯",()->{cancel.set(true);text("停止要求：次の送信は行いません。");});
        button(root,"送信記録をJSONで保存",()->{if(running){text("停止または完了してから保存してください。");return;}Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/json").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"optical_session.json");startActivityForResult(i,9);});
        speed.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> p){}public void onItemSelected(android.widget.AdapterView<?> p,View v,int pos,long id){if(!running)preview();}});
        batch.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> p){}public void onItemSelected(android.widget.AdapterView<?> p,View v,int pos,long id){if(running)return;JSONObject b=batches.optJSONObject(pos);int n=b.optJSONArray("cases").length();first.setText("1");last.setText(String.valueOf(n));first.setEnabled(false);last.setEnabled(false);preview();}});
    }
    private void enableRemote(){
        if(running){text("送信を停止してから設定してください。");return;}
        if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.CAMERA},1);text("カメラ権限を許可して、もう一度待受を開始してください。");return;}
        BluetoothRemote.choose(this,peer->{
            disableRemote();remote=new BluetoothRemote();getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            remote.listen(this,peer,this::remoteCommand,message->runOnUiThread(()->remoteStatus.setText(message)));
        });
    }
    private void disableRemote(){
        if(remote!=null){remote.close();remote=null;}
        if(remoteStarted&&running)cancel.set(true);
        if(remoteStatus!=null)remoteStatus.setText("Bluetooth遠隔待受：オフ");
        if(!running)getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }
    private void openController(){
        if(running){text("送信を停止してから切り替えてください。");return;}
        try{
            preview();JSONArray indices=new JSONArray();for(int index:selection.indicesOr(batch.getSelectedItemPosition()))indices.put(index);
            JSONObject request=new JSONObject().put("protocol",1).put("corpus_sha256",corpusHash).put("indices",indices).put("unit_ms",unit()).put("header",autoHeader.isChecked());
            startActivity(new Intent(this,RemoteActivity.class).putExtra("plan",request.toString()).putExtra("summary",details.getText().toString().split("\n",2)[0]+"\n"+plan().getString("name")));
        }catch(Exception e){text(e.getMessage());}
    }
    private JSONObject remoteCommand(JSONObject request)throws Exception{
        JSONObject reply=new JSONObject().put("ok",false);String message="";
        try{
            if(request.getInt("protocol")!=1)throw new IllegalArgumentException("通信版が一致しません。");
            String action=request.getString("action");
            if("stop".equals(action)){cancel.set(true);message="停止を受け付けました。";}
            else if("status".equals(action)){message="状態を取得しました。";}
            else if("start".equals(action)){
                String id=request.getString("request_id");
                if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)throw new IllegalArgumentException("送信側のカメラ権限が必要です。");
                int ms=request.getInt("unit_ms");JSONArray ids=request.getJSONArray("indices");int[] indices=new int[ids.length()];
                for(int i=0;i<indices.length;i++)indices[i]=ids.getInt(i);
                // Shared protocol validation rejects duplicates, invalid speeds and ranges.
                RemoteStartPolicy.validate(id,remoteStartIds,running,corpusHash,request.getString("corpus_sha256"),ms,indices);
                selection.clear();for(int index:indices)selection.add(index);
                speed.setSelection(ms==300?0:ms==450?1:2);autoHeader.setChecked(request.getBoolean("header"));preview();
                remoteStartIds.add(id);begin();remoteStarted=running;
                if(!running)throw new IllegalStateException("送信を開始できませんでした。");
                session.put("remote_request_id",id);message="開始を受け付けました。15秒後に発光します。";
            }else throw new IllegalArgumentException("未対応の指示です。");
            reply.put("ok",true);
        }catch(Exception e){message=e.getMessage();}
        return reply.put("message",message).put("running",running).put("completed",completedCases).put("total",totalCases).put("progress",timing.getText().toString());
    }
    private int unit(){return new int[]{300,450,600}[speed.getSelectedItemPosition()];}
    private void chooseMany(){
        if(running)return;
        String[] names=new String[batches.length()];boolean[] checked=new boolean[names.length];
        BatchSelection draft=selection.copy();
        for(int i=0;i<names.length;i++){names[i]=batches.optJSONObject(i).optString("name");checked[i]=draft.contains(i);}
        new AlertDialog.Builder(this).setTitle("チェックした順に送信（重複なし）")
            .setMultiChoiceItems(names,checked,(d,i,on)->{if(on)draft.add(i);else draft.remove(i);})
            .setNegativeButton("取消",null).setPositiveButton("選択を確定",(d,w)->{selection.replace(draft);preview();}).show();
    }
    // Build a fresh immutable-in-practice snapshot before starting the worker.
    // Flatten all 65 single cases; never truncate them to one item.
    private JSONObject plan()throws Exception{
        JSONArray cases=new JSONArray(), ids=new JSONArray();StringBuilder names=new StringBuilder();
        for(int index:selection.indicesOr(batch.getSelectedItemPosition())){
            JSONObject source=batches.getJSONObject(index);JSONArray items=source.getJSONArray("cases");
            BatchRange.full(source.getString("id"),items.length());ids.put(source.getString("id"));
            names.append(ids.length()).append(". ").append(source.getString("name")).append("\n");
            for(int i=0;i<items.length();i++)cases.put(new JSONObject(items.getJSONObject(i).toString()).put("source_batch",source.getString("id")));
        }
        String header=autoHeader.isChecked()?OpticalHeader.encode(corpusHash,unit(),selection.indicesOr(batch.getSelectedItemPosition())):"";
        return new JSONObject().put("header",header).put("id",ids.length()==1?ids.getString(0):"selection_queue").put("batch_ids",ids).put("name",names.toString()).put("cases",cases);
    }
    private void preview(){try{
        JSONObject p=plan();JSONArray cases=p.getJSONArray("cases");long units=0;StringBuilder labels=new StringBuilder();
        for(int i=0;i<cases.length();i++){JSONObject c=cases.getJSONObject(i);units+=c.getLong("units");labels.append(c.getString("id")).append("：").append(c.getString("labels")).append("\n");}
        String header=p.getString("header");double headerSeconds=header.isEmpty()?0:OpticalHeader.units(header)*unit()/1000.0+10;
        long seconds=(long)Math.ceil(units*unit()/1000.0+10*(cases.length()-1)+20+headerSeconds);
        first.setText("1");last.setText(String.valueOf(cases.length()));
        details.setText(String.format(Locale.JAPAN,"%d送信単位／%d件／予定 %d時間%02d分%02d秒\n開始前15秒・データ間10秒・終了後5秒\n送信順：\n%s\n送信する全文字／文章：\n%s",p.getJSONArray("batch_ids").length(),cases.length(),seconds/3600,seconds/60%60,seconds%60,p.getString("name"),labels));
        if(!header.isEmpty())details.append("\n自動連携信号＋本文前消灯：追加約"+(int)Math.ceil(headerSeconds)+"秒（予定時間に含む）");
    }catch(Exception e){text(e.getMessage());}}
    private void confirmStart(){
        if(running)return;
        if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.CAMERA},1);text("カメラ権限を許可後、もう一度開始してください。");return;}
        try{JSONObject p=plan();preview();new AlertDialog.Builder(this).setTitle("選択順に光送信を開始しますか")
            .setMessage(p.getString("name")+"\n合計 "+p.getJSONArray("cases").length()+"件。開始前15秒、データ間10秒消灯。①を選ぶと65文字すべてを送信します。\n別端末で録画し、照合用に送信記録JSONも保存してください。")
            .setNegativeButton("取消",null).setPositiveButton("開始",(d,w)->begin()).show();}catch(Exception e){text(e.getMessage());}
    }
    private void begin(){
        try{
            final JSONObject b=plan();final int[] r={1,b.getJSONArray("cases").length()};final int ms=unit();
            totalCases=r[1];completedCases=0;long totalUnits=0;for(int i=0;i<totalCases;i++)totalUnits+=b.getJSONArray("cases").getJSONObject(i).getLong("units");
            String header=b.getString("header");double headerSeconds=header.isEmpty()?0:OpticalHeader.units(header)*ms/1000.0+10;
            plannedNs=(long)((totalUnits*ms/1000.0+10*(totalCases-1)+20+headerSeconds)*1e9);
            log=new JSONArray();session=new JSONObject().put("batch",b.getString("id")).put("batch_ids",b.getJSONArray("batch_ids")).put("app_version","0.5.0").put("optical_header",header).put("estimated_duration_seconds",plannedNs/1e9).put("first",r[0]).put("last",r[1]).put("unit_ms",ms).put("gap_seconds",10).put("start_dark_seconds",15).put("end_dark_seconds",5).put("corpus_sha256",corpusHash).put("events",log).put("status","running");
            running=true;cancel.set(false);batch.setEnabled(false);speed.setEnabled(false);first.setEnabled(false);last.setEnabled(false);start.setEnabled(false);autoHeader.setEnabled(false);selectMany.setEnabled(false);clearSelection.setEnabled(false);
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            new Thread(()->send(b,r,ms),"OpticalBatchSender").start();
        }catch(Exception e){text("開始できません："+e.getMessage());}
    }
    private static String clockText(long seconds){return String.format(Locale.JAPAN,"%d:%02d:%02d",seconds/3600,seconds/60%60,seconds%60);}
    private void showProgress(boolean force){
        long now=System.nanoTime();if(!force&&now-lastProgressNs<500_000_000L)return;lastProgressNs=now;
        long elapsed=Math.max(0,now-startedNs),remaining=Math.max(0,plannedNs-elapsed);
        int value=(int)Math.min(999,elapsed*1000.0/Math.max(1,plannedNs));
        String message="完了 "+completedCases+" / "+totalCases+"件\n経過 "+clockText(elapsed/1_000_000_000L)+" ／ 予定 "+clockText((plannedNs+999_999_999L)/1_000_000_000L)+"\n残り目安 "+clockText((remaining+999_999_999L)/1_000_000_000L)+"（時間ベースの推定）";
        runOnUiThread(()->{progress.setProgress(value);timing.setText(message);});
    }
    private void sleepUntil(long deadline)throws Exception{while(!cancel.get()){long left=deadline-System.nanoTime();showProgress(false);if(left<=0)return;Thread.sleep(Math.min(20,Math.max(1,left/1000000)));}throw new InterruptedException("利用者操作または画面移動で停止しました。");}
    private void send(JSONObject b,int[] r,int ms){
        long origin=System.nanoTime();startedNs=origin;lastProgressNs=0;String result="完了";showProgress(true);
        try{
            torchId=null;for(String id:camera.getCameraIdList())if(Boolean.TRUE.equals(camera.getCameraCharacteristics(id).get(CameraCharacteristics.FLASH_INFO_AVAILABLE))){torchId=id;break;}
            if(torchId==null)throw new IllegalStateException("利用できるライトがありません。");
            camera.setTorchMode(torchId,false);text("開始待ち：15秒間消灯");sleepUntil(System.nanoTime()+15_000_000_000L);
            String header=b.getString("header");
            if(!header.isEmpty()){
                text("送信範囲の連携信号を送信中（本文の前）");long deadline=System.nanoTime();
                for(int pulse:OpticalHeader.pulses(header)){
                    if(cancel.get())throw new InterruptedException("停止しました。");
                    if((System.nanoTime()-deadline)/1e6>ms*.30)throw new IllegalStateException("連携信号のライト制御が遅れました。");
                    camera.setTorchMode(torchId,pulse>0);deadline+=(long)Math.abs(pulse)*ms*1_000_000L;sleepUntil(deadline);
                }
                camera.setTorchMode(torchId,false);text("連携信号完了：本文前10秒消灯");sleepUntil(System.nanoTime()+10_000_000_000L);
            }
            JSONArray cases=b.getJSONArray("cases");
            for(int i=r[0]-1;i<r[1];i++){
                JSONObject c=cases.getJSONObject(i);if(cancel.get())throw new InterruptedException("停止しました。");
                text("送信中 "+(i+1)+" / "+cases.length()+"\n"+c.getString("id"));
                JSONObject event=new JSONObject().put("id",c.getString("id")).put("source_batch",c.getString("source_batch")).put("position",i+1).put("start_seconds",(System.nanoTime()-origin)/1e9).put("complete",false);log.put(event);
                JSONArray pulses=c.getJSONArray("pulses");long deadline=System.nanoTime();double maxDelay=0;
                for(int j=0;j<pulses.length();j++){
                    if(cancel.get())throw new InterruptedException("停止しました。");
                    double late=(System.nanoTime()-deadline)/1e6;maxDelay=Math.max(maxDelay,late);if(late>ms*.30)throw new IllegalStateException("ライト制御が遅れました。短点を長くするか端末状態を確認してください。");
                    JSONArray p=pulses.getJSONArray(j);camera.setTorchMode(torchId,p.getBoolean(0));deadline+=(long)ms*p.getInt(1)*1_000_000L;sleepUntil(deadline);
                }
                camera.setTorchMode(torchId,false);event.put("end_seconds",(System.nanoTime()-origin)/1e9).put("complete",true).put("max_control_delay_ms",maxDelay);
                completedCases=i+1;showProgress(true);
                // Event log records global position and original batch ID for later matching.
                if(i+1<r[1]){text("送信継続中：10秒休止\n完了 "+(i+1)+" / "+cases.length()+"　次："+cases.getJSONObject(i+1).getString("labels"));sleepUntil(System.nanoTime()+10_000_000_000L);}
            }
            text("終端確認：5秒間消灯");sleepUntil(System.nanoTime()+5_000_000_000L);
        }catch(Exception e){result="未完了："+e.getMessage();}
        finally{
            if(torchId!=null)try{camera.setTorchMode(torchId,false);}catch(Exception ignored){}
            try{session.put("status",result);}catch(JSONException ignored){}
            showProgress(true);
            final String message=result;runOnUiThread(()->{running=false;if("完了".equals(message))progress.setProgress(1000);batch.setEnabled(true);speed.setEnabled(true);first.setEnabled(false);last.setEnabled(false);start.setEnabled(true);autoHeader.setEnabled(true);selectMany.setEnabled(true);clearSelection.setEnabled(true);if(remote==null)getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);remoteStarted=false;status.setText(message+"\n送信記録を保存できます。実際の点灯時刻は未測定です。");});
        }
    }
    @Override protected void onPause(){super.onPause();if(running)cancel.set(true);disableRemote();}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==9&&result==RESULT_OK&&data!=null&&data.getData()!=null){try(java.io.OutputStream out=getContentResolver().openOutputStream(data.getData())){if(out==null)throw new java.io.IOException("保存先を開けません。");out.write(session.toString(2).getBytes(StandardCharsets.UTF_8));text("送信記録を保存しました。");}catch(Exception e){text("保存エラー："+e.getMessage());}}}
}
