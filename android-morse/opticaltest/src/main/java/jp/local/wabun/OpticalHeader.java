package jp.local.wabun;
import java.util.*;
import java.util.zip.CRC32;
import java.nio.charset.StandardCharsets;

/** OB1 application header, International Morse. Not part of the test text. */
public final class OpticalHeader {
    private static final String ALPHABET="0123456789ABCDEFOM";
    private static final String[] CODE={"-----",".----","..---","...--","....-",".....","-....","--...","---..","----.",".-","-...","-.-.","-..",".","..-.","---","--"};
    public static String encode(String hash,int ms,int[] indices){
        int speed=ms==300?0:ms==450?1:ms==600?2:-1;
        if(speed<0||indices.length<1||indices.length>65||!hash.matches("[a-fA-F0-9]{64}"))throw new IllegalArgumentException("Invalid header");
        StringBuilder b=new StringBuilder("OB1").append(hash.substring(0,8).toUpperCase(Locale.ROOT)).append(speed).append(String.format(Locale.ROOT,"%02d",indices.length));
        Set<Integer> seen=new HashSet<>();
        for(int i:indices){if(i<0||i>=65||!seen.add(i))throw new IllegalArgumentException("Invalid selection");b.append(String.format(Locale.ROOT,"%02d",i));}
        CRC32 crc=new CRC32();crc.update(b.toString().getBytes(StandardCharsets.US_ASCII));
        return b.append(String.format(Locale.ROOT,"%08X",crc.getValue())).toString();
    }
    /** Positive units = light; negative units = dark. */
    public static int[] pulses(String text){
        ArrayList<Integer> list=new ArrayList<>();
        for(int c=0;c<text.length();c++){
            int index=ALPHABET.indexOf(text.charAt(c));if(index<0)throw new IllegalArgumentException();
            String code=CODE[index];for(int j=0;j<code.length();j++){list.add(code.charAt(j)=='.'?1:3);if(j+1<code.length())list.add(-1);}
            if(c+1<text.length())list.add(-3);
        }
        int[] result=new int[list.size()];for(int i=0;i<result.length;i++)result[i]=list.get(i);return result;
    }
    public static long units(String text){long n=0;for(int p:pulses(text))n+=Math.abs(p);return n;}
}
