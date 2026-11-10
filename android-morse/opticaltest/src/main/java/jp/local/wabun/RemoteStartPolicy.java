package jp.local.wabun;
import java.util.Set;

/** Validate a remote start before changing selection or triggering the torch. */
public final class RemoteStartPolicy {
    public static void validate(String id,Set<String> consumed,boolean running,String expectedHash,String actualHash,int unit,int[] indices){
        if(id==null||id.isEmpty()||id.length()>80)throw new IllegalArgumentException("指示番号が不正です。");
        if(consumed.contains(id))throw new IllegalArgumentException("同じ開始指示は実行済みです。状態を確認してください。");
        if(running)throw new IllegalArgumentException("すでに送信中です。");
        if(!expectedHash.equals(actualHash))throw new IllegalArgumentException("原稿版が異なります。両端末を更新してください。");
        OpticalHeader.encode(expectedHash,unit,indices);
        if(consumed.size()>=1000)throw new IllegalArgumentException("アプリを開き直してください。");
    }
}
