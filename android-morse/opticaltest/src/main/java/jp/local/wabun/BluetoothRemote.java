package jp.local.wabun;

import android.Manifest;
import android.app.*;
import android.bluetooth.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.Build;
import android.annotation.SuppressLint;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Paired-device, encrypted RFCOMM. A fresh connection carries one request. */
@SuppressLint("MissingPermission") // Every entry point checks permission through choose().
public final class BluetoothRemote implements AutoCloseable {
    public static final UUID SERVICE=UUID.fromString("7d52a2da-48d7-4d8c-a61d-51457ee8b4aa");
    public interface Handler { JSONObject command(JSONObject request) throws Exception; }
    public interface DeviceChoice { void selected(BluetoothDevice device); }
    private volatile boolean enabled;
    private volatile BluetoothServerSocket server;
    private volatile BluetoothSocket client;
    public static void choose(Activity activity,DeviceChoice callback){
        if(Build.VERSION.SDK_INT>=31 && activity.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)!=PackageManager.PERMISSION_GRANTED){
            activity.requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT},82);
            new AlertDialog.Builder(activity).setMessage("近くのデバイスの権限を許可した後、もう一度ボタンを押してください。").setPositiveButton("OK",null).show();return;
        }
        BluetoothManager manager=(BluetoothManager)activity.getSystemService(Context.BLUETOOTH_SERVICE);
        BluetoothAdapter adapter=manager==null?null:manager.getAdapter();
        if(adapter==null){new AlertDialog.Builder(activity).setMessage("Bluetoothを利用できません。").setPositiveButton("OK",null).show();return;}
        if(!adapter.isEnabled()){activity.startActivity(new Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE));return;}
        ArrayList<BluetoothDevice> devices=new ArrayList<>(adapter.getBondedDevices());
        if(devices.isEmpty()){new AlertDialog.Builder(activity).setMessage("先にAndroidのBluetooth設定で2台をペアリングしてください。").setPositiveButton("設定",(d,w)->activity.startActivity(new Intent(android.provider.Settings.ACTION_BLUETOOTH_SETTINGS))).setNegativeButton("閉じる",null).show();return;}
        String[] names=new String[devices.size()];for(int i=0;i<names.length;i++)names[i]=devices.get(i).getName()+"\n"+devices.get(i).getAddress();
        new AlertDialog.Builder(activity).setTitle("接続する相手のスマートフォン").setItems(names,(d,i)->callback.selected(devices.get(i))).setNegativeButton("取消",null).show();
    }
    public void listen(Activity activity,BluetoothDevice allowed,Handler handler,java.util.function.Consumer<String> status){
        enabled=true;
        new Thread(()->{
            try{
                BluetoothAdapter adapter=((BluetoothManager)activity.getSystemService(Context.BLUETOOTH_SERVICE)).getAdapter();
                BluetoothServerSocket opened=adapter.listenUsingRfcommWithServiceRecord("Morse optical remote",SERVICE);
                server=opened;if(!enabled){opened.close();return;}
                status.accept("Bluetooth待受中："+allowed.getName()+"\nこの画面を開いたままにしてください。");
                int failures=0;
                while(enabled){
                    try(BluetoothSocket socket=opened.accept()){
                        client=socket;if(!enabled)break;
                        if(!socket.getRemoteDevice().getAddress().equals(allowed.getAddress())||socket.getRemoteDevice().getBondState()!=BluetoothDevice.BOND_BONDED)continue;
                        Timer timer=new Timer(true);timer.schedule(new TimerTask(){public void run(){try{socket.close();}catch(IOException ignored){}}},8000);
                        try{
                            String raw=new DataInputStream(socket.getInputStream()).readUTF();if(raw.length()>8192)throw new IOException("Request too large");
                            JSONObject request=new JSONObject(raw);
                            FutureTask<JSONObject> task=new FutureTask<>(()->{if(!enabled)throw new IOException("待受を終了しました。");return handler.command(request);});
                            activity.runOnUiThread(task);JSONObject reply;
                            try{reply=task.get(3,TimeUnit.SECONDS);}catch(Exception e){task.cancel(false);reply=new JSONObject().put("ok",false).put("message","処理を確認できません。状態確認を行ってください。");}
                            new DataOutputStream(socket.getOutputStream()).writeUTF(reply.toString());failures=0;
                        }finally{timer.cancel();}
                    }catch(Exception e){if(enabled){if(++failures>=3)throw new IOException("通信エラーが続きました。待受を開始し直してください。",e);status.accept("通信を完了できませんでした。待受は継続中です。");}}
                    finally{client=null;}
                }
            }catch(Exception e){if(enabled)status.accept("Bluetooth待受エラー："+e.getMessage());}
            finally{close();}
        },"MorseBluetoothServer").start();
    }
    public static JSONObject request(BluetoothDevice peer,JSONObject command)throws Exception{
        try(BluetoothSocket socket=peer.createRfcommSocketToServiceRecord(SERVICE)){
            Timer timer=new Timer(true);timer.schedule(new TimerTask(){public void run(){try{socket.close();}catch(IOException ignored){}}},8000);
            try{socket.connect();new DataOutputStream(socket.getOutputStream()).writeUTF(command.toString());return new JSONObject(new DataInputStream(socket.getInputStream()).readUTF());}
            finally{timer.cancel();}
        }
    }
    @Override public void close(){enabled=false;try{if(server!=null)server.close();}catch(IOException ignored){}try{if(client!=null)client.close();}catch(IOException ignored){}}
}
