package jp.local.wabun;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.text.Normalizer;

/** Bounded plain-text import. Never silently drops unsupported characters. */
public final class TextInput {
    public static final int MAX_BYTES=65536;
    private TextInput(){}
    public static String read(InputStream in)throws IOException {
        if(in==null)throw new IOException("ファイルを開けません。");
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buf=new byte[4096];int n;
        while((n=in.read(buf))!=-1){
            if(out.size()+n>MAX_BYTES)throw new IOException("テキストファイルは64 KB以内にしてください。");
            out.write(buf,0,n);
        }
        byte[] bytes=out.toByteArray();String text;
        if(bytes.length>=2&&((bytes[0]&255)==255&&(bytes[1]&255)==254))text=decode(bytes,2,StandardCharsets.UTF_16LE);
        else if(bytes.length>=2&&((bytes[0]&255)==254&&(bytes[1]&255)==255))text=decode(bytes,2,StandardCharsets.UTF_16BE);
        else {
            int offset=bytes.length>=3&&(bytes[0]&255)==239&&(bytes[1]&255)==187&&(bytes[2]&255)==191?3:0;
            try{text=decode(bytes,offset,StandardCharsets.UTF_8);}
            catch(CharacterCodingException e){
                if(offset!=0)throw new IOException("UTF-8の文字コードを確認してください。",e);
                try{text=decode(bytes,0,Charset.forName("windows-31j"));}
                catch(CharacterCodingException bad){throw new IOException("UTF-8、Shift_JIS、またはBOM付きUTF-16のTXTを選んでください。",bad);}
            }
        }
        // Show decoded text first; transmission validation belongs to the send action.
        if(text.trim().isEmpty())throw new IllegalArgumentException("テキストファイルが空です。");
        if(text.indexOf('\u0000')>=0)throw new IllegalArgumentException("テキスト以外のデータが含まれています。");
        return MorseCodec.editableText(text).replace("\r\n","\n").replace('\r','\n');
    }
    private static String decode(byte[] bytes,int offset,Charset charset)throws CharacterCodingException {
        return charset.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes,offset,bytes.length-offset)).toString();
    }
}
