package jp.local.wabun;
import android.app.*;
import android.os.*;
import android.content.*;
import android.bluetooth.BluetoothDevice;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.UUID;

/** Receiver-side controller. Recording remains in the user's camera app. */
public class RemoteActivity extends Activity {
    private BluetoothDevice peer;
    private JSONObject plan;
    private TextView status;
    private boolean busy;
    private Button connect,start,stop,query;
    private Button button(LinearLayout root,String text,Runnable run){Button b=new Button(this);b.setText(text);root.addView(b);b.setOnClickListener(v->run.run());return b;}
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(24,32,24,32);scroll.addView(root);setContentView(scroll);
        root.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(24,32+i.getSystemWindowInsetTop(),24,32+i.getSystemWindowInsetBottom());return i;});
        TextView info=new TextView(this);info.setTextSize(18);root.addView(info);
        try{plan=new JSONObject(getIntent().getStringExtra("plan"));info.setText("受信側：Bluetooth送信指示\n"+getIntent().getStringExtra("summary")+"\n\n送信側で、この端末からの待受をオンにしてください。開始指示が受理されると15秒後に発光します。録画は別途カメラアプリで行ってください。通信失敗時は開始を連打せず状態を確認してください。");}
        catch(Exception e){info.setText("送信範囲がありません。前の画面へ戻ってください。");return;}
        status=new TextView(this);status.setTextSize(18);status.setText("未接続");root.addView(status);
        connect=button(root,"送信側スマートフォンを選択",()->BluetoothRemote.choose(this,d->{peer=d;send("status");}));
        start=button(root,"この範囲で送信開始を指示",()->new AlertDialog.Builder(this).setTitle("相手のライト送信を開始しますか").setMessage("受理後15秒で発光を開始します。録画の準備をしてください。").setNegativeButton("取消",null).setPositiveButton("開始指示",(d,w)->send("start")).show());
        stop=button(root,"相手の送信を停止・消灯",()->send("stop"));
        query=button(root,"相手の進捗を確認",()->send("status"));
        button(root,"選択画面へ戻る",this::finish);
    }
    private void send(String action){
        if(busy)return;if(peer==null){status.setText("先に送信側を選択してください。");return;}
        busy=true;connect.setEnabled(false);start.setEnabled(false);stop.setEnabled(false);query.setEnabled(false);status.setText("通信中…");
        new Thread(()->{
            String message;
            try{
                JSONObject command=new JSONObject(plan.toString()).put("action",action).put("request_id",UUID.randomUUID().toString());
                JSONObject response=BluetoothRemote.request(peer,command);
                message=response.optString("message")+"\n状態："+(response.optBoolean("running")?"送信中":"停止中／待機中")+"\n完了 "+response.optInt("completed")+" / "+response.optInt("total")+"件\n"+response.optString("progress");
                if(!response.optBoolean("ok"))message="指示は受理されませんでした。\n"+message;
            }catch(Exception e){message="通信結果を確認できません："+e.getMessage()+"\n開始指示が届いた可能性があります。状態確認または停止指示を行ってください。";}
            final String result=message;runOnUiThread(()->{busy=false;status.setText(result);connect.setEnabled(true);start.setEnabled(true);stop.setEnabled(true);query.setEnabled(true);});
        },"MorseBluetoothClient").start();
    }
}
