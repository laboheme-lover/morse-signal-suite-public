package jp.local.wabun;

import android.content.ContentResolver;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;

/** Display names from Android's document picker; never expose opaque document IDs. */
public final class InputFileName {
    private InputFileName(){}
    public static String read(ContentResolver resolver,Uri uri){
        if(uri==null)return "（ファイル名を取得できません）";
        if("content".equals(uri.getScheme())){
            try(Cursor c=resolver.query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
                if(c!=null&&c.moveToFirst()){
                    int i=c.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                    if(i>=0&&!c.isNull(i)){String name=clean(c.getString(i));if(!name.isEmpty())return name;}
                }
            }catch(RuntimeException ignored){/* Name lookup must not block file decoding. */}
        }else if("file".equals(uri.getScheme())){
            String name=clean(uri.getLastPathSegment());if(!name.isEmpty())return name;
        }
        return "（ファイル名を取得できません）";
    }
    private static String clean(String s){return s==null?"":s.replace('\r',' ').replace('\n',' ').trim();}
}
